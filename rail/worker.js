// London Live — National Rail relay (Cloudflare Worker)
//
// Holds the Rail Data Marketplace key (as a secret) so it never appears in the public web pages,
// calls the Darwin "Live Departure Board" web service, and returns small JSON the maps can use.
//
// Settings (Cloudflare dashboard → Worker → Settings → Variables and secrets):
//   RDM_KEY        (secret, required)  your Rail Data Marketplace consumer key
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
        return json({ok:true, configured:!!env.RDM_KEY, boardUrl:(env.BOARD_URL || DEFAULT_BOARD_URL).replace(/\?.*$/, '')}, 200, cors);
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
      return json({error:String(e.message || e)}, 502, cors);
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
export const _test = {normaliseBoard, mergeTrains, toMs, stop};
