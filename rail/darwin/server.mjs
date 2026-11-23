// London Live: Darwin server. Reads National Rail's Darwin Push Port (Rail Data Marketplace, Kafka) and answers
//   GET /trains?bbox=minLat,minLon,maxLat,maxLon → {trains:[{id, op, opCode, dest, destCrs, headcode, live, calls:[[CRS, ms, actual]]}]}
//   GET /health → {ok, trains, messages, lastMessage}
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

const here = path.dirname(fileURLToPath(import.meta.url));
const tiplocs = JSON.parse(fs.readFileSync(path.join(here, '..', 'tiplocs.json'), 'utf8'));
const names = Object.fromEntries(JSON.parse(fs.readFileSync(path.join(here, '..', 'stations.json'), 'utf8')).map(s => [s[0], s[1]]));
const D = new Darwin(), env = process.env;
const SNAP = path.join(here, 'state.json');

// survive restarts: the trains seen so far are saved every minute
try{ const s = JSON.parse(fs.readFileSync(SNAP, 'utf8')); for(const t of s) D.trains.set(t.rid, t); console.log('restored', D.trains.size, 'trains'); }catch(e){}
setInterval(() => { D.prune(); try{ fs.writeFileSync(SNAP + '.tmp', JSON.stringify([...D.trains.values()])); fs.renameSync(SNAP + '.tmp', SNAP); }catch(e){ console.warn('save', e.message); } }, 60000);

// testing without Kafka: DARWIN_REPLAY=file of Push Port messages (one per line) is read in at the start
if(env.DARWIN_REPLAY){ try{ for(const line of fs.readFileSync(env.DARWIN_REPLAY, 'utf8').split(/\n(?=<|\{)/)) if(line.trim()) D.ingest(line); console.log('replayed', D.msgs, 'messages,', D.trains.size, 'trains'); }catch(e){ console.warn('replay', e.message); } }
async function consume(){
  if(!env.DARWIN_BOOTSTRAP){ console.warn('DARWIN_BOOTSTRAP not set: serving saved state only'); return; }
  const {Kafka, logLevel} = await import('kafkajs');
  const kafka = new Kafka({clientId:'london-live', brokers:env.DARWIN_BOOTSTRAP.split(','), ssl:true, logLevel:logLevel.WARN,
    sasl:{mechanism:env.DARWIN_SASL || 'plain', username:env.DARWIN_USERNAME, password:env.DARWIN_PASSWORD}});
  const consumer = kafka.consumer({groupId:env.DARWIN_GROUP || 'london-live', sessionTimeout:45000});
  await consumer.connect();
  await consumer.subscribe({topic:env.DARWIN_TOPIC, fromBeginning:false});
  await consumer.run({eachMessage:async ({message}) => { try{ D.ingest(message.value); }catch(e){ console.warn('message', e.message); } }});
  console.log('reading', env.DARWIN_TOPIC);
}
// the stream can drop (it does now and then): reconnect with a back-off
(async function loop(delay = 5000){ try{ await consume(); }catch(e){ console.warn('kafka', e.message, '- retrying in', delay/1000, 's'); setTimeout(() => loop(Math.min(delay*2, 300000)), delay); } })();

http.createServer((req, res) => {
  const u = new URL(req.url, 'http://x'), send = (code, body) => { res.writeHead(code, {'content-type':'application/json', 'cache-control':'no-store', 'access-control-allow-origin':'*'}); res.end(JSON.stringify(body)); };
  if(env.RELAY_TOKEN && req.headers['x-relay-token'] !== env.RELAY_TOKEN && u.pathname !== '/health') return send(403, {error:'forbidden'});
  if(u.pathname === '/health') return send(200, {ok:true, trains:D.trains.size, messages:D.msgs, lastMessage:D.last ? new Date(D.last).toISOString() : null});
  if(u.pathname === '/trains'){
    const b = (u.searchParams.get('bbox') || '').split(',').map(Number), bbox = b.length === 4 && b.every(isFinite) ? b : null;
    return send(200, {generatedAt:new Date().toISOString(), source:'darwin', trains:D.calls(tiplocs, Date.now(), bbox, names)}); }
  send(404, {error:'not found'});
}).listen(+env.PORT || 8080, () => console.log('Darwin server on port', +env.PORT || 8080));
