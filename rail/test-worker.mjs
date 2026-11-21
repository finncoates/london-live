// node rail/test-worker.mjs — tests the relay against fake Darwin boards (no key needed)
import worker from './worker.js';
import {boards} from './mock.mjs';

const now = Date.now(), B = boards(now);
let calls = 0;
const SIRI = `<?xml version="1.0"?><Siri xmlns="http://www.siri.org.uk/siri"><ServiceDelivery><VehicleMonitoringDelivery>
${[0,1,2].map(i => `<VehicleActivity><RecordedAtTime>2026-11-21T21:00:0${i}+00:00</RecordedAtTime><MonitoredVehicleJourney><LineRef>4${i}</LineRef><PublishedLineName>4${i}</PublishedLineName><OperatorRef>FMAN</OperatorRef><DestinationName>Piccadilly Gardens &amp; Centre</DestinationName><VehicleLocation><Longitude>-2.24${i}</Longitude><Latitude>53.48${i}</Latitude></VehicleLocation><Bearing>9${i}</Bearing><VehicleRef>BUS${i}</VehicleRef></MonitoredVehicleJourney></VehicleActivity>`).join('')}
<VehicleActivity><MonitoredVehicleJourney><LineRef>X</LineRef><VehicleRef>NOPOS</VehicleRef></MonitoredVehicleJourney></VehicleActivity>
</VehicleMonitoringDelivery></ServiceDelivery></Siri>`;
const TFE = {vehicles:[{vehicle_id:'101', service_name:'26', destination:'Clerwood', latitude:55.95, longitude:-3.19, heading:180, last_gps_fix:1763758800, vehicle_type:'bus'},
  {vehicle_id:'T1', service_name:'T50', destination:'Airport', latitude:55.946, longitude:-3.21, heading:270, last_gps_fix:1763758800, vehicle_type:'tram'}, {vehicle_id:'X', latitude:0, longitude:0}]};
const MLK = {value:[{StationLocation:'Piccadilly', AtcoCode:'9400ZZMAPIC1', Direction:'Outgoing', Line:'Bury', Dest0:'Bury', Wait0:'4', Status0:'Due', Dest1:'Altrincham', Wait1:'9', Status1:'Due'}]};
globalThis.fetch = async (url, opts = {}) => {
  calls++;
  if(String(url).includes('bus-data.dft.gov.uk')) return /api_key=bods-test/.test(url) ? new Response(SIRI) : new Response('bad key', {status:401});
  if(String(url).includes('tfe-opendata')) return new Response(JSON.stringify(TFE));
  if(String(url).includes('api.tfgm.com')) return opts.headers['Ocp-Apim-Subscription-Key'] ? new Response(JSON.stringify(MLK)) : new Response('', {status:401});
  if(!opts.headers || !opts.headers['x-apikey']) return new Response('no key', {status:401});
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

// ---- live vehicles ----
const env2 = {BODS_KEY:'bods-test', TFGM_KEY:'tfgm-test'};
const get2 = async (path, e = env2) => { const r = await worker.fetch(new Request('https://relay.example' + path, {headers:{origin:'https://finncoates.github.io'}}), e, ctx); return [r.status, await r.json()]; };
let [v1, vb] = await get2('/vehicles?src=bods&bbox=-2.30,53.45,-2.20,53.51');
ok(v1 === 200 && vb.vehicles.length === 3, `BODS: ${vb.vehicles.length} buses parsed (one without a position skipped)`);
ok(vb.vehicles[0].dest === 'Piccadilly Gardens & Centre' && vb.vehicles[0].line === '40' && vb.vehicles[0].brg === 90 && vb.vehicles[0].t > 0, 'BODS fields: line, destination (unescaped), bearing, time');
[v1] = await get2('/vehicles?src=bods&bbox=-3,53,-1,54'); ok(v1 === 400, 'BODS: too-big area refused');
[v1] = await get2('/vehicles?src=bods'); ok(v1 === 400, 'BODS: missing bbox refused');
[v1] = await get2('/vehicles?src=bods&bbox=-2.30,53.45,-2.20,53.51', {}); ok(v1 === 503, 'BODS: missing key → 503');
let [v2, ve] = await get2('/vehicles?src=tfe', {});
ok(v2 === 200 && ve.vehicles.length === 2 && ve.vehicles[1].tram === true, 'Edinburgh: buses + tram, no key needed');
let [v3, ml] = await get2('/metrolink');
ok(v3 === 200 && ml.platforms[0].trams.length === 2 && ml.platforms[0].trams[0].wait === 4, 'Metrolink: platform departures');
[v3] = await get2('/metrolink', {}); ok(v3 === 503, 'Metrolink: missing key → 503');
let [, hh] = await get2('/health'); ok(hh.bods && hh.metrolink && !hh.rail, 'health lists what is switched on');
console.log(process.exitCode ? 'SOME TESTS FAILED' : 'all relay tests passed');
