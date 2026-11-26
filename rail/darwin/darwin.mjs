// Darwin Push Port → every train's calling points (the part that doesn't need Kafka, so it can be tested on its own)
//
// Darwin sends XML "Pport" messages. The two that matter here:
//   <schedule rid uid trainId ssd toc> <OR|OPOR|IP|OPIP|PP|DT|OPDT tpl pta ptd wta wtd wtp/> … </schedule>
//       the train's whole run: every timing point (TIPLOC) with its times
//   <TS rid uid ssd> <Location tpl wta wtd wtp pta ptd> <arr|dep|pass at=".." et=".."/> </Location> … </TS>
//       actual (at) and expected (et) times as the train runs
// Times are "HH:MM" or "HH:MM:SS" (UK local) on the schedule start date (ssd), rolling past midnight.
import {XMLParser} from 'fast-xml-parser';

const parser = new XMLParser({ignoreAttributes:false, attributeNamePrefix:'', removeNSPrefix:true, isArray:(name) => ['schedule', 'TS', 'Location', 'OR', 'OPOR', 'IP', 'OPIP', 'PP', 'DT', 'OPDT', 'deactivated', 'uR', 'sR'].includes(name)});
const arr = x => x == null ? [] : Array.isArray(x) ? x : [x];
const LOC_KINDS = ['OR', 'OPOR', 'IP', 'OPIP', 'PP', 'DT', 'OPDT'];

// "HH:MM(:SS)" on the day `ssd` (YYYY-MM-DD, UK local) → epoch ms; `after` (ms): roll to the next day if it would go backwards
const LDN = new Intl.DateTimeFormat('en-GB', {timeZone:'Europe/London', hourCycle:'h23', year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit'});
// (the UK's offset changes only on the hour: worked out once an hour, not for each of the day's ~600,000 times; the
// time-zone formatter for every one made a request for London's trains take 19 s on the small server)
const OFF = new Map();
function londonOffsetMin(utcMs){ const h = Math.floor(utcMs/3600e3); let o = OFF.get(h); if(o !== undefined) return o;
  const p = Object.fromEntries(LDN.formatToParts(new Date(h*3600e3)).map(x => [x.type, x.value]));
  o = Math.round((Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour, +p.minute) - h*3600e3)/60000); if(OFF.size > 5000) OFF.clear(); OFF.set(h, o); return o; }
export function toMs(hhmm, ssd, after){
  if(!hhmm || !ssd) return null; const [h, m, s] = hhmm.split(':').map(Number); if(!isFinite(h) || !isFinite(m)) return null;
  const [Y, M, D] = ssd.split('-').map(Number); const guess = Date.UTC(Y, M - 1, D, h, m, s || 0);
  let t = guess - londonOffsetMin(guess)*60000;
  if(after != null){ while(t < after - 6*3600e3) t += 864e5; } // past midnight
  return t; }

const CALLS = new WeakMap(); // train → its worked-out calls (kept out of the saved state)
export class Darwin {
  constructor(){ this.trains = new Map(); this.msgs = 0; this.last = 0; }
  // one Kafka message (RDM's JSON topic wraps the XML in a "bytes" field) or raw XML
  ingest(raw){
    let xml = typeof raw === 'string' ? raw : raw?.toString?.('utf8') ?? '';
    if(xml.trimStart().startsWith('{')){ try{ const j = JSON.parse(xml); xml = j.bytes || j.Bytes || j.message || j.body || ''; }catch(e){ return; } }
    let pp;
    if(typeof xml === 'string' && xml.trimStart().startsWith('{')){ // RDM's JSON topic: the Pport itself as JSON, same names as the XML ({"ts", "uR":{"TS":{…}}})
      try{ pp = JSON.parse(xml); }catch(e){ return; } if(pp.Pport) pp = pp.Pport; if(!pp.uR && !pp.sR) return; }
    else { if(!xml.includes('Pport')) return;
      let doc; try{ doc = parser.parse(xml); }catch(e){ return; } pp = doc.Pport; if(!pp) return; }
    this.msgs++; this.last = Date.now();
    for(const u of [...arr(pp.uR), ...arr(pp.sR)]){
      for(const s of arr(u.schedule)) this.schedule(s);
      for(const ts of arr(u.TS)) this.status(ts);
      for(const d of arr(u.deactivated)) this.trains.delete(d.rid);
    } }
  schedule(s){
    const t = this.trains.get(s.rid) || {rid:s.rid, locs:[]};
    Object.assign(t, {partial:false, uid:s.uid, trainId:s.trainId, ssd:s.ssd, toc:s.toc, cancelled:s.isCancelled === 'true' || s.cancelReason != null});
    const old = new Map(t.locs.map(l => [l.tpl + '|' + (l.w || ''), l]));
    const locs = [];
    for(const k of LOC_KINDS) for(const l of arr(s[k])) locs.push({k, tpl:l.tpl, pta:l.pta, ptd:l.ptd, wta:l.wta, wtd:l.wtd, wtp:l.wtp, can:l.can === 'true'});
    // Darwin lists them in order inside the schedule but grouped by kind once parsed: put them back in time order
    for(const l of locs){ l.w = l.wtd || l.wta || l.wtp; }
    const base = secs((locs.find(l => l.k === 'OR' || l.k === 'OPOR') || locs[0] || {}).w); t.base = base;
    locs.sort((a, b) => order(a, base) - order(b, base));
    for(const l of locs){ const o = old.get(l.tpl + '|' + (l.w || '')); if(o){ l.at = o.at; l.et = o.et; } }
    t.locs = locs; t.v = (t.v || 0) + 1; this.trains.set(s.rid, t); }
  status(ts){
    let t = this.trains.get(ts.rid);
    if(!t){ t = {rid:ts.rid, uid:ts.uid, ssd:ts.ssd, locs:[], partial:true}; this.trains.set(ts.rid, t); } // no schedule seen yet: build from the updates
    t.ssd ||= ts.ssd;
    for(const L of arr(ts.Location)){
      const w = L.wtd || L.wta || L.wtp;
      let l = t.locs.find(x => x.tpl === L.tpl && (!w || x.w === w)) || t.locs.find(x => x.tpl === L.tpl);
      if(!l){ l = {k:'IP', tpl:L.tpl, pta:L.pta, ptd:L.ptd, wta:L.wta, wtd:L.wtd, wtp:L.wtp, w}; t.locs.push(l); if(t.base == null) t.base = secs(w); t.locs.sort((a, b) => order(a, t.base) - order(b, t.base)); }
      for(const ev of ['arr', 'pass', 'dep']){ const e = L[ev]; if(!e) continue; // the time it leaves a station wins (the map runs station to station)
        if(e.at){ l.at = e.at; l.atEv = ev; } else if(e.et && !l.at){ l.et = e.et; } }
      const pl = platOf(L.plat); if(pl !== undefined) l.plat = pl; } // its platform (null: kept from the public)
    t.updated = Date.now(); t.v = (t.v || 0) + 1; }
  // every train running now (or about to), with its stations and their times: the shape the map's rail engine takes
  //  {id, op, opCode, dest, destCrs, calls:[[CRS, ms, actual 0/1], …]}   (only points that are stations with a CRS code)
  calls(tiplocs, now = Date.now(), bbox = null, names = {}){
    const out = [], at = this._at && this._atFor === tiplocs ? this._at : (this._atFor = tiplocs, this._at = Object.fromEntries(Object.values(tiplocs).filter(v => v[2]).map(v => [v[2], v])));
    const inBox = c => { const x = at[c[0]]; return x && x[0] >= bbox[0] && x[0] <= bbox[2] && x[1] >= bbox[1] && x[1] <= bbox[3]; };
    for(const t of this.trains.values()){
      if(t.cancelled || !t.locs.length || !t.ssd) continue;
      // its times and stations, worked out again only when the train changes (each request went through all ~600,000 times)
      let C = CALLS.get(t);
      if(!C || C.v !== t.v || C.tl !== tiplocs){ let prevMs = null; const pts = [];
        for(const l of t.locs){ if(l.can) continue;
          const sched = l.ptd || l.pta || l.wtd || l.wta || l.wtp, ms = toMs((l.at || l.et || sched || '').slice(0, 8), t.ssd, prevMs);
          if(ms == null) continue; prevMs = ms; pts.push({tpl:l.tpl, ms, actual:!!l.at, kind:l.k, plat:l.plat}); }
        const calls = []; for(const p of pts){ const x = tiplocs[p.tpl]; if(x && x[2] && (!calls.length || calls[calls.length-1][0] !== x[2])) calls.push(p.plat ? [x[2], p.ms, p.actual ? 1 : 0, p.plat] : [x[2], p.ms, p.actual ? 1 : 0]); }
        C = {v:t.v, tl:tiplocs, live:pts.some(p => p.actual), first:pts.length > 1 ? pts[0].ms : null, last:pts.length > 1 ? pts[pts.length - 1].ms : null, calls}; CALLS.set(t, C); }
      if(C.first == null || C.last < now - 10*60e3 || C.first > now + 30*60e3) continue; // finished, or not yet started
      const calls = C.calls; if(calls.length < 2) continue;
      if(bbox){ // the stretch the train is on now must touch the box
        let i = calls.findIndex(c => c[1] > now); if(i < 0) i = calls.length - 1; const a = calls[Math.max(0, i - 1)], b = calls[i];
        if(!inBox(a) && !inBox(b)) continue; }
      const last = t.locs.filter(l => !l.can).at(-1), dx = last && tiplocs[last.tpl];
      out.push({id:t.rid, op:TOC[t.toc] || t.toc || '', opCode:t.toc || '', dest:dx && names[dx[2]] || '', destCrs:dx && dx[2] || null, headcode:t.trainId || '', live:C.live, calls});
    }
    return out; }
  prune(now = Date.now()){ // forget trains long finished
    for(const [rid, t] of this.trains){ const last = t.locs.at(-1); const ms = last && toMs((last.at || last.et || last.wta || last.wtp || last.wtd || '').slice(0, 8), t.ssd);
      if(ms != null && ms < now - 1.5*3600e3) this.trains.delete(rid); } }
}
// a TS location's platform: <plat platsup="true" conf="true">7</plat> (XML) or the same as JSON; suppressed ones
// (platsup / cisPlatsup: not to be shown to the public) are dropped
function platOf(x){ if(x == null) return undefined; if(typeof x !== 'object') return String(x).trim().toUpperCase() || undefined;
  if(x.platsup === 'true' || x.platsup === true || x.cisPlatsup === 'true' || x.cisPlatsup === true) return null;
  const v = x['#text'] ?? x[''] ?? x.value ?? x.content ?? x.plat; return v == null ? undefined : String(v).trim().toUpperCase() || undefined; }
// timing points in running order: by working time, from the train's first point (after midnight = the next day)
function secs(w){ const [h, m, s] = (w || '').split(':').map(Number); return isFinite(h) ? h*3600 + (m || 0)*60 + (s || 0) : 0; }
function order(l, base = 0){ const x = secs(l.w || l.wtd || l.wta || l.wtp); return x < base - 6*3600 ? x + 86400 : x; }
export const TOC = {GR:'LNER', EM:'East Midlands Railway', VT:'Avanti West Coast', XC:'CrossCountry', NT:'Northern', TP:'TransPennine Express', SR:'ScotRail', SN:'Southern', TL:'Thameslink', SW:'South Western Railway', SE:'Southeastern', GW:'Great Western Railway', CC:'c2c', LE:'Greater Anglia', GN:'Great Northern', CH:'Chiltern Railways', GC:'Grand Central', HT:'Hull Trains', AW:'Transport for Wales', LM:'West Midlands Railway', ME:'Merseyrail', LD:'Lumo', CS:'Caledonian Sleeper', HX:'Heathrow Express', GX:'Gatwick Express', IL:'Island Line', LO:'London Overground', XR:'Elizabeth line', ES:'Eurostar', LN:'London Northwestern Railway', ZZ:'Other'};
