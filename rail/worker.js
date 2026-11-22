// London Live — relay (Cloudflare Worker): National Rail + live vehicles around Great Britain
//
// Holds the API keys (as secrets) so they never appear in the public web pages, calls the
// upstream services and returns small JSON the maps can use:
//   - National Rail: Darwin "Live Departure Board" (Rail Data Marketplace key)
//   - Buses in England: Bus Open Data Service live locations (free key)
//   - Edinburgh buses and trams: Transport for Edinburgh open data (no key)
//   - Manchester Metrolink: TfGM departures (free key)
//
// Settings (Cloudflare dashboard → Worker → Settings → Variables and secrets):
//   RDM_KEY        (secret, for National Rail)  your Rail Data Marketplace consumer key
//   BODS_KEY       (secret, for buses in England) from https://data.bus-data.dft.gov.uk (free, instant)
//   TFGM_KEY       (secret, for Manchester Metrolink) from https://developer.tfgm.com (free)
//   BOARD_URL      (optional) the board endpoint from the product's Specification page, with {crs}
//                  default: Live Departure Board (GetDepBoardWithDetails, up to 10 trains per station)
//   KEY_HEADER     (optional) header the key goes in; default "x-apikey"
//   ALLOWED_ORIGINS (optional) comma-separated sites allowed to call this; default finncoates.github.io
//
// Endpoints:
//   GET /health                 → {ok, configured}
//   GET /board?crs=VIC          → one station's departures, with calling points and delays
//   GET /trains?crs=VIC,CLJ,... → every train seen on those boards, merged, with times at each stop
//                                 (what the live map needs to place trains)
//   GET /vehicles?src=bods&bbox=minLon,minLat,maxLon,maxLat → live bus positions (England)
//   GET /vehicles?src=tfe       → Edinburgh buses and trams
//   GET /metrolink              → Manchester Metrolink departures by stop

const DEFAULT_BOARD_URL = 'https://api1.raildata.org.uk/1010-live-departure-board-dep1_2/LDBWS/api/20220120/GetDepBoardWithDetails/{crs}?numRows=10';
const DEFAULT_ORIGINS = 'https://finncoates.github.io';
const BOARD_TTL = 80;      // seconds a station board is cached (the maps poll every 60 s)
const MAX_STATIONS = 40;   // per /trains call (Cloudflare free plan: 50 outbound requests per call)

export default {
  async fetch(request, env, ctx){
    const url = new URL(request.url);
    const cors = corsHeaders(request, env);
    if(request.method === 'OPTIONS') return new Response(null, {status:204, headers:cors});
    if(request.method !== 'GET') return json({error:'GET only'}, 405, cors);
    try{
      if(url.pathname === '/' || url.pathname === '/health')
        return json({ok:true, configured:!!env.RDM_KEY, rail:!!env.RDM_KEY, bods:!!env.BODS_KEY, tfe:true, metrolink:!!env.TFGM_KEY,
          boardUrl:(env.BOARD_URL || DEFAULT_BOARD_URL).replace(/\?.*$/, '')}, 200, cors);
      if(url.pathname === '/vehicles') return json(await vehicles(url, env, ctx), 200, cors, 10);
      if(url.pathname === '/metrolink') return json(await metrolink(env, ctx), 200, cors, 20);
      if(!env.RDM_KEY) return json({error:'RDM_KEY secret is not set on the worker'}, 503, cors);
      if(url.pathname === '/board'){
        const crs = cleanCrs(url.searchParams.get('crs'));
        if(!crs) return json({error:'crs=XXX required'}, 400, cors);
        const raw = await getBoard(crs, env, ctx);
        return json(normaliseBoard(raw, crs), 200, cors, 30);
      }
      if(url.pathname === '/trains'){
        const list = [...new Set((url.searchParams.get('crs') || '').split(',').map(cleanCrs).filter(Boolean))].slice(0, MAX_STATIONS);
        if(!list.length) return json({error:'crs=AAA,BBB required'}, 400, cors);
        const boards = await Promise.all(list.map(c => getBoard(c, env, ctx).then(r => normaliseBoard(r, c)).catch(e => ({crs:c, error:String(e.message || e), services:[]}))));
        return json(mergeTrains(boards), 200, cors, 30);
      }
      return json({error:'not found'}, 404, cors);
    }catch(e){
      return json({error:String(e.message || e)}, e.status || 502, cors);
    }
  }
};

// ---------- upstream ----------
async function getBoard(crs, env, ctx){
  const target = (env.BOARD_URL || DEFAULT_BOARD_URL).replace('{crs}', crs);
  const cacheKey = new Request('https://cache.local/board/' + encodeURIComponent(target));
  const cache = typeof caches !== 'undefined' ? caches.default : null;
  if(cache){ const hit = await cache.match(cacheKey); if(hit) return hit.json(); }
  const r = await fetch(target, {headers:{[env.KEY_HEADER || 'x-apikey']:env.RDM_KEY, accept:'application/json'}, signal:AbortSignal.timeout(8000)});
  if(!r.ok) throw new Error(`board ${crs}: HTTP ${r.status}`);
  const data = await r.json();
  if(cache && ctx) ctx.waitUntil(cache.put(cacheKey, new Response(JSON.stringify(data), {headers:{'cache-control':`max-age=${BOARD_TTL}`}})));
  return data;
}

// ---------- normalising (tolerant of the public and staff versions of the service) ----------
const arr = x => Array.isArray(x) ? x : x == null ? [] : [x];
const pick = (o, ...ks) => { for(const k of ks) if(o && o[k] != null && o[k] !== '') return o[k]; return null; };
// calling points come as [{callingPoint:[...]}] (public) or [...] (staff)
function callingPoints(list){
  const out = [];
  for(const group of arr(list).slice(0, 1)){ // dividing/joining trains have extra groups: keep the main one
    if(group && Array.isArray(group.callingPoint)) out.push(...group.callingPoint);
    else if(group && group.callingPoint) out.push(group.callingPoint);
    else if(group && (group.crs || group.locationName)) out.push(group);
  }
  return out;
}
// one stop: scheduled time, expected/actual time (or null), whether it has happened, cancelled
function stop(cp, kind){
  const st = pick(cp, kind === 'dep' ? 'std' : 'sta', 'st', 'std', 'sta');
  const at = pick(cp, 'at', kind === 'dep' ? 'atd' : 'ata', 'atd', 'ata');
  const et = pick(cp, 'et', kind === 'dep' ? 'etd' : 'eta', 'etd', 'eta');
  const cancelled = !!(cp.isCancelled || cp.cancelled || /cancel/i.test(et || '') );
  let actual = false, time = st, note = null;
  if(at && at !== 'No report'){ actual = true; time = /^\d\d:\d\d/.test(at) ? at.slice(0, 5) : st; }
  else if(et){ if(/^\d\d:\d\d/.test(et)) time = et.slice(0, 5); else if(!/on time/i.test(et)) note = et; }
  return {crs:cp.crs || null, name:cp.locationName || '', st:st && st.slice(0, 5), t:time && time.slice(0, 5), actual, cancelled, note};
}
function normaliseBoard(raw, crs){
  const gen = raw.generatedAt || new Date().toISOString();
  const services = arr(raw.trainServices).map(s => {
    const prev = callingPoints(s.previousCallingPoints).map(cp => stop(cp, 'arr'));
    const here = stop({crs:raw.crs || crs, locationName:raw.locationName, std:s.std, etd:s.etd, atd:s.atd, sta:s.sta, eta:s.eta, ata:s.ata, isCancelled:s.isCancelled}, 'dep');
    const next = callingPoints(s.subsequentCallingPoints).map(cp => stop(cp, 'arr'));
    const calls = [...prev, here, ...next];
    // serviceID differs from board to board; the RID (staff version) or origin + its time is the same everywhere
    const key = s.rid || ((s.operatorCode || '') + ':' + (calls[0].crs || '') + ':' + (calls[0].st || '') + ':' + (arr(s.destination)[0]?.crs || ''));
    return {
      id:key, boardId:s.serviceID || s.serviceId || null,
      operator:s.operator || null, opCode:s.operatorCode || null,
      platform:s.platform || null,
      std:here.st, etd:pick(s, 'etd', 'eta') || null,
      cancelled:!!s.isCancelled || here.cancelled,
      reason:s.cancelReason || s.delayReason || null,
      origin:arr(s.origin).map(o => o.locationName).join(' & ') || null,
      destination:arr(s.destination).map(o => o.locationName).join(' & ') || null,
      destCrs:arr(s.destination)[0]?.crs || null,
      calls:calls.map(c => ({...c, ms:toMs(c.t, gen)})),
    };
  });
  return {crs:raw.crs || crs, name:raw.locationName || crs, generatedAt:gen, messages:arr(raw.nrccMessages).map(m => stripTags(m.value || m.Value || m)).filter(Boolean), services};
}
// merge the same train seen on several boards; keep the best-known time at each stop
function mergeTrains(boards){
  const by = new Map();
  for(const b of boards) for(const s of b.services){
    const key = s.id;
    const cur = by.get(key);
    if(!cur || s.calls.filter(c => c.actual).length > cur.calls.filter(c => c.actual).length) by.set(key, s);
  }
  const trains = [...by.values()].filter(s => !s.cancelled).map(s => ({
    id:s.id, op:s.operator, opCode:s.opCode, dest:s.destination, destCrs:s.destCrs, reason:s.reason,
    calls:s.calls.filter(c => c.crs && c.ms != null && !c.cancelled).map(c => [c.crs, c.ms, c.actual ? 1 : 0]),
  })).filter(t => t.calls.length >= 2);
  return {generatedAt:new Date().toISOString(), stations:boards.map(b => ({crs:b.crs, ok:!b.error, error:b.error || undefined})), trains};
}

// ---------- time: "HH:MM" (UK local) → epoch ms, using the board's generatedAt as reference ----------
const LDN = new Intl.DateTimeFormat('en-GB', {timeZone:'Europe/London', hourCycle:'h23', year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', second:'2-digit'});
function parts(ms){ const o = {}; for(const p of LDN.formatToParts(new Date(ms))) o[p.type] = p.value; return o; }
function londonToMs(y, m, d, hh, mm){
  const guess = Date.UTC(y, m - 1, d, hh, mm), p = parts(guess);
  return guess - (Date.UTC(+p.year, p.month - 1, +p.day, +p.hour, +p.minute, +p.second) - guess);
}
function toMs(hhmm, genIso){
  if(!hhmm || !/^\d\d:\d\d/.test(hhmm)) return null;
  const ref = Date.parse(genIso) || Date.now(), p = parts(ref);
  let ms = londonToMs(+p.year, +p.month, +p.day, +hhmm.slice(0, 2), +hhmm.slice(3, 5));
  if(ms - ref > 12*3600e3) ms -= 864e5; else if(ref - ms > 12*3600e3) ms += 864e5; // around midnight
  return ms;
}

// ---------- live vehicles (buses/trams with GPS) ----------
// Everyone viewing the same area shares one upstream call: answers are cached for 15 s
// (the Cache API works on a custom domain; on *.workers.dev it is skipped and each call goes upstream).
async function cached(key, ttl, ctx, fn){
  const cache = typeof caches !== 'undefined' ? caches.default : null, k = new Request('https://cache.local/' + encodeURIComponent(key));
  if(cache){ const hit = await cache.match(k); if(hit) return hit.json(); }
  const data = await fn();
  if(cache && ctx) ctx.waitUntil(cache.put(k, new Response(JSON.stringify(data), {headers:{'cache-control':`max-age=${ttl}`}})));
  return data;
}
const fail = (msg, status) => Object.assign(new Error(msg), {status});
async function vehicles(url, env, ctx){
  const src = url.searchParams.get('src') || 'bods';
  if(src === 'tfe') return cached('tfe', 15, ctx, async () => {
    const r = await fetch(env.TFE_URL || 'https://tfe-opendata.com/api/v1/vehicle_locations', {signal:AbortSignal.timeout(8000)});
    if(!r.ok) throw fail('Edinburgh: HTTP ' + r.status, 502);
    return {src, vehicles:parseTfe(await r.json())};
  });
  if(src !== 'bods') throw fail('src must be bods or tfe', 400);
  if(!env.BODS_KEY) throw fail('BODS_KEY secret is not set on the worker', 503);
  // bounding box, rounded so nearby viewers share the cache; at most ~0.5° × 0.35° (a city)
  const b = (url.searchParams.get('bbox') || '').split(',').map(Number);
  if(b.length !== 4 || b.some(x => !isFinite(x)) || b[2] <= b[0] || b[3] <= b[1]) throw fail('bbox=minLon,minLat,maxLon,maxLat required', 400);
  if(b[2] - b[0] > 0.6 || b[3] - b[1] > 0.4) throw fail('area too big: zoom in', 400);
  const r2 = x => (Math.round(x*50)/50).toFixed(2), bb = [Math.floor(b[0]*50)/50, Math.floor(b[1]*50)/50, Math.ceil(b[2]*50)/50, Math.ceil(b[3]*50)/50].map(r2).join(',');
  return cached('bods:' + bb, 15, ctx, async () => {
    const r = await fetch(`https://data.bus-data.dft.gov.uk/api/v1/datafeed/?boundingBox=${bb}&api_key=${encodeURIComponent(env.BODS_KEY)}`, {signal:AbortSignal.timeout(10000)});
    if(!r.ok) throw fail('Bus Open Data: HTTP ' + r.status, 502);
    return {src, bbox:bb, vehicles:parseSiriVm(await r.text())};
  });
}
// SIRI-VM XML → [{id, line, op, dest, lat, lon, brg, t}] (no XML library in Workers: simple, tolerant scanning)
const TAGS = {}; // compiled once (the free plan allows ~10 ms of CPU per request)
const tag = (x, n) => { const m = x.match(TAGS[n] ||= new RegExp(`<(?:\\w+:)?${n}[^>]*>([^<]*)</(?:\\w+:)?${n}>`)); return m ? m[1].trim() : null; };
function parseSiriVm(xml){
  const out = [], seen = new Set();
  for(const m of xml.matchAll(/<(?:\w+:)?VehicleActivity\b[^>]*>([\s\S]*?)<\/(?:\w+:)?VehicleActivity>/g)){
    const x = m[1], lat = +tag(x, 'Latitude'), lon = +tag(x, 'Longitude'); if(!lat || !lon) continue;
    const id = (tag(x, 'OperatorRef') || '') + ':' + (tag(x, 'VehicleRef') || tag(x, 'FramedVehicleJourneyRef') || out.length);
    if(seen.has(id)) continue; seen.add(id);
    const brg = tag(x, 'Bearing');
    out.push({id, line:tag(x, 'PublishedLineName') || tag(x, 'LineRef') || '', op:tag(x, 'OperatorRef') || '', dest:unesc(tag(x, 'DestinationName') || ''),
      lat:Math.round(lat*1e5)/1e5, lon:Math.round(lon*1e5)/1e5, brg:brg == null ? null : +brg, t:Date.parse(tag(x, 'RecordedAtTime') || '') || null});
  }
  return out;
}
const unesc = s => s.replace(/&amp;/g, '&').replace(/&apos;/g, "'").replace(/&quot;/g, '"').replace(/&lt;/g, '<').replace(/&gt;/g, '>');
function parseTfe(j){
  return (j.vehicles || []).filter(v => v.latitude && v.longitude && v.service_name).map(v => ({id:'tfe:' + v.vehicle_id, line:String(v.service_name), op:'TfE',
    dest:v.destination || '', lat:+v.latitude, lon:+v.longitude, brg:v.heading ?? null, t:v.last_gps_fix ? v.last_gps_fix*1000 : null, tram:v.vehicle_type === 'tram'}));
}
// Manchester Metrolink: platform departure boards (no positions) → [{stop, dir, line, trams:[{dest, wait, status}]}]
async function metrolink(env, ctx){
  if(!env.TFGM_KEY) throw fail('TFGM_KEY secret is not set on the worker', 503);
  return cached('metrolink', 20, ctx, async () => {
    const r = await fetch('https://api.tfgm.com/odata/Metrolinks', {headers:{'Ocp-Apim-Subscription-Key':env.TFGM_KEY}, signal:AbortSignal.timeout(10000)});
    if(!r.ok) throw fail('TfGM: HTTP ' + r.status, 502);
    const j = await r.json(), out = [];
    for(const p of j.value || []){ const trams = [];
      for(let i = 0; i < 4; i++){ const d = p['Dest' + i]; if(d) trams.push({dest:d, wait:+p['Wait' + i] || 0, status:p['Status' + i] || ''}); }
      out.push({stop:p.StationLocation, atco:p.AtcoCode, dir:p.Direction, line:p.Line, trams}); }
    return {updated:new Date().toISOString(), platforms:out};
  });
}

// ---------- helpers ----------
const cleanCrs = s => (s || '').trim().toUpperCase().replace(/[^A-Z]/g, '').slice(0, 3) || null;
const stripTags = s => String(s || '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
function corsHeaders(request, env){
  const allowed = (env.ALLOWED_ORIGINS || DEFAULT_ORIGINS).split(',').map(s => s.trim());
  const origin = request.headers.get('origin') || '';
  const ok = allowed.includes('*') || allowed.includes(origin) || /^http:\/\/localhost(:\d+)?$/.test(origin);
  return {'access-control-allow-origin':ok ? origin || allowed[0] : allowed[0], 'access-control-allow-methods':'GET, OPTIONS', 'vary':'origin'};
}
function json(data, status, cors, maxAge){
  return new Response(JSON.stringify(data), {status, headers:{'content-type':'application/json', ...(maxAge ? {'cache-control':`public, max-age=${maxAge}`} : {}), ...cors}});
}
export const _test = {normaliseBoard, mergeTrains, toMs, stop, parseSiriVm, parseTfe};
