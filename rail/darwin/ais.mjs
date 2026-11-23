// Live ferries from ships' own AIS position reports (aisstream.io: free key, sign in with GitHub).
// Keeps passenger ships (AIS ship types 60–69) and high-speed craft (40–49): ferries, river boats, Thames Clippers, CalMac…
// Ship types arrive in "static data" messages every few minutes, so a ship shows once both its type and position are known;
// the types are saved so a restart knows them straight away.
import fs from 'node:fs';

export class Ais {
  constructor(file){ this.file = file; this.ships = new Map(); this.types = new Map(); this.msgs = 0; this.last = 0; this.status = 'off';
    try{ const s = JSON.parse(fs.readFileSync(file, 'utf8')); for(const [k, v] of s.types || []) this.types.set(k, v); for(const sh of s.ships || []) this.ships.set(sh.mmsi, sh); }catch(e){} }
  save(){ try{ fs.writeFileSync(this.file + '.tmp', JSON.stringify({types:[...this.types], ships:[...this.ships.values()]})); fs.renameSync(this.file + '.tmp', this.file); }catch(e){ console.warn('ais save', e.message); } }
  static passenger(t){ return (t >= 60 && t <= 69) || (t >= 40 && t <= 49); }
  // one AISStream message (already parsed JSON)
  ingest(m){
    const md = m.MetaData || {}, mmsi = String(md.MMSI || ''); if(!mmsi) return; this.msgs++; this.last = Date.now();
    if(m.MessageType === 'ShipStaticData' || m.MessageType === 'StaticDataReport'){
      const sd = m.Message?.ShipStaticData || m.Message?.StaticDataReport?.ReportB || {}, t = +sd.Type || +sd.ShipType;
      if(t) this.types.set(mmsi, t);
      const sh = this.ships.get(mmsi); if(sh && sd.Destination) sh.dest = String(sd.Destination).trim();
      return; }
    const p = m.Message?.PositionReport || m.Message?.StandardClassBPositionReport || m.Message?.ExtendedClassBPositionReport; if(!p) return;
    const t = this.types.get(mmsi); if(!Ais.passenger(t)) return;
    const lat = +md.latitude, lon = +md.longitude; if(!isFinite(lat) || !isFinite(lon) || (lat === 0 && lon === 0)) return;
    const hd = +p.TrueHeading, sh = this.ships.get(mmsi) || {mmsi};
    Object.assign(sh, {name:String(md.ShipName || sh.name || '').trim(), type:t, lat:+lat.toFixed(5), lon:+lon.toFixed(5), sog:+(+p.Sog || 0).toFixed(1),
      cog:isFinite(+p.Cog) ? Math.round(+p.Cog) : null, hdg:hd >= 0 && hd < 360 ? hd : null, at:Date.now()});
    this.ships.set(mmsi, sh); }
  // ships in a box, heard from in the last 15 minutes
  list(bbox, now = Date.now()){
    const out = []; for(const s of this.ships.values()){ if(now - s.at > 900000) continue;
      if(bbox && (s.lat < bbox[0] || s.lat > bbox[2] || s.lon < bbox[1] || s.lon > bbox[3])) continue; out.push(s); }
    return out; }
  prune(now = Date.now()){ for(const [k, s] of this.ships) if(now - s.at > 3*3600000) this.ships.delete(k); }
  // connect and keep reconnecting. boxes: [[[minLat,minLon],[maxLat,maxLon]], …]
  run(key, boxes){
    let delay = 5000;
    const open = () => { this.status = 'connecting';
      const ws = new WebSocket('wss://stream.aisstream.io/v0/stream');
      ws.onopen = () => { this.status = 'open'; delay = 5000;
        ws.send(JSON.stringify({APIKey:key, BoundingBoxes:boxes, FilterMessageTypes:['PositionReport', 'StandardClassBPositionReport', 'ExtendedClassBPositionReport', 'ShipStaticData', 'StaticDataReport']})); };
      ws.onmessage = async e => { try{ const txt = typeof e.data === 'string' ? e.data : Buffer.from(await e.data.arrayBuffer?.() ?? e.data).toString('utf8'); const m = JSON.parse(txt);
        if(m.error){ this.status = 'error: ' + m.error; console.warn('ais', m.error); return; } this.ingest(m); }catch(err){} };
      ws.onclose = () => { if(!this.status.startsWith('error')) this.status = 'closed'; setTimeout(open, delay); delay = Math.min(delay*2, 300000); };
      ws.onerror = () => {}; };
    open();
    setInterval(() => { this.prune(); this.save(); }, 60000); }
}
