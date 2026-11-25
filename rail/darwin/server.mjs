// London Live server (one small always-on machine, e.g. Oracle Cloud's free tier). Each part switches on when its
// settings are present (/etc/london-live-darwin.env):
//   Darwin (DARWIN_*): National Rail's Push Port →  GET /trains?bbox=minLat,minLon,maxLat,maxLon
//       → {trains:[{id, op, opCode, dest, destCrs, headcode, live, calls:[[CRS, ms, actual]]}]}
//   Ferries (AISSTREAM_KEY): ships' AIS positions  →  GET /ferries?bbox=… → {ships:[{mmsi, name, lat, lon, sog, cog, hdg, at}]}
//   Live feeds (feeds.json; some need a key)       →  GET /rt?feed=id&bbox=… → {vehicles:[{id, lat, lon, bearing, line, kind, col, op, at}]}
//   GET /health → what's running
// in the same shape as the relay's /trains, so the map places every train from its real running (actual times at
// the stations it has passed, expected times ahead). The relay fetches from here (set DARWIN_URL on the relay), so this
// server needs no HTTPS or domain name of its own.
//
// Settings (environment): DARWIN_BOOTSTRAP (Kafka bootstrap server), DARWIN_USERNAME, DARWIN_PASSWORD, DARWIN_TOPIC,
// DARWIN_GROUP (consumer group id, from the Rail Data Marketplace subscription), PORT (default 8080),
// RELAY_TOKEN (optional: a shared secret the relay sends, so only it can ask). See SETUP.md.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Darwin} from './darwin.mjs';
import {Ais} from './ais.mjs';
import {Feed} from './rt.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const tiplocs = JSON.parse(fs.readFileSync(path.join(here, '..', 'tiplocs.json'), 'utf8'));
const names = Object.fromEntries(JSON.parse(fs.readFileSync(path.join(here, '..', 'stations.json'), 'utf8')).map(s => [s[0], s[1]]));
const D = new Darwin(), env = process.env;
const SNAP = path.join(here, 'state.json');

// survive restarts: the trains seen so far are saved every minute
try{ const s = JSON.parse(fs.readFileSync(SNAP, 'utf8')); for(const t of s) D.trains.set(t.rid, t); console.log('restored', D.trains.size, 'trains'); }catch(e){}
// a fresh start knows only fragments of the trains already running (their timetables come when they set off): until
// it has seen a couple of hours, the map keeps using station boards. A restart with saved state is ready at once.
const READY_AT = Date.now() + ([...D.trains.values()].filter(t => !t.partial).length > 500 ? 0 : 2*3600e3);
setInterval(() => { D.prune(); try{ fs.writeFileSync(SNAP + '.tmp', JSON.stringify([...D.trains.values()])); fs.renameSync(SNAP + '.tmp', SNAP); }catch(e){ console.warn('save', e.message); } }, 60000);

// testing without Kafka: DARWIN_REPLAY=file of Push Port messages (one per line) is read in at the start
if(env.DARWIN_REPLAY){ try{ for(const line of fs.readFileSync(env.DARWIN_REPLAY, 'utf8').split(/\n(?=<|\{)/)) if(line.trim()) D.ingest(line); console.log('replayed', D.msgs, 'messages,', D.trains.size, 'trains'); }catch(e){ console.warn('replay', e.message); } }
// ferries: the seas around the UK and Ireland, the Channel, North Sea and Baltic, the Mediterranean (and the Thames)
const AIS = new Ais(path.join(here, 'ais.json'));
if(env.AISSTREAM_KEY) AIS.run(env.AISSTREAM_KEY, JSON.parse(env.AIS_BOXES || '[[[49.0,-11.0],[61.5,2.5]],[[43.0,-10.0],[49.0,10.0]],[[49.0,2.5],[66.0,31.0]],[[30.0,-6.0],[46.0,37.0]]]'));
// live vehicle feeds
const FEEDS = new Map();
try{ for(const f of JSON.parse(fs.readFileSync(path.join(here, 'feeds.json'), 'utf8')).feeds.sort((a, b) => (b.trips === true) - (a.trips === true))){ /* (feeds whose vehicles can't be named without their timetable load first: Sweden's) */ const F = new Feed(f, env); if(F.enabled && !(env.FEEDS_OFF || '').split(',').includes(f.id)){ FEEDS.set(f.id, F); F.run(); } } }
catch(e){ console.warn('feeds', e.message); }
// each feed's area as learnt from its vehicles is kept across restarts (feed-boxes.json), so the map finds it straight away
const BOXF = path.join(here, 'feed-boxes.json');
try{ const bx = JSON.parse(fs.readFileSync(BOXF, 'utf8')); for(const [id, F] of FEEDS) if(!F.cfg.box && bx[id]) F.box = bx[id]; }catch(e){}
setInterval(() => { try{ fs.writeFileSync(BOXF, JSON.stringify(Object.fromEntries([...FEEDS].filter(([, F]) => F.box).map(([id, F]) => [id, F.box])))); }catch(e){} }, 300000);
console.log('feeds on:', [...FEEDS.keys()].join(', ') || 'none', '· ferries:', env.AISSTREAM_KEY ? 'on' : 'off (no AISSTREAM_KEY)');
async function consume(){
  if(!env.DARWIN_BOOTSTRAP){ console.warn('DARWIN_BOOTSTRAP not set: Darwin off (serving saved state only)'); return; }
  const {Kafka, logLevel} = await import('kafkajs');
  // small machines are slow to open TLS connections: kafkajs's 1 s default times out on some brokers
  const kafka = new Kafka({clientId:'london-live', brokers:env.DARWIN_BOOTSTRAP.split(','), ssl:true, logLevel:logLevel.WARN,
    connectionTimeout:15000, authenticationTimeout:15000, requestTimeout:60000, retry:{retries:10, initialRetryTime:1000},
    sasl:{mechanism:(env.DARWIN_SASL || 'plain').toLowerCase(), username:env.DARWIN_USERNAME, password:env.DARWIN_PASSWORD}});
  const consumer = kafka.consumer({groupId:env.DARWIN_GROUP || 'london-live', sessionTimeout:45000});
  consumer.on(consumer.events.GROUP_JOIN, e => console.log('darwin: joined the group,', Object.values(e.payload.memberAssignment || {}).flat().length, 'partitions'));
  consumer.on(consumer.events.CRASH, e => console.warn('darwin: consumer crashed:', e.payload.error && e.payload.error.message, e.payload.restart ? '(restarting)' : ''));
  await consumer.connect();
  await consumer.subscribe({topic:env.DARWIN_TOPIC, fromBeginning:false});
  await consumer.run({eachMessage:async ({message}) => { D.raw = (D.raw || 0) + 1;
    if(D.raw === 1){ const t = String(message.value || '').slice(0, 300); console.log('darwin: first message', (message.value || '').length, 'bytes:', t.replace(/\s+/g, ' ').slice(0, 200)); }
    try{ D.ingest(message.value); }catch(e){ console.warn('message', e.message); } }});
  console.log('reading', env.DARWIN_TOPIC);
  // watchdog: Darwin sends several messages a second, so 3 minutes of silence means a stuck connection: start again
  const since = D.raw || 0, started = Date.now(); let seen = since, seenAt = started;
  const dog = setInterval(async () => { if((D.raw || 0) !== seen){ seen = D.raw || 0; seenAt = Date.now(); } const quiet = Date.now() - seenAt;
    if(quiet < 180000) return; clearInterval(dog); console.warn('darwin: nothing for 3 minutes, reconnecting');
    try{ await consumer.disconnect(); }catch(e){} loop(); }, 30000);
}
// the stream can drop (it does now and then): reconnect with a back-off
async function loop(delay = 5000){ try{ await consume(); }catch(e){ console.warn('kafka', e.message, '- retrying in', delay/1000, 's'); setTimeout(() => loop(Math.min(delay*2, 300000)), delay); } }
loop();

http.createServer((req, res) => {
  const u = new URL(req.url, 'http://x'), send = (code, body) => { res.writeHead(code, {'content-type':'application/json', 'cache-control':'no-store', 'access-control-allow-origin':'*'}); res.end(JSON.stringify(body)); };
  if(env.RELAY_TOKEN && req.headers['x-relay-token'] !== env.RELAY_TOKEN && u.pathname !== '/health') return send(403, {error:'forbidden'});
  const bbox = (b => b.length === 4 && b.every(isFinite) ? b : null)((u.searchParams.get('bbox') || '').split(',').map(Number));
  if(u.pathname === '/health') return send(200, {ok:true, trains:D.trains.size, messages:D.msgs, lastMessage:D.last ? new Date(D.last).toISOString() : null, received:D.raw || 0, darwin:!!env.DARWIN_BOOTSTRAP,
    ferries:{on:!!env.AISSTREAM_KEY, status:AIS.status, ships:AIS.list(null).length, messages:AIS.msgs},
    feeds:Object.fromEntries([...FEEDS].map(([id, F]) => [id, {name:F.cfg.name, cc:F.cfg.cc || null, box:F.cfg.box || F.box || null, tt:F.cfg.tt || null, ttModes:F.cfg.ttModes || null, vehicles:F.vehicles.length, routes:F.routes.size, trips:F.trips.size, timetable:F.routesAt ? new Date(F.routesAt).toISOString() : F.routesLoading || null, timetableError:F.routesErr || null, at:F.at ? new Date(F.at).toISOString() : null, error:F.error}]))});
  if(u.pathname === '/ferries') return send(200, {at:Date.now(), ships:AIS.list(bbox)});
  if(u.pathname === '/rt'){ const F = FEEDS.get(u.searchParams.get('feed')); if(!F) return send(404, {error:'no such feed (on)'}); F.wanted = Date.now(); if(Date.now() - (F.at || 0) > 45000) F.poll(); /* (someone's looking: polled at once if its data is old, then every 30 s) */ return send(200, {feed:F.cfg.id, name:F.cfg.name, at:F.at, error:F.error, vehicles:F.list(bbox)}); }
  if(u.pathname === '/trains'){
    if(Date.now() < READY_AT) return send(200, {generatedAt:new Date().toISOString(), source:'darwin', warming:true, readyAt:new Date(READY_AT).toISOString(), trains:[]});
    return send(200, {generatedAt:new Date().toISOString(), source:'darwin', trains:D.calls(tiplocs, Date.now(), bbox, names).filter(t => t.op || t.dest)}); }
  send(404, {error:'not found'});
}).listen(+env.PORT || 8080, () => console.log('London Live server on port', +env.PORT || 8080));
