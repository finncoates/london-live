// Live vehicles from GTFS-realtime feeds that are too big or too strict for the relay (one poll here, shared by
// everyone; the relay asks for just the box on screen). Feeds are listed in feeds.json; a feed whose key isn't set is skipped.
// Route names, colours and kinds (bus, tram, metro, train, ferry) come from the feed's GTFS timetable: only its small
// routes.txt (and agency.txt) are read, straight out of the zip with ranged downloads, once a day.
import zlib from 'node:zlib';
import fs from 'node:fs';
import fsp from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {Readable} from 'node:stream';
import {pipeline} from 'node:stream/promises';
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
  else { const n = +(r0.headers.get('content-length') || 0); // no ranges: the whole zip; a big one (Stockholm's) goes to disk, not memory
    if(!n || n > 30e6){ const tmp = path.join(os.tmpdir(), 'gtfs-' + process.pid + '-' + Date.now() + '.zip');
      await pipeline(Readable.fromWeb(r0.body), fs.createWriteStream(tmp)); const fh = await fsp.open(tmp, 'r'), size = (await fh.stat()).size;
      const rd = async (from, len) => { const b = Buffer.alloc(len); await fh.read(b, 0, len, from); return b; };
      try{ end = await rd(Math.max(0, size - 65536), Math.min(size, 65536)); const base = Math.max(0, size - 65536), cdi = centralDir(end);
        const ents = entries(await rd(cdi.offset, cdi.size)); return await pick(ents, rd, names); }
      finally{ await fh.close().catch(() => {}); fsp.unlink(tmp).catch(() => {}); } }
    const all = Buffer.from(await r0.arrayBuffer());
    read = async (from, len) => all.subarray(from, from + len); end = all; }
  const cdi = centralDir(end), ents = entries(await read(cdi.offset, cdi.size));
  return pick(ents, read, names); }
// the files wanted, unpacked: text, except trips.txt, kept as bytes (Stockholm's is tens of MB: read by tripRoutes)
async function pick(ents, read, names){ const out = {};
  for(const n of names){ const en = ents.get(n); if(!en) continue;
    const lh = await read(en.off, 30), data = await read(en.off + 30 + lh.readUInt16LE(26) + lh.readUInt16LE(28), en.csize), raw = en.method === 8 ? zlib.inflateRawSync(data) : data;
    out[n] = n === 'trips.txt' ? raw : raw.toString('utf8').replace(/^﻿/, ''); }
  return out; }
// trip_id → route_id from trips.txt's bytes, line by line and only those two fields (the generic CSV reader made an
// object of every row: hundreds of MB for Stockholm, more than the small server has). Route ids are shared strings.
export function tripRoutes(buf){
  const out = new Map(), ids = new Map(); let i = 0; if(buf[0] === 0xef && buf[1] === 0xbb && buf[2] === 0xbf) i = 3;
  const line = () => { let j = buf.indexOf(10, i); if(j < 0) j = buf.length; const t = buf.toString('utf8', i, j).replace(/\r$/, ''); i = j + 1; return t; };
  const split = t => t.indexOf('"') < 0 ? t.split(',') : (t.match(/("([^"]|"")*"|[^,]*)(,|$)/g) || []).map(f => f.replace(/,$/, '').replace(/^"|"$/g, '').replace(/""/g, '"'));
  const h = split(line()).map(x => x.trim()), ti = h.indexOf('trip_id'), ri = h.indexOf('route_id'); if(ti < 0 || ri < 0) return out;
  while(i < buf.length){ const f = split(line()); const t = f[ti], r = f[ri]; if(!t || r == null) continue;
    let id = ids.get(r); if(id === undefined){ id = r; ids.set(r, r); } out.set(t, id); }
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

let LOADQ = Promise.resolve();
export class Feed {
  constructor(cfg, env){ this.cfg = cfg; this.env = env; this.vehicles = []; this.routes = new Map(); this.trips = new Map(); this.at = 0; this.error = null; this.polls = 0; }
  sub(x){ return String(x).replace(/\$([A-Z_]+)/g, (_, n) => encodeURIComponent(this.env[n] || '')); }
  headers(){ const h = {}; for(const [k, v] of Object.entries(this.cfg.headers || {})) h[k] = String(v).replace(/\$([A-Z_]+)/g, (_, n) => this.env[n] || ''); return h; }
  get enabled(){ return !this.cfg.needs || this.cfg.needs.every(n => this.env[n]); }
  async loadRoutes(){ if(!this.cfg.gtfs) return; // one feed at a time: a small server can't read many timetables at once
    const turn = LOADQ.then(() => this._loadRoutes()); LOADQ = turn.catch(() => {}); return turn; }
  async _loadRoutes(){
    try{ const f = await zipFiles(this.sub(this.cfg.gtfs), ['routes.txt', 'agency.txt', ...(this.cfg.trips === true ? ['trips.txt'] : [])], this.cfg.gtfsHeaders ? this.headers() : {});
      const ag = new Map((f['agency.txt'] ? csv(f['agency.txt']) : []).map(a => [a.agency_id, a.agency_name]));
      this.routes = new Map(csv(f['routes.txt'] || '').map(r => [r.route_id, {name:r.route_short_name || r.route_long_name || '', kind:kindOf(r.route_type),
        col:/^[0-9a-f]{6}$/i.test(r.route_color || '') ? '#' + r.route_color : null, op:ag.get(r.agency_id) || (ag.size === 1 ? [...ag.values()][0] : '') || ''}]));
      if(f['trips.txt']){ this.trips = new Map(); this.trips = tripRoutes(f['trips.txt']); } // a feed that gives only the trip: its route from the timetable
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
      this.vehicles = out; this.at = now; this.error = null; this.polls++;
      if(!this.cfg.box && out.length >= 3){ // no area given: where its vehicles have been (trimmed of the odd stray, ~2 km around)
        const la = out.map(v => v.lat).sort((a, b) => a - b), lo = out.map(v => v.lon).sort((a, b) => a - b), q = (v, f) => v[Math.min(v.length - 1, Math.floor(v.length*f))];
        const b = [q(la, 0.02) - 0.02, q(lo, 0.02) - 0.03, q(la, 0.98) + 0.02, q(lo, 0.98) + 0.03];
        this.box = this.box ? [Math.min(this.box[0], b[0]), Math.min(this.box[1], b[1]), Math.max(this.box[2], b[2]), Math.max(this.box[3], b[3])].map(x => +x.toFixed(3)) : b.map(x => +x.toFixed(3)); }
      if(this.cfg.trips === 'auto' && !this.trips.size && out.length && out.filter(v => !v.route && v.trip).length > out.length/2){ this.cfg.trips = true; this.loadRoutes(); } } // vehicles give only their trip: its route from the timetable
    catch(e){ this.error = e.message; console.warn(this.cfg.id, e.message); } }
  list(bbox){ return bbox ? this.vehicles.filter(v => v.lat >= bbox[0] && v.lat <= bbox[2] && v.lon >= bbox[1] && v.lon <= bbox[3]) : this.vehicles; }
  run(){ const d = Math.random()*60000; // first polls spread over a minute (many feeds)
    setTimeout(() => { this.poll(); setInterval(() => this.poll(), (this.cfg.every || 30)*1000); }, d); this.loadRoutes().catch(() => {}); setInterval(() => this.loadRoutes(), 24*3600000); }
}
