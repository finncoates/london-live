// ---------- National Rail (live via the relay in rail/worker.js; see rail/SETUP.md) ----------
// Trains come from Darwin departure boards at the big London stations. Each operator is a "line"
// (mode 'rail'); its drawn network is built from the stops its trains actually call at.
const RAIL_DEFAULT_RELAY = ''; // ← set to the deployed relay address (e.g. https://london-rail.NAME.workers.dev) to switch it on for everyone
const RAIL = {
  relay:(Q.get('rail') || (() => { try{ return localStorage.getItem('railRelay'); }catch(e){ return null; } })() || RAIL_DEFAULT_RELAY).replace(/\/+$/, ''),
  stations:null, byCrs:{}, state:'off', msg:'', last:0, boards:new Map(),
};
// Stations polled for live trains: the London termini and big interchanges (≤ 40, the relay's limit)
const RAIL_HUBS = 'VIC,CLJ,WAT,LBG,CHX,CST,BFR,STP,KGX,EUS,MYB,PAD,LST,FST,SRA,ECR,WIM,RMD,SUR,LEW,ZFD,WFJ,HHY,TOM,ENF,BKG,SVS,EAL,HRW,SNF,DFD,BXY,GTW,WOK,SAC,FPK,WCY,OLD,SUO,RDG'.split(',');
// Operator colours (brand-like, approximate)
const RAIL_COL = {NT:'#262262', TP:'#09A4EC', SR:'#1E467D', SN:'#5C9F3B', TL:'#E9438D', SW:'#24398C', SE:'#1D82D4', GW:'#0A493E', CC:'#B7007C', LE:'#D70428', GN:'#5A2C83',
  CH:'#00A7DF', GR:'#CE0E2D', VT:'#004354', EM:'#713563', HX:'#532E63', GX:'#EB1E2D', XC:'#660F21', GC:'#1D1D1B', LD:'#2B6EF5',
  HT:'#DE005C', AW:'#E10600', LM:'#00BF6F', XR:'#60399E', LO:'#FA7B05', IL:'#1E90FF'};
const railOn = () => !!RAIL.relay;
// which stations to poll: London's termini/hubs in London, elsewhere the 25 nearest stations to the view
const inLondonView = p => p[0] > 51.28 && p[0] < 51.72 && p[1] > -0.56 && p[1] < 0.35;
function railHubs(){
  const c = typeof map !== 'undefined' && map.getCenter ? map.getCenter() : null, p = c ? [c.lat(), c.lng()] : [51.51, -0.12];
  if(inLondonView(p) || !RAIL.stations) return {key:'london', list:RAIL_HUBS};
  const near = RAIL.stations.map(([crs, , lat, lon]) => [crs, dist([lat, lon], p)]).filter(x => x[1] < 40000).sort((a, b) => a[1] - b[1]).slice(0, 25).map(x => x[0]);
  return {key:near.slice(0, 3).join(), list:near.length ? near : RAIL_HUBS};
}
async function railStations(){
  if(RAIL.stations) return RAIL.stations;
  const base = location.pathname.includes('/journey') ? '../rail/' : 'rail/';
  const list = await (await fetch(base + 'stations.json')).json();
  RAIL.stations = list; for(const [crs, n, lat, lon] of list) RAIL.byCrs[crs] = {n, p:[lat, lon]};
  return list;
}
const nearestCrs = (p, max = 350) => { let best = null, bd = max; for(const [crs, , lat, lon] of RAIL.stations || []){ const d = dist([lat, lon], p); if(d < bd){ bd = d; best = crs; } } return best; };
async function railGet(path){
  if(RAIL.relay === 'demo') return railDemo(path);
  const r = await fetch(RAIL.relay + path); if(!r.ok) throw new Error((await r.json().catch(() => ({}))).error || 'HTTP ' + r.status);
  return r.json();
}
// one "line" per operator, created on first sight
function railLine(code, name){
  const id = 'nr-' + (code || 'XX'); let l = BY[id];
  if(!l){
    const polys = []; // straight stop-to-stop lines; also used as the "track" trains follow
    l = {id, name:name || code, colour:RAIL_COL[code] || '#5B6770', mode:'rail', group:'rail', on:true, count:0, polys, routes:[], stops:{}, seg:{},
      adj:new Set(), byName:{}, alias:{}, curves:polys, pathCache:{}, snapCache:{}, layer:new Group(), rail:true, edges:new Set()};
    ACTIVE.push(l); BY[id] = l; if(typeof renderModeChips === 'function') renderModeChips();
  }
  return l;
}
async function refreshRail(){
  const onRailLeg = typeof J !== 'undefined' && J.active && J.plan && J.plan.legs.some(L => L.kind === 'rail');
  if(!railOn() || (MODES_OFF.has('rail') && !onRailLeg)) return; // switched off — unless you're on a train
  try{
    await railStations();
    const hubs = railHubs(); RAIL.region = hubs.key;
    const res = await railGet('/trains?crs=' + hubs.list.join(','));
    const t0 = Date.now(), seen = new Set(); let newStops = false;
    for(const tr of res.trains || []){
      const l = railLine(tr.opCode, tr.op);
      const calls = tr.calls.filter(c => RAIL.byCrs[c[0]]); if(calls.length < 2 || calls.at(-1)[1] < t0 - 120000) continue;
      for(const [crs] of calls) if(!l.stops[crs]){ l.stops[crs] = RAIL.byCrs[crs]; newStops = true; }
      // draw the network from consecutive stops (once per pair)
      for(let i = 1; i < calls.length; i++){ const a = calls[i-1][0], b = calls[i][0], k = a < b ? a + b : b + a;
        if(!l.edges.has(k)){ l.edges.add(k); l.polys.push([RAIL.byCrs[a].p, RAIL.byCrs[b].p]); LANES = null; linesSig = ''; } }
      const key = 'nr:' + tr.id; let t = trains.get(key);
      if(!t){ t = {key, rail:true}; trains.set(key, t); }
      Object.assign(t, {line:l.id, ahead:calls.map(c => [c[0], c[1]]), prev:calls[0][0], next:calls[1][0], arr:calls[1][1],
        towards:tr.dest || '', loc:tr.reason || '', seen:t0}); seen.add(key);
    }
    for(const [k, t] of trains) if(t.rail && !seen.has(k) && t0 - t.seen > 150000) trains.delete(k);
    for(const l of ACTIVE) if(l.rail) l.count = 0;
    for(const t of trains.values()) if(t.rail && BY[t.line]) BY[t.line].count++;
    if(newStops){ if(typeof STATIONS !== 'undefined') STATIONS = null; if(typeof STIDX !== 'undefined') STIDX = null; } // station search/near-you indexes
    RAIL.state = 'live'; RAIL.msg = `${[...trains.values()].filter(t => t.rail).length} trains`; RAIL.last = t0;
  }catch(e){ RAIL.state = 'error'; RAIL.msg = e.message; console.warn('rail', e); }
  if(typeof renderLegend === 'function') renderLegend();
  if(typeof renderRailStatus === 'function') renderRailStatus();
}
// a station's National Rail departures (for station cards / journey legs), cached 30 s
async function railBoard(crs){
  const c = RAIL.boards.get(crs); if(c && Date.now() - c.t < 30000) return c.d;
  const d = await railGet('/board?crs=' + crs); RAIL.boards.set(crs, {t:Date.now(), d}); return d;
}
// a station's National Rail departures in the same shape as TfL arrivals (so boards/cards can mix them)
async function railArrivals(crs){
  if(!railOn() || !/^[A-Z]{3}$/.test(crs)) return [];
  try{
    const b = await railBoard(crs), now = Date.now();
    return (b.services || []).filter(s => !s.cancelled).map(s => { const here = s.calls.find(c => c.crs === crs) || {}; const l = railLine(s.opCode, s.operator);
      const late = here.st && here.t && here.t !== here.st;
      return {lineId:l.id, vehicleId:s.id, timeToStation:Math.max(0, Math.round(((here.ms || now) - now)/1000)), destinationName:s.destination || '',
        towards:s.destination || '', platformName:s.platform ? 'Platform ' + s.platform : '', rail:true, late, scheduled:here.st, reason:s.reason}; })
      .filter(a => a.timeToStation < 3600);
  }catch(e){ return []; }
}
if(railOn()){ setTimeout(refreshRail, 2500); setInterval(refreshRail, 60000);
  // moved to another part of the country: poll that area's stations straight away
  setTimeout(() => { if(typeof map !== 'undefined' && map.addListener) map.addListener('idle', () => { if(RAIL.stations && RAIL.region && railHubs().key !== RAIL.region && map.getZoom() >= 9) refreshRail(); }); }, 3000); }

// settings row in the Map menu: status, relay address, demo
function renderRailStatus(){
  const el = document.getElementById('railRow'); if(!el) return;
  const st = !RAIL.relay ? 'Not connected' : RAIL.relay === 'demo' ? 'Demo data (not real trains)' : RAIL.state === 'live' ? 'Live · ' + RAIL.msg : RAIL.state === 'error' ? 'Problem: ' + RAIL.msg : 'Connecting…';
  el.querySelector('.rs').textContent = st;
  el.querySelector('.rs').className = 'rs ' + (RAIL.state === 'error' ? 'bad' : RAIL.state === 'live' && RAIL.relay !== 'demo' ? 'good' : '');
}
(function addRailRow(){
  const menu = document.getElementById('mapMenu'); if(!menu || document.getElementById('railRow')) return;
  const d = document.createElement('div'); d.className = 'mm-row mm-rail'; d.id = 'railRow';
  d.innerHTML = `<span>National Rail<small class="rs"></small></span><span class="rbtn"><button type="button" data-r="set">Relay…</button><button type="button" data-r="demo">${RAIL.relay === 'demo' ? 'Stop demo' : 'Demo'}</button></span>`;
  menu.appendChild(d);
  d.addEventListener('click', e => {
    const b = e.target.closest('[data-r]'); if(!b) return;
    let v = null;
    if(b.dataset.r === 'demo') v = RAIL.relay === 'demo' ? '' : 'demo';
    else { v = prompt('National Rail relay address (from rail/SETUP.md), or leave empty to turn off:', RAIL.relay && RAIL.relay !== 'demo' ? RAIL.relay : 'https://'); if(v === null) return; v = v.trim(); if(v === 'https://') v = ''; }
    try{ v ? localStorage.setItem('railRelay', v) : localStorage.removeItem('railRelay'); }catch(x){}
    location.reload();
  });
  const css = document.createElement('style');
  css.textContent = '.mm-rail .rs{display:block;color:var(--mute);font-size:12px}.mm-rail .rs.good{color:var(--good,#188038)}.mm-rail .rs.bad{color:var(--bad,#d93025)}.mm-rail .rbtn{display:flex;gap:6px;flex:none}.mm-rail .rbtn button{font-size:12px;padding:5px 9px}';
  document.head.appendChild(css);
  renderRailStatus();
})();

// ---- demo data (?rail=demo): made-up trains on real routes, to preview the feature without a key ----
function railDemo(path){
  const R = [['Southern','SN',[['VIC',0],['CLJ',6],['ECR',15],['GTW',30]]],['Thameslink','TL',[['STP',0],['ZFD',4],['BFR',9],['LBG',13],['ECR',26],['GTW',40]]],
    ['South Western Railway','SW',[['WAT',0],['VXH',3],['CLJ',7],['WIM',13],['SUR',20],['WOK',33]]],['Southeastern','SE',[['CHX',0],['WAE',2],['LBG',6],['LEW',14],['DFD',33]]],
    ['c2c','CC',[['FST',0],['LHS',4],['WHM',8],['BKG',13],['UPM',21]]],['Greater Anglia','LE',[['LST',0],['SRA',7],['RMF',18],['SNF',29]]],
    ['Great Western Railway','GW',[['PAD',0],['EAL',8],['SLO',18],['RDG',26]]],['Chiltern Railways','CH',[['MYB',0],['WCX',8],['HRW',16]]],
    ['Northern','NT',[['MAN',0],['SPT',8],['MAC',22],['CRE',45]]],['TransPennine Express','TP',[['MCV',0],['HUD',25],['DEW',32],['LDS',45],['YRK',70]]],
    ['ScotRail','SR',[['EDB',0],['HYM',4],['LIN',18],['FKK',27],['GLQ',50]]],['West Midlands Railway','LM',[['WVH',0],['SAD',8],['BHM',18],['BHI',30],['COV',40],['LMS',55]]]];
  const now = Date.now(), base = Math.floor(now/600000)*600000, trains = [];
  R.forEach(([op, code, st], ri) => { for(let k = -5; k <= 2; k++){ const s = base + (k*10 - ri*2)*60000, slot = Math.round(s/600000), delay = (slot + ri) % 3 === 0 ? 3 : 0;
    trains.push({id:'demo' + code + slot, op, opCode:code, dest:(RAIL.byCrs[st.at(-1)[0]] || {}).n, reason:delay ? 'Demo: delayed by a signalling problem' : null,
      calls:st.map(([c, m]) => [c, s + (m + delay)*60000, s + (m + delay)*60000 < now ? 1 : 0])}); } });
  if(path.startsWith('/trains')) return {trains};
  const crs = (path.match(/crs=([A-Z]{3})/) || [])[1];
  return {crs, name:(RAIL.byCrs[crs] || {}).n, services:trains.filter(t => t.calls.some(c => c[0] === crs && c[1] > now - 60000)).map(t => { const i = t.calls.findIndex(c => c[0] === crs);
    return {id:t.id, operator:t.op, opCode:t.opCode, platform:String(1 + i), destination:t.dest, reason:t.reason, cancelled:false,
      calls:t.calls.map(c => ({crs:c[0], name:(RAIL.byCrs[c[0]] || {}).n, ms:c[1], actual:!!c[2]}))}; }).sort((a, b) => a.calls.find(c => c.crs === crs).ms - b.calls.find(c => c.crs === crs).ms)};
}
// ---------- end National Rail ----------
