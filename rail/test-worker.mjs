// node rail/test-worker.mjs — tests the relay against fake Darwin boards (no key needed)
import worker from './worker.js';
import {boards} from './mock.mjs';

const now = Date.now(), B = boards(now);
let calls = 0;
globalThis.fetch = async (url, opts) => {
  calls++;
  if(!opts.headers['x-apikey']) return new Response('no key', {status:401});
  const crs = decodeURIComponent(url).match(/\/([A-Z]{3})\?/)[1];
  return B[crs] ? new Response(JSON.stringify(B[crs])) : new Response('{"trainServices":null}');
};
const env = {RDM_KEY:'test'}, ctx = {waitUntil(){}};
const get = async path => { const r = await worker.fetch(new Request('https://relay.example' + path, {headers:{origin:'https://finncoates.github.io'}}), env, ctx); return [r.status, await r.json(), r.headers]; };
const ok = (c, m) => { if(!c){ console.error('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };

let [st, h, hd] = await get('/health');
ok(st === 200 && h.configured, 'health reports configured');
ok(hd.get('access-control-allow-origin') === 'https://finncoates.github.io', 'CORS allows the site');

let [s2, b] = await get('/board?crs=clj');
ok(s2 === 200 && b.services.length > 0, `board CLJ has ${b.services.length} services`);
const sv = b.services[0];
ok(sv.calls.some(c => c.crs === 'CLJ'), 'board service includes the station itself');
ok(sv.calls.every((c, i, a) => !i || c.ms >= a[i-1].ms - 60000), 'calling points in time order');
ok(sv.calls.every(c => Math.abs(c.ms - now) < 3*3600e3), 'times converted near now');

let [s3, t] = await get('/trains?crs=VIC,CLJ,STP,LBG,WAT,LST,FST,CHX,ECR');
ok(s3 === 200 && t.trains.length > 10, `trains merged: ${t.trains.length}`);
const ids = t.trains.map(x => x.id); ok(new Set(ids).size === ids.length, 'no duplicate trains');
const moving = t.trains.filter(x => x.calls.some(c => c[2] === 1) && x.calls.some(c => c[2] === 0));
ok(moving.length > 0, `${moving.length} trains between stations (some stops passed, some to come)`);
ok(t.trains.some(x => x.reason), 'delay reasons carried through');

const before = calls; await get('/trains?crs=VIC'); ok(calls === before + 1, 'one upstream call per station');
[st] = await worker.fetch(new Request('https://relay.example/trains?crs=VIC'), {}, ctx).then(r => [r.status]);
ok(st === 503, 'missing key → clear 503');
console.log(process.exitCode ? 'SOME TESTS FAILED' : 'all relay tests passed');
