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
//   GET /vehicles?src=coach → every long-distance coach in England (National Express, Megabus, FlixBus…)
//   GET /vehicles?src=tfe       → Edinburgh buses and trams
//   GET /vehicles?src=gdansk|tallinn|vilnius|warsaw → those cities' buses and trams (open data, no key; they don't allow browsers directly)
//   GET /vehicles?src=gdstop&id=<ZTM stop id> → a Gdańsk stop's next departures
//   GET /metrolink              → Manchester Metrolink departures by stop
//   GET /tfl/<TfL API path>     → TfL's answer, shared by every visitor (cached briefly); optional secret TFL_KEY
//   GET /transitous/api/v5/plan?… → Transitous journey planning (open data, worldwide), named and cached 60 s

const DEFAULT_BOARD_URL = 'https://api1.raildata.org.uk/1010-live-departure-board-dep1_2/LDBWS/api/20220120/GetDepBoardWithDetails/{crs}?numRows=10';
const DEFAULT_ORIGINS = 'https://finncoates.github.io';
const BOARD_TTL = 80;      // seconds a station board is cached (the maps poll every 60 s)
const MAX_STATIONS = 40;   // per /trains call (Cloudflare free plan: 50 outbound requests per call)

export default {
  async fetch(request, env, ctx){
    const url = new URL(request.url);
    const cors = corsHeaders(request, env);
    if(request.method === 'OPTIONS') return new Response(null, {status:204, headers:cors});
    if(request.method === 'POST' && url.pathname === '/report'){ // a page's anonymous error report: passed to the server's log
      const body = (await request.text()).slice(0, 2000);
      if(env.DARWIN_URL) ctx.waitUntil(fetch(env.DARWIN_URL.replace(/\/+$/, '') + '/report', {method:'POST', body, headers:{'x-relay-token':env.RELAY_TOKEN || '', 'content-type':'application/json'}, signal:AbortSignal.timeout(10000)}).catch(() => {}));
      return new Response(null, {status:204, headers:cors}); }
    if(request.method !== 'GET') return json({error:'GET only'}, 405, cors);
    try{
      if(url.pathname === '/' || url.pathname === '/health')
        return json({ok:true, configured:!!env.RDM_KEY, rail:!!env.RDM_KEY, bods:!!env.BODS_KEY, tfe:true, metrolink:!!env.TFGM_KEY, tfl:true, tflKey:!!env.TFL_KEY, live:LIVE_CITIES, darwin:!!env.DARWIN_URL, server:!!env.DARWIN_URL,
          boardUrl:(env.BOARD_URL || DEFAULT_BOARD_URL).replace(/\?.*$/, '')}, 200, cors);
      if(url.pathname === '/vehicles') return json(await vehicles(url, env, ctx), 200, cors, 10);
      if(url.pathname === '/metrolink') return json(await metrolink(env, ctx), 200, cors, 20);
      if(url.pathname.startsWith('/tfl/')) return await tfl(url, env, cors);
      if(url.pathname.startsWith('/transitous/')) return await transitous(url, cors);
      if(url.pathname === '/tt') return await ttTile(url, cors);
      if(url.pathname === '/planes') return await planes(url, cors);
      if(url.pathname === '/gbfs') return await gbfsProxy(url, cors);
      if(url.pathname === '/darwin/trains') return await darwinTrains(url, env, cors);
      if(/^\/srv\/(health|ferries|rt)$/.test(url.pathname)) return await srv(url, env, cors);
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
    if(s.platform) here.plat = String(s.platform).trim().toUpperCase(); /* the board's own station: its platform */
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
  const by = new Map(), plats = new Map(); /* each board knows only its own station's platform: gather them */
  for(const b of boards) for(const s of b.services){
    const key = s.id; for(const c of s.calls) if(c.plat && c.crs){ (plats.get(key) || plats.set(key, {}).get(key))[c.crs] = c.plat; }
    const cur = by.get(key);
    if(!cur || s.calls.filter(c => c.actual).length > cur.calls.filter(c => c.actual).length) by.set(key, s);
  }
  const trains = [...by.values()].filter(s => !s.cancelled).map(s => ({
    id:s.id, op:s.operator, opCode:s.opCode, dest:s.destination, destCrs:s.destCrs, reason:s.reason,
    calls:s.calls.filter(c => c.crs && c.ms != null && !c.cancelled).map(c => { const pl = c.plat || plats.get(s.id)?.[c.crs]; return pl ? [c.crs, c.ms, c.actual ? 1 : 0, pl] : [c.crs, c.ms, c.actual ? 1 : 0]; }),
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
// the cities /vehicles?src= serves live (the page switches each on once it is here)
const LIVE_CITIES = ['gdansk', 'tallinn', 'vilnius', 'warsaw', 'kaunas', 'klaipeda', 'szczecin', 'tampere', 'porto', 'poznan', 'zagreb', 'turin'];
async function vehicles(url, env, ctx){
  const src = url.searchParams.get('src') || 'bods';
  if(src === 'tfe') return cached('tfe', 15, ctx, async () => {
    const r = await fetch(env.TFE_URL || 'https://tfe-opendata.com/api/v1/vehicle_locations', {signal:AbortSignal.timeout(8000)});
    if(!r.ok) throw fail('Edinburgh: HTTP ' + r.status, 502);
    return {src, vehicles:parseTfe(await r.json())};
  });
  const OPEN = {gdansk:['https://ckan2.multimediagdansk.pl/gpsPositions?v=2', parseGdansk], tallinn:['https://transport.tallinn.ee/gps.txt', parseTallinn],
    vilnius:['https://www.stops.lt/vilnius/gps_full.txt', parseVilnius], renfe:['https://gtfsrt.renfe.com/vehicle_positions.json', parseRenfe],
    warsaw:['https://mkuran.pl/gtfs/warsaw/vehicles.json', parseWarsaw],
    kaunas:['https://www.stops.lt/kaunas/gps_full.txt', t => parseStopsLt(t, 'kns', 'Kaunas')], klaipeda:['https://www.stops.lt/klaipeda/gps_full.txt', t => parseStopsLt(t, 'kla', 'Klaipėda')],
    szczecin:['https://www.zditm.szczecin.pl/api/v1/vehicles', parseSzczecin], tampere:['https://data.itsfactory.fi/journeys/api/1/vehicle-activity', parseTampere],
    porto:['https://broker.fiware.urbanplatform.portodigital.pt/v2/entities?type=Vehicle&limit=1000&q=vehicleType==bus', parsePorto],
    // GTFS-realtime (protobuf): read with rtVehicles below; a tram told from its line number
    poznan:['https://www.ztm.poznan.pl/pl/dla-deweloperow/getGtfsRtFile?file=vehicle_positions.pb', b => rtCity(b, 'poz', 'Poznań', r => /^\d{1,2}$/.test(r)), 1],
    zagreb:['https://www.zet.hr/gtfs-rt-protobuf', b => rtCity(b, 'zag', 'ZET', r => /^\d{1,2}$/.test(r)), 1],
    turin:['https://percorsieorari.gtt.to.it/das_gtfsrt/vehicle_position.aspx', b => rtCity(b, 'gtt', 'GTT', r => /^(3|4|9|10|15|16|16CS|16CD)$/.test(r)), 1]};
  if(OPEN[src]) return cached(src, 15, ctx, async () => {
    const r = await fetch(OPEN[src][0], {signal:AbortSignal.timeout(8000), headers:{'user-agent':'LondonLive/1.0 (+https://github.com/finncoates/london-live)'}}); if(!r.ok) throw fail(src + ': HTTP ' + r.status, 502);
    return {src, vehicles:OPEN[src][1](OPEN[src][2] ? new Uint8Array(await r.arrayBuffer()) : await r.text())};
  });
  if(src === 'bustimes'){ // bustimes.org: every UK operator that shares positions (incl. Cardiff Bus, Lothian, Translink), cached and rounded to be polite
    const b = (url.searchParams.get('bbox') || '').split(',').map(Number);
    if(b.length !== 4 || b.some(x => !isFinite(x)) || b[2] <= b[0] || b[3] <= b[1]) throw fail('bbox=minLon,minLat,maxLon,maxLat required', 400);
    if(b[2] - b[0] > 0.6 || b[3] - b[1] > 0.4) throw fail('area too big: zoom in', 400);
    const r2 = x => (Math.round(x*50)/50).toFixed(2), bb = [Math.floor(b[0]*50)/50, Math.floor(b[1]*50)/50, Math.ceil(b[2]*50)/50, Math.ceil(b[3]*50)/50].map(r2);
    return cached('bt:' + bb.join(), 20, ctx, async () => {
      const r = await fetch(`https://bustimes.org/vehicles.json?xmin=${bb[0]}&ymin=${bb[1]}&xmax=${bb[2]}&ymax=${bb[3]}`, {headers:{'user-agent':'london-live-map (finncoates.github.io/london-live)'}, signal:AbortSignal.timeout(10000)});
      if(!r.ok) throw fail('bustimes: HTTP ' + r.status, 502);
      return {src, vehicles:parseBustimes(await r.json())};
    });
  }
  if(src === 'gdstop'){ // a Gdańsk stop's next departures (ZTM Gdańsk open data; no CORS for browsers), cached 20 s
    const id = (url.searchParams.get('id') || '').replace(/[^0-9]/g, '').slice(0, 8); if(!id) throw fail('id required', 400);
    return cached('gd:' + id, 20, ctx, async () => {
      const r = await fetch(`https://ckan2.multimediagdansk.pl/departures?stopId=${id}`, {signal:AbortSignal.timeout(8000)});
      if(!r.ok) throw fail('ztm: HTTP ' + r.status, 502);
      const j = await r.json();
      return {src, id, departures:(j.departures || []).map(d => ({line:String(d.routeShortName ?? d.routeId ?? ''), dest:d.headsign || '', t:Date.parse(d.estimatedTime || d.theoreticalTime) || null, late:d.delayInSeconds ?? null, live:d.status === 'REALTIME'})).filter(d => d.t).slice(0, 30)};
    });
  }
  if(src === 'stop'){ // a bus stop's next departures anywhere in Britain (bustimes.org: timetable + live predictions), cached 45 s
    const id = (url.searchParams.get('id') || '').replace(/[^A-Za-z0-9]/g, '').slice(0, 20); if(!id) throw fail('id required', 400);
    return cached('stop:' + id, 45, ctx, async () => {
      const r = await fetch(`https://bustimes.org/stops/${id}/departures`, {headers:{'user-agent':'london-live-map (finncoates.github.io/london-live)'}, signal:AbortSignal.timeout(8000)});
      if(!r.ok) throw fail('bustimes: HTTP ' + r.status, 502);
      return {src, id, departures:parseStopDeps(await r.text())};
    });
  }
  if(src === 'coach'){ // every long-distance coach in England (National Express, Megabus, FlixBus…), the whole country at once
    if(!env.BODS_KEY) throw fail('BODS_KEY secret is not set on the worker', 503);
    return cached('coach', 30, ctx, async () => {
      const ops = 'NATX,NXSH,MEGA,SMGB,SCMB,FLIX,FLXB,FLXO,SCLK,CTLK';
      const r = await fetch(`https://data.bus-data.dft.gov.uk/api/v1/datafeed/?operatorRef=${ops}&api_key=${encodeURIComponent(env.BODS_KEY)}`, {signal:AbortSignal.timeout(15000)});
      if(!r.ok) throw fail('Bus Open Data: HTTP ' + r.status, 502);
      const out = parseSiriVm(await r.text());
      // FlixBus (and others) that are only on bustimes.org: the whole country by operator
      for(const op of ['FLIX', 'SCLK']){ try{
        const b = await fetch(`https://bustimes.org/vehicles.json?operator=${op}`, {headers:{'user-agent':'london-live-map (finncoates.github.io/london-live)'}, signal:AbortSignal.timeout(8000)});
        if(b.ok) for(const v of parseBustimes(await b.json())){ v.op = op; out.push(v); } }catch(e){} }
      return {src, vehicles:out};
    });
  }
  if(src !== 'bods') throw fail('src must be bods, coach, stop, gdstop, bustimes, tfe or a city: ' + Object.keys(OPEN).join(', '), 400);
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
    const t = Date.parse(tag(x, 'RecordedAtTime') || '') || null; if(t && Date.now() - t > 600000) continue; // no report for 10 min: parked / off service
    const op = tag(x, 'OperatorRef') || ''; if(/^(test|dummy)/i.test(op)) continue; // operators' test feeds
    out.push({id, line:tag(x, 'PublishedLineName') || tag(x, 'LineRef') || '', op, dest:unesc(tag(x, 'DestinationName') || '').replace(/_/g, ' ').replace(/^Destination$/i, ''),
      lat:Math.round(lat*1e5)/1e5, lon:Math.round(lon*1e5)/1e5, brg:brg == null ? null : +brg, t});
  }
  return out;
}
const unesc = s => s.replace(/&amp;/g, '&').replace(/&apos;/g, "'").replace(/&quot;/g, '"').replace(/&lt;/g, '<').replace(/&gt;/g, '>');
function parseTfe(j){
  return (j.vehicles || []).filter(v => v.latitude && v.longitude && v.service_name).map(v => ({id:'tfe:' + v.vehicle_id, line:String(v.service_name), op:'TfE',
    dest:v.destination || '', lat:+v.latitude, lon:+v.longitude, brg:v.heading ?? null, t:v.last_gps_fix ? v.last_gps_fix*1000 : null, tram:v.vehicle_type === 'tram'}));
}
function parseBustimes(list){
  // no operator_id: the vehicle's page names it (acah-25119 → ACAH), except Irish fleet numbers (ie-663-…) and unknown owners (none-…): those take the operator of another vehicle on the same service, or none
  const pre = v => (((v.vehicle || {}).url || '').split('/')[2] || '').split('-')[0].toUpperCase(), bySvc = new Map();
  for(const v of list || []){ const o = v.operator_id || (pre(v) !== 'IE' && pre(v) !== 'NONE' ? pre(v) : ''); if(o && v.service_id != null && !bySvc.has(v.service_id)) bySvc.set(v.service_id, o); }
  return (list || []).filter(v => v.coordinates).map(v => { const slug = ((v.vehicle || {}).url || '').split('/')[2] || '';
    const brand = ((v.vehicle || {}).name || '') + ' ' + ((v.service || {}).url || ''), named = /flix/i.test(brand) ? 'FLIX' : /megabus/i.test(brand) ? 'MEGA' : /national.express/i.test(brand) ? 'NATX' : /citylink/i.test(brand) ? 'SCLK' : '';
    return {id:'bt:' + v.id, line:(v.service || {}).line_name || '', op:v.operator_id || ((pre(v) === 'IE' || pre(v) === 'NONE') && (bySvc.get(v.service_id) || named)) || (pre(v) === 'NONE' ? '' : slug.split('-')[0].toUpperCase()) || named, dest:v.destination || '',
      lat:+v.coordinates[1], lon:+v.coordinates[0], brg:v.heading ?? null, t:Date.parse(v.datetime) || null, col:(v.vehicle || {}).colour || null, late:v.delay != null ? -v.delay : null}; })
    .filter(v => (!v.t || Date.now() - v.t < 600000) && !/^(test|dummy)/i.test(v.op));
}
// bustimes.org departures fragment: rows of [line, destination, scheduled hh:mm, expected hh:mm or '']
function parseStopDeps(html){
  const out = [], strip = x => x.replace(/<[^>]*>/g, ' ').replace(/&shy;|&nbsp;/g, '').replace(/&#x([0-9a-f]+);/gi, (m, h) => String.fromCodePoint(parseInt(h, 16))).replace(/&#(\d+);/g, (m, d) => String.fromCodePoint(+d)).replace(/&quot;/g, '"').replace(/&amp;/g, '&').replace(/\s+/g, ' ').trim();
  const date = (html.match(/name="date" value="([\d-]+)"/) || [])[1] || null;
  for(const row of html.split(/<tr>/).slice(1)){ const td = row.split(/<td[^>]*>/).slice(1).map(c => c.split('</td>')[0]); if(td.length < 3) continue;
    const line = strip(td[0]), dest = strip(td[1].split('<div class="vehicle">')[0]), sched = strip(td[2]), exp = td[3] ? strip(td[3]) : '';
    if(/^\d{1,2}:\d{2}$/.test(sched)) out.push({line, dest, sched, exp:/^\d{1,2}:\d{2}$/.test(exp) ? exp : '', live:/^\d{1,2}:\d{2}$/.test(exp), date}); }
  return out.slice(0, 20);
}
function parseGdansk(txt){
  return (JSON.parse(txt).vehicles || []).filter(v => v.lat && v.lon).map(v => ({id:'gda:' + v.vehicleId, line:String(v.routeShortName || ''), op:'ZTM Gdańsk', dest:v.headsign || '',
    lat:+v.lat, lon:+v.lon, brg:v.direction ?? null, t:Date.parse(v.generated) || null, tram:+v.routeShortName < 100 && v.routeShortName !== '', late:v.delay != null ? -v.delay : null}));
}
// Tallinn: type (1 trolleybus, 2 bus, 3 tram), route, lon×1e6, lat×1e6, -, heading, vehicle, -, -, destination
// Spain: Renfe's live train positions (GTFS-realtime as JSON): Cercanías/Rodalies and more; the label starts with the line (C1-23560-…)
function parseRenfe(txt){ let j; try{ j = JSON.parse(txt); }catch(e){ return []; }
  return (j.entity || []).map(e => e.vehicle).filter(v => v && v.position && v.position.latitude).map(v => { const lab = v.vehicle?.label || '', line = (/^([A-Z]+\d*[a-z]?)-/.exec(lab) || [])[1] || '';
    return {id:'es:' + (v.vehicle?.id || v.trip?.tripId), line, op:'Renfe', dest:'', lat:+v.position.latitude, lon:+v.position.longitude, brg:v.position.bearing ?? null, t:v.timestamp ? +v.timestamp*1000 : null, train:true, kind:'train'}; }); }

function parseTallinn(txt){
  return txt.split('\n').map(l => l.trim().split(',')).filter(a => a.length >= 10 && +a[2] && +a[3]).map(a => ({id:'tln:' + a[6], line:(a[0] === '3' ? '' : a[0] === '1' ? 'T' : '') + a[1], op:'TLT ' + ({1:'trolleybus', 2:'bus', 3:'tram'}[a[0]] || ''),
    dest:a[9] || '', lat:+a[3]/1e6, lon:+a[2]/1e6, brg:a[5] === '' ? null : +a[5], t:null, tram:a[0] === '3'}));
}
// Vilnius: CSV with a header (Transportas, Marsrutas, ..., Ilguma = lon×1e6, Platuma = lat×1e6, Azimutas, ..., KryptiesPavadinimas)
// Warsaw: every ZTM bus and tram (mkuran.pl's open feed from the city's API: {time, positions:[{id, lat, lon, bearing, timestamp, trip_id "date:line:..."}]})
function parseWarsaw(txt){ const j = JSON.parse(txt);
  return (j.positions || []).filter(v => v.lat && v.lon).map(v => { const line = String(v.trip_id || '').split(':')[1] || '', tram = /^\d{1,2}$/.test(line);
    return {id:'waw:' + v.id, line, op:'Warsaw ' + (tram ? 'tram' : 'bus'), dest:'', lat:+v.lat, lon:+v.lon, brg:v.bearing != null ? Math.round(+v.bearing) : null, t:v.timestamp ? Date.parse(v.timestamp) : null, tram}; }); }
// Lithuanian cities on stops.lt (Kaunas, Klaipėda): Vilnius's CSV (lon, lat ×1e6)
function parseStopsLt(txt, pre, city){ return parseVilnius(txt).map(v => ({...v, id:pre + ':' + v.id.slice(4), op:city + ' ' + (/trol/i.test(v.op) ? 'trolleybus' : 'bus')})); }
// Szczecin (ZDiTM's open API): {data:[{line_number, vehicle_type, vehicle_number, direction, latitude, longitude, bearing, punctuality}]}
function parseSzczecin(txt){ return (JSON.parse(txt).data || []).filter(v => v.latitude && v.longitude).map(v => ({id:'szc:' + v.vehicle_number, line:String(v.line_number || ''), op:'ZDiTM ' + v.vehicle_type, dest:v.direction || '',
  lat:+v.latitude, lon:+v.longitude, brg:v.bearing != null ? +v.bearing : null, t:null, tram:v.vehicle_type === 'tram'})); }
// Tampere (ITS Factory's SIRI-like journeys API): trams are operator 56920 (lines 1 and 3)
function parseTampere(txt){ return (JSON.parse(txt).body || []).map(x => { const m = x.monitoredVehicleJourney || {}, l = m.vehicleLocation || {}, tram = m.operatorRef === '56920';
  return {id:'tre:' + m.vehicleRef, line:m.lineRef || '', op:tram ? 'Tampere tram' : 'Nysse', dest:'', lat:+l.latitude, lon:+l.longitude, brg:m.bearing != null ? +m.bearing : null, t:x.recordedAtTime ? Date.parse(x.recordedAtTime) : null, tram}; }).filter(v => v.lat && v.lon); }
// Porto (the city's FIWARE broker: STCP's buses)
function parsePorto(txt){ return (JSON.parse(txt) || []).map(x => { const c = x.location?.value?.coordinates || [], a = x.annotations?.value || [], rt = (a.find(s => /^stcp:route:/.test(s)) || '').split(':')[2] || '';
  return {id:'opo:' + (x.fleetVehicleId?.value || x.id), line:rt, op:'STCP', dest:'', lat:+c[1], lon:+c[0], brg:x.bearing?.value ?? null, t:x.dateObserved?.value ? Date.parse(x.dateObserved.value) : null, tram:false}; }).filter(v => v.lat && v.lon); }
// a city's GTFS-realtime vehicle positions → its buses and trams
function rtCity(b, pre, op, isTram){ return rtVehicles(b).map(v => { const r = String(v.route || v.label.split('/')[0] || '').replace(/U$/, ''), tram = isTram(r);
  return {id:pre + ':' + (v.vid || v.id), line:r, op:op + ' ' + (tram ? 'tram' : 'bus'), dest:'', lat:v.lat, lon:v.lon, brg:v.brg != null ? Math.round(v.brg) : null, t:v.t, tram}; }); }
// GTFS-realtime vehicle positions from protobuf bytes, without a library: [{id, vid, trip, route, lat, lon, brg, speed, t, label}]
function rtVehicles(b){
  const dv = new DataView(b.buffer, b.byteOffset, b.byteLength), out = [], td = new TextDecoder();
  const varint = o => { let x = 0, s = 1, c; do{ c = b[o.p++]; x += (c & 127)*s; s *= 128; }while(c & 128 && o.p < b.length); return x; };
  const fields = (start, end, fn) => { const o = {p:start}; while(o.p < end){ const k = varint(o), f = Math.floor(k/8), w = k & 7;
      if(w === 0) fn(f, 0, varint(o)); else if(w === 2){ const n = varint(o), s = o.p; o.p += n; fn(f, 2, s, s + n); } else if(w === 5){ fn(f, 5, o.p); o.p += 4; } else if(w === 1){ o.p += 8; } else return; } };
  const str = (s, e) => td.decode(b.subarray(s, e)), fl = p => dv.getFloat32(p, true);
  fields(0, b.length, (f, w, s, e) => { if(f !== 2 || w !== 2) return; let id = '', vp = null;
    fields(s, e, (f2, w2, s2, e2) => { if(f2 === 1 && w2 === 2) id = str(s2, e2); else if(f2 === 4 && w2 === 2) vp = [s2, e2]; });
    if(!vp) return; const v = {id, vid:'', trip:'', route:'', lat:null, lon:null, brg:null, speed:null, t:null, label:''};
    fields(vp[0], vp[1], (f3, w3, s3, e3) => {
      if(f3 === 1 && w3 === 2) fields(s3, e3, (f4, w4, s4, e4) => { if(w4 !== 2) return; if(f4 === 1) v.trip = str(s4, e4); else if(f4 === 5) v.route = str(s4, e4); });
      else if(f3 === 2 && w3 === 2) fields(s3, e3, (f4, w4, s4) => { if(w4 !== 5) return; if(f4 === 1) v.lat = fl(s4); else if(f4 === 2) v.lon = fl(s4); else if(f4 === 3) v.brg = fl(s4); else if(f4 === 5) v.speed = fl(s4); });
      else if(f3 === 5 && w3 === 0) v.t = s3*1000;
      else if(f3 === 8 && w3 === 2) fields(s3, e3, (f4, w4, s4, e4) => { if(w4 !== 2) return; if(f4 === 1) v.vid = str(s4, e4); else if(f4 === 2) v.label = str(s4, e4); }); });
    if(v.lat && v.lon) out.push(v); });
  return out; }
function parseVilnius(txt){
  const rows = txt.trim().split('\n').map(l => l.split(',')), h = rows.shift() || [], ix = n => h.indexOf(n);
  const I = {type:ix('Transportas'), route:ix('Marsrutas'), car:ix('MasinosNumeris'), lon:ix('Ilguma'), lat:ix('Platuma'), az:ix('Azimutas'), late:ix('NuokrypisSekundemis'), dest:ix('KryptiesPavadinimas')};
  return rows.filter(a => +a[I.lat] && +a[I.lon]).map(a => ({id:'vno:' + a[I.car], line:a[I.route] || '', op:/trol/i.test(a[I.type]) ? 'Vilnius trolleybus' : 'Vilnius bus', dest:I.dest >= 0 ? a[I.dest] || '' : '',
    lat:+a[I.lat]/1e6, lon:+a[I.lon]/1e6, brg:a[I.az] === '' ? null : +a[I.az], t:null, late:I.late >= 0 && a[I.late] !== '' ? -a[I.late] : null}));
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

// ---------- TfL: one shared copy for every visitor ----------
// TfL allows 500 calls a minute per key, shared by everyone using the app. Every visitor asking TfL directly
// would hit that at ~40 people at once, so the maps ask here: each answer is fetched once and kept a short
// while (live arrivals 20 s, line status 60 s, line shapes a day). Optional secret TFL_KEY: your free TfL app key.
const TFL_TTL = [[/\/Arrivals/i, 20], [/\/Status/i, 60], [/\/(Route\/Sequence|StopPoints|Route)\b/i, 86400], [/^\/BikePoint/i, 60], [/^\/Road/i, 300], [/crowding/i, 300], [/^\/StopPoint/i, 600]];
const TFL_MEM = new Map(), TFL_WAIT = new Map(); // (per worker instance: plus Cloudflare's cache where available)
async function tfl(url, env, cors){
  const path = url.pathname.slice(4);
  if(!/^\/(Line|StopPoint|BikePoint|Road|Mode|crowding|Disruptions|Place|Journey)\b/i.test(path)) return json({error:'not a TfL path this relay passes on'}, 400, cors);
  const q = [...url.searchParams].filter(([k]) => k !== 'app_key').sort(), qs = q.map(([k, v]) => encodeURIComponent(k) + '=' + encodeURIComponent(v)).join('&');
  const key = path + '?' + qs, ttl = (TFL_TTL.find(([re]) => re.test(path)) || [null, 30])[1], now = Date.now();
  let hit = TFL_MEM.get(key);
  if(!hit || now - hit.t > ttl*1000){
    let wait = TFL_WAIT.get(key); // many visitors at once: one call to TfL
    if(!wait){ wait = (async () => {
        const cacheKey = new Request('https://tfl-cache.invalid' + key), cache = typeof caches !== 'undefined' ? caches.default : null;
        let r = cache ? await cache.match(cacheKey).catch(() => null) : null;
        if(!r){ const target = 'https://api.tfl.gov.uk' + path + '?' + qs + (env.TFL_KEY ? (qs ? '&' : '') + 'app_key=' + encodeURIComponent(env.TFL_KEY) : '');
          const up = await fetch(target, {headers:{'user-agent':'london-live-relay'}, signal:AbortSignal.timeout(10000)});
          r = new Response(await up.text(), {status:up.status, headers:{'content-type':up.headers.get('content-type') || 'application/json', 'cache-control':'public, max-age=' + ttl}});
          if(up.ok && cache) await cache.put(cacheKey, r.clone()).catch(() => {}); }
        const v = {t:Date.now(), status:r.status, type:r.headers.get('content-type') || 'application/json', body:await r.text()};
        if(v.status === 429) v.t = Date.now() - Math.max(0, ttl - 10)*1000; // TfL said "too many": don't ask again for 10 s (the pages then ask TfL directly)
        if(v.status === 200 || v.status === 429){ TFL_MEM.set(key, v); if(TFL_MEM.size > 3000) TFL_MEM.delete(TFL_MEM.keys().next().value); }
        return v; })().finally(() => TFL_WAIT.delete(key));
      TFL_WAIT.set(key, wait); }
    hit = await wait; }
  return new Response(hit.body, {status:hit.status, headers:{'content-type':hit.type, 'cache-control':'public, max-age=' + Math.min(ttl, 30), ...cors}}); }

// ---------- Transitous (free, open journey planning across Europe and beyond; https://transitous.org) ----------
// Asked through here so every request names the app, as Transitous asks, and the same question in the same
// minute is answered once. Before a big launch: tell Transitous (they ask to be told above ~720 plans a day).
const TR_MEM = new Map(), TR_WAIT = new Map();
// how long an answer is shared: departures change by the minute, a trip's stops barely, a search or a stop's place never
const TR_TTL = {stoptimes:20, trip:60, plan:60, 'map/stops':300, geocode:86400, 'reverse-geocode':86400};
async function transitous(url, cors){
  const path = url.pathname.slice('/transitous'.length), m = path.match(/^\/api\/v\d+\/(plan|geocode|reverse-geocode|stoptimes|trip|map\/stops)$/);
  if(!m) return json({error:'not a Transitous path this relay passes on'}, 400, cors);
  const ttl = TR_TTL[m[1]] || 60, key = path + url.search, now = Date.now(), hit = TR_MEM.get(key);
  const out = (body, status, how) => new Response(body, {status, headers:{'content-type':'application/json', 'cache-control':status === 200 ? 'public, max-age=' + Math.min(ttl, 300) : 'no-store', 'x-ll-cache':how, ...cors}});
  if(hit && now - hit.t < ttl*1000) return out(hit.body, 200, 'memory');
  // the data centre's shared cache (every worker instance there, not only this one's memory), then one call upstream
  // however many visitors ask the same thing at the same moment
  const ck = new Request('https://tr-cache.invalid' + key), cache = typeof caches !== 'undefined' ? caches.default : null;
  const ch = cache ? await cache.match(ck).catch(() => null) : null;
  if(ch){ const body = await ch.text(); TR_MEM.set(key, {t:now, body}); return out(body, 200, 'shared'); }
  let w = TR_WAIT.get(key);
  if(!w){ w = (async () => { const up = await fetch('https://api.transitous.org' + key, {headers:{'user-agent':'LondonLive/1.0 (+https://github.com/finncoates/london-live)'}, signal:AbortSignal.timeout(25000)});
      const body = await up.text();
      if(up.ok){ TR_MEM.set(key, {t:Date.now(), body}); if(TR_MEM.size > 800) TR_MEM.delete(TR_MEM.keys().next().value);
        if(cache) await cache.put(ck, new Response(body, {headers:{'content-type':'application/json', 'cache-control':'public, max-age=' + ttl}})).catch(() => {}); }
      return {body, status:up.status}; })().finally(() => TR_WAIT.delete(key)); TR_WAIT.set(key, w); }
  const r = await w; return out(r.body, r.status, 'upstream'); }

// ---------- planes: real aircraft positions from ADS-B receivers run by volunteers ----------
// GET /planes?la=51.5&lo=-0.1 → {now, src, ac:[[hex, callsign, lat, lon, track°, speed kt, altitude ft (or -1 on the
// ground), type, registration, seconds since its position, vertical rate ft/min]]} within ~220 km of that 1° square's
// middle. adsb.lol (open data, ODbL), else adsb.fi, else airplanes.live (Cloudflare's shared addresses are sometimes turned away); one call per square every 8 s, shared by everyone.
const PL_MEM = new Map(), PL_WAIT = new Map(), PL_TTL = 8;
async function planes(url, cors){
  const la = Math.round(+url.searchParams.get('la')*2)/2, lo = Math.round(+url.searchParams.get('lo')*2)/2;
  if(!isFinite(la) || !isFinite(lo) || Math.abs(la) > 85 || Math.abs(lo) > 180) return json({error:'la, lo'}, 400, cors);
  const key = la + ',' + lo, now = Date.now(), hit = PL_MEM.get(key);
  const out = (body, how) => new Response(body, {status:200, headers:{'content-type':'application/json', 'cache-control':'public, max-age=' + PL_TTL, 'x-ll-cache':how, ...cors}});
  if(hit && now - hit.t < PL_TTL*1000) return out(hit.body, 'memory');
  const ck = new Request('https://pl-cache.invalid/' + key), cache = typeof caches !== 'undefined' ? caches.default : null;
  const ch = cache ? await cache.match(ck).catch(() => null) : null;
  if(ch){ const body = await ch.text(); PL_MEM.set(key, {t:now, body}); return out(body, 'shared'); }
  let w = PL_WAIT.get(key);
  if(!w){ w = (async () => {
      const UA = {headers:{'user-agent':'LondonLive/1.0 (+https://github.com/finncoates/london-live)'}, signal:AbortSignal.timeout(9000)};
      let d = null, src = 'adsb.lol';
      for(const [s, u] of [['adsb.lol', `https://api.adsb.lol/v2/lat/${la}/lon/${lo}/dist/120`], ['adsb.fi', `https://opendata.adsb.fi/api/v2/lat/${la}/lon/${lo}/dist/120`], ['airplanes.live', `https://api.airplanes.live/v2/point/${la}/${lo}/120`]]){
        try{ const r = await fetch(u, UA); if(r.ok){ d = await r.json(); d.ac ||= d.aircraft; src = s; if(Array.isArray(d.ac)) break; } }catch(e){} }
      if(!d || !Array.isArray(d.ac)) return hit ? hit.body : JSON.stringify({now:Date.now(), src:null, ac:[]});
      const r1 = x => Math.round(x*1e5)/1e5;
      const ac = d.ac.filter(a => a.lat != null && a.lon != null && (a.seen_pos ?? 0) < 60).map(a => [a.hex, (a.flight || '').trim(), r1(a.lat), r1(a.lon), Math.round(a.track ?? a.true_heading ?? 0),
        Math.round(a.gs ?? 0), a.alt_baro === 'ground' ? -1 : Math.round(a.alt_baro ?? a.alt_geom ?? 0), a.t || '', a.r || '', Math.round((a.seen_pos ?? 0)*10)/10, a.baro_rate ?? a.geom_rate ?? 0]);
      const body = JSON.stringify({now:d.now || Date.now(), src, ac});
      PL_MEM.set(key, {t:Date.now(), body}); if(PL_MEM.size > 400) PL_MEM.delete(PL_MEM.keys().next().value);
      if(cache) await cache.put(ck, new Response(body, {headers:{'content-type':'application/json', 'cache-control':'public, max-age=' + PL_TTL}})).catch(() => {});
      return body; })().finally(() => PL_WAIT.delete(key)); PL_WAIT.set(key, w); }
  return out(await w, 'upstream'); }

// ---------- timetable vehicles from Transitous (every train/tram/bus running now, from open timetables) ----------
// GET /tt?la=52.5&lo=-1.5&modes=rail|tram|all → the vehicles on the move in that 0.5° tile in the next ~3 minutes:
// [mode, colour, name, from:[name, code, lat, lon, platform?], to:[…], dep ms, arr ms, realTime, tripId]. One call to Transitous
// per tile every 2 minutes, shared by every visitor (cached here).
const TT_MEM = new Map(), TT_WAIT = new Map();
// Polylines (precision 5): a country-sized tile only needs a rough shape, so points closer than tol° are dropped
const polyDec = str => { const out = []; let i = 0, la = 0, lo = 0;
  while(i < str.length){ for(const k of [0, 1]){ let b, sh = 0, r = 0; do{ b = str.charCodeAt(i++) - 63; r |= (b & 31) << sh; sh += 5; }while(b >= 32); const d = r & 1 ? ~(r >> 1) : r >> 1; if(k) lo += d; else la += d; } out.push([la, lo]); }
  return out; };
const polyEnc = pts => { let o = '', pa = 0, po = 0; const e = v => { v = v < 0 ? ~(v << 1) : v << 1; let c = ''; while(v >= 32){ c += String.fromCharCode((32 | (v & 31)) + 63); v >>= 5; } return c + String.fromCharCode(v + 63); };
  for(const [a, b] of pts){ o += e(a - pa) + e(b - po); pa = a; po = b; } return o; };
const polyThin = (str, tol) => { if(!tol || !str) return str; const p = polyDec(str), t = tol*1e5, out = [p[0]];
  for(let i = 1; i < p.length - 1; i++){ const q = out[out.length - 1]; if(Math.abs(p[i][0] - q[0]) + Math.abs(p[i][1] - q[1]) >= t) out.push(p[i]); }
  if(p.length > 1) out.push(p[p.length - 1]); return polyEnc(out); };
// Long journeys (Strasbourg–Paris) carry their whole shape, repeated in every tile they cross: keep only the stretch
// over this tile (plus a margin) and move the times to match, so the vehicle is still in the right place along it.
const polyClip = (str, dep, arr, box, m) => { if(!str) return [str, dep, arr]; const p = polyDec(str); if(p.length < 3) return [str, dep, arr];
  const [a0, b0, a1, b1] = [(box[0] - m)*1e5, (box[1] - m)*1e5, (box[2] + m)*1e5, (box[3] + m)*1e5], inn = q => q[0] >= a0 && q[0] <= a1 && q[1] >= b0 && q[1] <= b1;
  let i0 = -1, i1 = -1; for(let i = 0; i < p.length; i++) if(inn(p[i])){ if(i0 < 0) i0 = i; i1 = i; }
  if(i0 < 0) return [str, dep, arr]; i0 = Math.max(0, i0 - 1); i1 = Math.min(p.length - 1, i1 + 1);
  if(i0 === 0 && i1 === p.length - 1) return [str, dep, arr];
  const cum = [0]; for(let i = 1; i < p.length; i++){ const dy = p[i][0] - p[i-1][0], dx = (p[i][1] - p[i-1][1])*Math.cos(p[i][0]*1.745e-7); cum.push(cum[i-1] + Math.hypot(dx, dy)); }
  const D = cum[cum.length - 1] || 1, T = arr - dep;
  return [polyEnc(p.slice(i0, i1 + 1)), Math.round(dep + T*cum[i0]/D), Math.round(dep + T*cum[i1]/D)]; };
const TT_MODES = {rail:/RAIL|LONG_DISTANCE|SUBURBAN|NIGHT_RAIL|HIGHSPEED/, tram:/TRAM|SUBWAY|METRO|FUNICULAR|CABLE/, bus:/BUS|COACH/, ferry:/FERRY/};
// bikes and scooters for hire whose open GBFS feeds don't let browsers read them (Vélib', Lime, Voi…): passed through,
// only from these hosts (cities/gbfs-fr-hosts.json, made by cities/fr_gbfs.py), kept 30 s
const GBFS_HOSTS = new Set(["api.gbfs.ecovelo.mobi", "api.gbfs.v2.2.ecovelo.mobi", "api.gbfs.v3.0.ecovelo.mobi", "api.voiapp.io", "data.lime.bike", "eu.ftp.opendatasoft.com", "gbfs.getapony.com", "services.rideyego.com", "stables.donkey.bike", "stce.transdev-hdf.fr", "velib-metropole-opendata.smovengo.cloud", "www.mobility-parc.net"]);
async function gbfsProxy(url, cors){
  const u = url.searchParams.get('u') || ''; let h = ''; try{ h = new URL(u).hostname; }catch(e){}
  if(!GBFS_HOSTS.has(h)) return json({error:'not an allowed bike-share feed'}, 400, cors);
  const r = await fetch(u, {headers:{'user-agent':'LondonLive/1.0 (+https://github.com/finncoates/london-live)'}, cf:{cacheTtl:30, cacheEverything:true}, signal:AbortSignal.timeout(15000)});
  return new Response(r.body, {status:r.status, headers:{'content-type':'application/json', 'cache-control':'public, max-age=30', ...cors}}); }
const TT_LAST = new Map(); // tile → its last good answer, for when Transitous briefly fails
async function ttTile(url, cors){
  const sz = [4, 2, 1, 0.5, 0.25, 0.125].includes(+url.searchParams.get('s')) ? +url.searchParams.get('s') : 0.5; // smaller tiles for dense cities (Paris); 1–4° tiles for a whole country zoomed out (Transitous then sends only intercity / high-speed)
  const la = Math.floor(+url.searchParams.get('la')/sz)*sz, lo = Math.floor(+url.searchParams.get('lo')/sz)*sz;
  if(!isFinite(la) || !isFinite(lo) || Math.abs(la) > 85 || Math.abs(lo) > 180) return json({error:'la, lo required'}, 400, cors);
  const want = (url.searchParams.get('modes') || 'rail').split(',').filter(m => TT_MODES[m] || m === 'all');
  const zm = Math.max(5, Math.min(14, Math.round(+url.searchParams.get('z') || 14))); // Transitous shows fewer, bigger routes when zoomed out
  const bucket = Math.floor(Date.now()/120000)*120000, key = la + ':' + lo + ':' + bucket + ':' + zm + ':' + sz;
  let all = TT_MEM.get(key);
  if(!all){ let w = TT_WAIT.get(key);
    if(!w){ w = (async () => {
        // Cloudflare's cache too (shared by every worker instance in the data centre, not only this one's memory)
        const ck = new Request('https://tt-cache.invalid/' + key), cache = typeof caches !== 'undefined' ? caches.default : null;
        const ch = cache ? await cache.match(ck).catch(() => null) : null; if(ch){ const v = await ch.json(); TT_MEM.set(key, v); return v; }
        const q = `zoom=${zm}&min=${la},${lo}&max=${la + sz},${lo + sz}&startTime=${new Date(bucket).toISOString()}&endTime=${new Date(bucket + 240000).toISOString()}`;
        const get = () => fetch('https://api.transitous.org/api/v5/map/trips?' + q, {headers:{'user-agent':'LondonLive/1.0 (+https://github.com/finncoates/london-live)'}, signal:AbortSignal.timeout(20000)}).catch(e => ({ok:false, status:e.message}));
        let r = await get(); for(const ms of [700, 1800]){ if(r.ok) break; await new Promise(ok => setTimeout(ok, ms)); r = await get(); } // Transitous turns away the odd burst: twice more
        const lastKey = la + ':' + lo + ':' + zm + ':' + sz, last = TT_LAST.get(lastKey), lk = new Request('https://tt-cache.invalid/last/' + lastKey);
        if(!r.ok){ if(last && bucket - last.at <= 600000) return last.v; // keep showing the last good answer (up to 10 min)
          const lc = cache ? await cache.match(lk).catch(() => null) : null; if(lc) return await lc.json(); // (or another instance's, from the shared cache: a fresh instance has none of its own)
          throw fail('Transitous: HTTP ' + r.status, 502); }
        const stop = s => { const r = [s.name, s.stopCode || null, +s.lat.toFixed(5), +s.lon.toFixed(5)], tk = s.track || s.scheduledTrack; if(tk) r.push(String(tk).trim()); return r; }; /* its platform, where the timetable has one */
        const box = [la, lo, la + sz, lo + sz], tol = sz >= 4 ? 0.02 : sz >= 2 ? 0.01 : sz >= 1 ? 0.005 : 0.0002;
        const v = (await r.json()).map(s => { const c = polyClip(s.polyline || '', Date.parse(s.departure), Date.parse(s.arrival), box, Math.max(0.03, sz*0.4));
          return [s.mode, s.routeColor || null, s.trips?.[0]?.displayName || '', stop(s.from), stop(s.to), c[1], c[2], s.realTime ? 1 : 0, s.trips?.[0]?.tripId || '', polyThin(c[0], tol)]; });
        TT_MEM.set(key, v); for(const k of TT_MEM.keys()) if(+k.split(':')[2] < bucket - 240000) TT_MEM.delete(k);
        TT_LAST.set(lastKey, {at:bucket, v}); if(TT_LAST.size > 400) TT_LAST.delete(TT_LAST.keys().next().value);
        if(cache){ const body = JSON.stringify(v); await cache.put(ck, new Response(body, {headers:{'content-type':'application/json', 'cache-control':'public, max-age=240'}})).catch(() => {});
          await cache.put(lk, new Response(body, {headers:{'content-type':'application/json', 'cache-control':'public, max-age=900'}})).catch(() => {}); }
        return v; })().finally(() => TT_WAIT.delete(key));
      TT_WAIT.set(key, w); }
    all = await w; }
  const out = want.includes('all') ? all : all.filter(s => want.some(m => TT_MODES[m].test(s[0])));
  return json({tile:[la, lo], at:bucket, vehicles:out}, 200, cors, 60); }

// ---------- the London Live server's other parts (rail/darwin): live ferries (AIS) and big live feeds (feeds.json) ----------
// /srv/health (what's on, and where), /srv/ferries?bbox, /srv/rt?feed=id&bbox. Boxes are rounded to 0.05° so nearby views
// share an answer; answers are kept 10 s (health 60 s).
const SRV_MEM = new Map();
async function srv(url, env, cors){
  if(!env.DARWIN_URL) return json({error:'the London Live server is not connected (DARWIN_URL)'}, 503, cors);
  const p = url.pathname.slice(4), q = new URLSearchParams();
  const b = (url.searchParams.get('bbox') || '').split(',').map(Number);
  if(b.length === 4 && b.every(isFinite)) q.set('bbox', b.map((x, i) => (i < 2 ? Math.floor(x*20) : Math.ceil(x*20))/20).join(','));
  if(p === '/rt'){ const f = url.searchParams.get('feed') || ''; if(!/^[a-z0-9-]{1,30}$/.test(f)) return json({error:'feed=id required'}, 400, cors); q.set('feed', f); }
  const key = p + '?' + q, ttl = p === '/health' ? 60000 : 10000, hit = SRV_MEM.get(key);
  if(hit && Date.now() - hit.t < ttl) return new Response(hit.body, {status:hit.status, headers:{'content-type':'application/json', 'cache-control':'public, max-age=' + ttl/1000, 'x-ll-cache':'memory', ...cors}});
  // the data centre's shared cache: however many visitors watch a place, the small server is asked once per 10 s per area
  const sck = new Request('https://srv-cache.invalid' + key), scache = typeof caches !== 'undefined' ? caches.default : null;
  const sch = scache ? await scache.match(sck).catch(() => null) : null;
  if(sch){ const body = await sch.text(); SRV_MEM.set(key, {t:Date.now(), body, status:200}); return new Response(body, {status:200, headers:{'content-type':'application/json', 'cache-control':'public, max-age=' + ttl/1000, 'x-ll-cache':'shared', ...cors}}); }
  // the small server can be slow for a moment: 20 s, and its last good answer (up to 5 min old) if it doesn't come
  const r = await fetch(env.DARWIN_URL.replace(/\/+$/, '') + key, {headers:{'x-relay-token':env.RELAY_TOKEN || ''}, signal:AbortSignal.timeout(20000)}).catch(e => ({ok:false, status:504, text:async () => JSON.stringify({error:e.message})}));
  if(!r.ok && hit && Date.now() - hit.t < 300000) return new Response(hit.body, {status:hit.status, headers:{'content-type':'application/json', 'cache-control':'public, max-age=5', ...cors}});
  const body = await r.text(); if(r.ok){ SRV_MEM.set(key, {t:Date.now(), body, status:r.status}); if(SRV_MEM.size > 500) SRV_MEM.delete(SRV_MEM.keys().next().value);
    if(scache) await scache.put(sck, new Response(body, {headers:{'content-type':'application/json', 'cache-control':'public, max-age=' + ttl/1000}})).catch(() => {}); }
  return new Response(body, {status:r.status, headers:{'content-type':'application/json', 'cache-control':'public, max-age=' + (r.ok ? ttl/1000 : 5), ...cors}}); }

// ---------- Darwin (every train's real running), from the London Live Darwin server (rail/darwin) ----------
// Set DARWIN_URL (e.g. http://SERVER-IP:8080) and RELAY_TOKEN (the same secret as on the server). Answers are kept 20 s.
const DW_MEM = new Map();
async function darwinTrains(url, env, cors){
  if(!env.DARWIN_URL) return json({error:'DARWIN_URL is not set on the relay'}, 503, cors);
  const b = (url.searchParams.get('bbox') || '').split(',').map(Number); if(b.length !== 4 || !b.every(isFinite)) return json({error:'bbox=minLat,minLon,maxLat,maxLon required'}, 400, cors);
  const q = b.map((x, i) => (i < 2 ? Math.floor(x*4) : Math.ceil(x*4))/4).join(','), hit = DW_MEM.get(q); // rounded to 0.25°, so nearby views share an answer
  if(hit && Date.now() - hit.t < 20000) return new Response(hit.body, {headers:{'content-type':'application/json', 'cache-control':'public, max-age=20', ...cors}});
  const r = await fetch(env.DARWIN_URL.replace(/\/+$/, '') + '/trains?bbox=' + q, {headers:{'x-relay-token':env.RELAY_TOKEN || ''}, signal:AbortSignal.timeout(20000)}).catch(e => ({ok:false, status:e.message}));
  if(!r.ok){ if(hit && Date.now() - hit.t < 300000) return new Response(hit.body, {headers:{'content-type':'application/json', 'cache-control':'public, max-age=5', ...cors}}); throw fail('Darwin server: HTTP ' + r.status, 502); } // (its last good answer, up to 5 min, rather than no trains)
  const body = await r.text(); DW_MEM.set(q, {t:Date.now(), body}); if(DW_MEM.size > 300) DW_MEM.delete(DW_MEM.keys().next().value);
  return new Response(body, {headers:{'content-type':'application/json', 'cache-control':'public, max-age=20', ...cors}}); }

// ---------- helpers ----------
const cleanCrs = s => (s || '').trim().toUpperCase().replace(/[^A-Z]/g, '').slice(0, 3) || null;
const stripTags = s => String(s || '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
function corsHeaders(request, env){
  const allowed = (env.ALLOWED_ORIGINS || DEFAULT_ORIGINS).split(',').map(s => s.trim());
  const origin = request.headers.get('origin') || '';
  const ok = allowed.includes('*') || allowed.includes(origin) || /^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(origin);
  return {'access-control-allow-origin':ok ? origin || allowed[0] : allowed[0], 'access-control-allow-methods':'GET, OPTIONS', 'vary':'origin'};
}
function json(data, status, cors, maxAge){
  return new Response(JSON.stringify(data), {status, headers:{'content-type':'application/json', ...(maxAge ? {'cache-control':`public, max-age=${maxAge}`} : {}), ...cors}});
}
export const _test = {normaliseBoard, mergeTrains, toMs, stop, parseSiriVm, parseTfe, parseGdansk, parseTallinn, parseVilnius, parseBustimes};
