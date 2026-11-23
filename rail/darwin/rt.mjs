// Live vehicles from GTFS-realtime feeds that are too big or too strict for the relay (one poll here, shared by
// everyone; the relay asks for just the box on screen). Feeds are listed in feeds.json; a feed whose key isn't set is skipped.
// Route names, colours and kinds (bus, tram, metro, train, ferry) come from the feed's GTFS timetable: only its small
// routes.txt (and agency.txt) are read, straight out of the zip with ranged downloads, once a day.
import zlib from 'node:zlib';
import {createRequire} from 'node:module';
const require = createRequire(import.meta.url);
const GTFSRT = require('gtfs-realtime-bindings').transit_realtime;
const UA = {'user-agent':'LondonLive/1.0 (+https://github.com/finncoates/london-live)'};

// ---------- reading single files out of a remote zip ----------
// Big timetables (the Netherlands' is 280 MB) are read with ranged downloads: the directory at the end, then just the
// files wanted. A server that ignores ranges (or a small zip) is simply downloaded whole.
function centralDir(buf){ // the end-of-central-directory record
  for(let i = buf.length - 22; i >= 0; i--) if(buf.readUInt32LE(i) === 0x06054b50) return {size:buf.readUInt32LE(i + 12), offset:buf.readUInt32LE(i + 16)};
  throw new Error('not a zip'); }
function entries(cd){ const out = new Map(); let i = 0;
  while(i + 46 <= cd.length && cd.readUInt32LE(i) === 0x02014b50){
    const method = cd.readUInt16LE(i + 10), csize = cd.readUInt32LE(i + 20), nlen = cd.readUInt16LE(i + 28), xlen = cd.readUInt16LE(i + 30), clen = cd.readUInt16LE(i + 32), off = cd.readUInt32LE(i + 42);
    out.set(cd.toString('utf8', i + 46, i + 46 + nlen).replace(/^.*\//, ''), {method, csize, off}); i += 46 + nlen + xlen + clen; }
  return out; }
export async function zipFiles(url, names, headers = {}){
  const get = async (u, rg) => { const r = await fetch(u, {headers:{...UA, ...headers, ...(rg ? {range:'bytes=' + rg} : {})}, signal:AbortSignal.timeout(300000)}); if(!r.ok) throw new Error('HTTP ' + r.status); return r; };
  const r0 = await get(url, '-65536');
  let read, end; // read(from, length) → bytes of the zip; end: its last 64 kB (where the directory is)
  if(r0.status === 206){ const total = +(r0.headers.get('content-range') || '').split('/')[1], tail = Buffer.from(await r0.arrayBuffer()), base = total - tail.length, u = r0.url || url; end = tail;
    read = async (from, len) => from >= base && from + len <= total ? tail.subarray(from - base, from - base + len) : Buffer.from(await (await get(u, `${from}-${from + len - 1}`)).arrayBuffer()); }
  else { const all = Buffer.from(await r0.arrayBuffer()); read = async (from, len) => all.subarray(from, from + len); end = all; }
  const cdi = centralDir(end), ents = entries(await read(cdi.offset, cdi.size)), out = {};
  for(const n of names){ const en = ents.get(n); if(!en) continue;
    const lh = await read(en.off, 30), data = await read(en.off + 30 + lh.readUInt16LE(26) + lh.readUInt16LE(28), en.csize);
    out[n] = (en.method === 8 ? zlib.inflateRawSync(data) : data).toString('utf8').replace(/^﻿/, ''); }
  return out; }

// ---------- CSV (GTFS: quoted fields, commas inside quotes) ----------
export function csv(text){
  const rows = []; let row = [], f = '', q = false;
  for(let i = 0; i < text.length; i++){ const c = text[i];
    if(q){ if(c === '"'){ if(text[i + 1] === '"'){ f += '"'; i++; } else q = false; } else f += c; }
    else if(c === '"') q = true; else if(c === ','){ row.push(f); f = ''; }
    else if(c === '\n' || c === '\r'){ if(c === '\r' && text[i + 1] === '\n') i++; row.push(f); f = ''; if(row.length > 1 || row[0]) rows.push(row); row = []; }
    else f += c; }
  if(f || row.length){ row.push(f); rows.push(row); }
  const h = rows.shift() || []; return rows.map(r => Object.fromEntries(h.map((k, i) => [k.trim(), r[i]]))); }

// GTFS route_type (basic and extended) → the map's kinds
export const kindOf = t => { t = +t; return t === 0 || (t >= 900 && t < 1000) ? 'tram' : t === 1 || (t >= 400 && t < 500) ? 'metro' : t === 2 || (t >= 100 && t < 200) ? 'train'
  : t === 4 || (t >= 1000 && t < 1300) ? 'ferry' : t === 5 || t === 6 || t === 7 || t === 12 || (t >= 1300 && t < 1500) ? 'tram' : 'bus'; };

export class Feed {
  constructor(cfg, env){ this.cfg = cfg; this.env = env; this.vehicles = []; this.routes = new Map(); this.trips = new Map(); this.at = 0; this.error = null; this.polls = 0; }
  sub(x){ return String(x).replace(/\$([A-Z_]+)/g, (_, n) => encodeURIComponent(this.env[n] || '')); }
  headers(){ const h = {}; for(const [k, v] of Object.entries(this.cfg.headers || {})) h[k] = String(v).replace(/\$([A-Z_]+)/g, (_, n) => this.env[n] || ''); return h; }
  get enabled(){ return !this.cfg.needs || this.cfg.needs.every(n => this.env[n]); }
  async loadRoutes(){ if(!this.cfg.gtfs) return;
    try{ const f = await zipFiles(this.cfg.gtfs, ['routes.txt', 'agency.txt', ...(this.cfg.trips ? ['trips.txt'] : [])], this.cfg.gtfsHeaders ? this.headers() : {});
      const ag = new Map((f['agency.txt'] ? csv(f['agency.txt']) : []).map(a => [a.agency_id, a.agency_name]));
      this.routes = new Map(csv(f['routes.txt'] || '').map(r => [r.route_id, {name:r.route_short_name || r.route_long_name || '', kind:kindOf(r.route_type),
        col:/^[0-9a-f]{6}$/i.test(r.route_color || '') ? '#' + r.route_color : null, op:ag.get(r.agency_id) || (ag.size === 1 ? [...ag.values()][0] : '') || ''}]));
      if(f['trips.txt']) this.trips = new Map(csv(f['trips.txt']).map(t => [t.trip_id, t.route_id])); // a feed that gives only the trip: its route from the timetable
      console.log(this.cfg.id, 'routes:', this.routes.size, 'trips:', this.trips.size); }
    catch(e){ console.warn(this.cfg.id, 'routes', e.message); } }
  async poll(){
    try{ const r = await fetch(this.sub(this.cfg.url), {headers:{...UA, ...this.headers()}, signal:AbortSignal.timeout(30000)});
      if(!r.ok) throw new Error('HTTP ' + r.status);
      const m = GTFSRT.FeedMessage.decode(new Uint8Array(await r.arrayBuffer())), now = Date.now(), out = [];
      for(const e of m.entity){ const v = e.vehicle; if(!v?.position) continue;
        const ts = +v.timestamp*1000 || now; if(now - ts > 600000) continue; // silent for 10 minutes: gone
        const rid = v.trip?.routeId || this.trips.get(v.trip?.tripId), rt = this.routes.get(rid) || {}, p = v.position;
        out.push({id:String(v.vehicle?.id || e.id), lat:+p.latitude.toFixed(5), lon:+p.longitude.toFixed(5), bearing:p.bearing != null && isFinite(p.bearing) ? Math.round(p.bearing) : null,
          line:rt.name || v.vehicle?.label || '', kind:rt.kind || this.cfg.kind || 'bus', col:rt.col || null, op:rt.op || this.cfg.name, trip:v.trip?.tripId || null, route:rid || null, at:ts}); }
      this.vehicles = out; this.at = now; this.error = null; this.polls++; }
    catch(e){ this.error = e.message; console.warn(this.cfg.id, e.message); } }
  list(bbox){ return bbox ? this.vehicles.filter(v => v.lat >= bbox[0] && v.lat <= bbox[2] && v.lon >= bbox[1] && v.lon <= bbox[3]) : this.vehicles; }
  run(){ this.loadRoutes().finally(() => this.poll()); setInterval(() => this.poll(), (this.cfg.every || 30)*1000); setInterval(() => this.loadRoutes(), 24*3600000); }
}
