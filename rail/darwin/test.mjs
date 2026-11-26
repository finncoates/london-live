// Tests with Push Port-shaped messages (no Kafka needed): node --test test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import {Darwin, toMs} from './darwin.mjs';

const TPL = {EUSTON:[51.528, -0.134, 'EUS'], WATFDJ:[51.663, -0.397, 'WFJ'], MKNSCEN:[52.034, -0.774, 'MKC'], CMDNJN:[51.54, -0.15, null], RUGBY:[52.379, -1.250, 'RUG']};
const NAMES = {EUS:'London Euston', WFJ:'Watford Junction', MKC:'Milton Keynes Central', RUG:'Rugby'};
const ssd = '2026-11-23';
const sched = `<?xml version="1.0"?><Pport xmlns="http://www.thalesgroup.com/rtti/PushPort/v16" xmlns:ns2="http://www.thalesgroup.com/rtti/PushPort/Schedules/v3" ts="2026-11-23T15:00:00" version="16.0"><uR updateOrigin="CIS">
<ns2:schedule rid="202611237100001" uid="W12345" trainId="1A23" ssd="${ssd}" toc="VT">
<ns2:OR tpl="EUSTON" act="TB" ptd="15:00" wtd="15:00"/>
<ns2:PP tpl="CMDNJN" wtp="15:03"/>
<ns2:IP tpl="WATFDJ" act="T " pta="15:14" ptd="15:15" wta="15:14" wtd="15:15"/>
<ns2:IP tpl="MKNSCEN" act="T " pta="15:35" ptd="15:36" wta="15:35" wtd="15:36"/>
<ns2:DT tpl="RUGBY" act="TF" pta="15:55" wta="15:55"/>
</ns2:schedule></uR></Pport>`;
const ts = `<Pport xmlns="http://www.thalesgroup.com/rtti/PushPort/v16" xmlns:ns5="http://www.thalesgroup.com/rtti/PushPort/Forecasts/v3" ts="2026-11-23T15:20:00" version="16.0"><uR updateOrigin="TD">
<TS rid="202611237100001" uid="W12345" ssd="${ssd}">
<ns5:Location tpl="EUSTON" wtd="15:00" ptd="15:00"><ns5:dep at="15:01" src="TD"/></ns5:Location>
<ns5:Location tpl="CMDNJN" wtp="15:03"><ns5:pass at="15:04"/></ns5:Location>
<ns5:Location tpl="WATFDJ" wta="15:14" wtd="15:15" pta="15:14" ptd="15:15"><ns5:arr at="15:16"/><ns5:dep at="15:17"/><ns5:plat conf="true">9</ns5:plat></ns5:Location>
<ns5:Location tpl="MKNSCEN" wta="15:35" wtd="15:36" pta="15:35" ptd="15:36"><ns5:arr et="15:37"/><ns5:dep et="15:38"/></ns5:Location>
</TS></uR></Pport>`;

test('times are UK local on the schedule day', () => {
  assert.equal(new Date(toMs('15:00', ssd)).toISOString(), '2026-11-23T15:00:00.000Z'); // GMT in November
  assert.equal(new Date(toMs('15:00', '2026-07-01')).toISOString(), '2026-07-01T14:00:00.000Z'); // BST in summer
  const late = toMs('23:50', ssd), after = toMs('00:10', ssd, late); assert.equal(after - late, 20*60e3); // past midnight
});
test('a schedule, then running updates → stations with actual and expected times', () => {
  const D = new Darwin(); D.ingest(sched); D.ingest(ts);
  const now = Date.parse('2026-11-23T15:25:00Z'), [t] = D.calls(TPL, now, null, NAMES);
  assert.equal(t.opCode, 'VT'); assert.equal(t.op, 'Avanti West Coast'); assert.equal(t.dest, 'Rugby'); assert.equal(t.headcode, '1A23'); assert.equal(t.live, true);
  assert.deepEqual(t.calls.map(c => c[0]), ['EUS', 'WFJ', 'MKC', 'RUG']); // the passing point (no CRS) left out
  assert.equal(new Date(t.calls[1][1]).toISOString(), '2026-11-23T15:17:00.000Z'); assert.equal(t.calls[1][2], 1); // departed Watford at 15:17 (actual)
  assert.equal(new Date(t.calls[2][1]).toISOString(), '2026-11-23T15:38:00.000Z'); assert.equal(t.calls[2][2], 0); // expected at MK
  assert.equal(t.calls[1][3], '9'); assert.equal(t.calls[2][3], undefined); // Watford: platform 9; MK: not known
});
test('platforms: plain, as JSON, and kept from the public', () => {
  const D = new Darwin(); D.ingest(sched);
  D.ingest(JSON.stringify({bytes:JSON.stringify({ts:'x', uR:{TS:{rid:'202611237100001', uid:'W12345', ssd, Location:[{tpl:'EUSTON', wtd:'15:00', ptd:'15:00', dep:{at:'15:01'}, plat:{'':'14', conf:'true'}}, {tpl:'MKNSCEN', wta:'15:35', wtd:'15:36', arr:{et:'15:37'}, plat:{'':'4', platsup:'true'}}]}}})}));
  const [t] = D.calls(TPL, Date.parse('2026-11-23T15:25:00Z'), null, NAMES);
  assert.equal(t.calls[0][3], '14'); assert.equal(t.calls.find(c => c[0] === 'MKC')[3], undefined);
});
test('a box around where the train is now', () => {
  const D = new Darwin(); D.ingest(sched); D.ingest(ts); const now = Date.parse('2026-11-23T15:25:00Z');
  assert.equal(D.calls(TPL, now, [51.6, -0.9, 52.1, -0.3]).length, 1); // between Watford and MK: in
  assert.equal(D.calls(TPL, now, [53, -3, 54, -2]).length, 0); // Manchester: out
});
test('RDM JSON wrapping, finished and cancelled trains', () => {
  const D = new Darwin(); D.ingest(JSON.stringify({bytes:sched})); assert.equal(D.trains.size, 1);
  assert.equal(D.calls(TPL, Date.parse('2026-11-23T18:00:00Z')).length, 0); // long finished
  D.ingest(sched.replace('toc="VT"', 'toc="VT" isCancelled="true"')); assert.equal(D.calls(TPL, Date.parse('2026-11-23T15:10:00Z')).length, 0);
});
test('updates for a train whose schedule we never saw still place it', () => {
  const D = new Darwin(); D.ingest(ts); const [t] = D.calls(TPL, Date.parse('2026-11-23T15:25:00Z'), null, NAMES);
  assert.ok(t); assert.deepEqual(t.calls.map(c => c[0]), ['EUS', 'WFJ', 'MKC']);
});

// ---------- live ferries (AIS) and live feeds ----------
import {Ais} from './ais.mjs';
import {csv, kindOf} from './rt.mjs';
test('AIS: a passenger ship shows once its type is known, cargo ships never', () => {
  const a = new Ais('/nonexistent/ais.json'), md = (mmsi, name) => ({MMSI:mmsi, ShipName:name, latitude:50.79, longitude:-1.10});
  const pos = (mmsi, name) => ({MessageType:'PositionReport', MetaData:md(mmsi, name), Message:{PositionReport:{Cog:181.4, Sog:14.2, TrueHeading:180}}});
  a.ingest(pos(235000001, 'ST CLARE ')); assert.equal(a.list(null).length, 0); // type not known yet
  a.ingest({MessageType:'ShipStaticData', MetaData:md(235000001, 'ST CLARE'), Message:{ShipStaticData:{Type:60, Destination:'FISHBOURNE'}}});
  a.ingest({MessageType:'ShipStaticData', MetaData:md(235000002, 'BOX SHIP'), Message:{ShipStaticData:{Type:70}}});
  a.ingest(pos(235000001, 'ST CLARE ')); a.ingest(pos(235000002, 'BOX SHIP'));
  const l = a.list([50, -2, 51, 0]); assert.equal(l.length, 1); assert.equal(l[0].name, 'ST CLARE'); assert.equal(l[0].hdg, 180); assert.equal(l[0].cog, 181);
  assert.equal(a.list([52, -2, 53, 0]).length, 0); // outside the box
});
test('GTFS: quoted CSV and route kinds', () => {
  const r = csv('﻿route_id,route_short_name,route_type\r\n1,"Line ""A"", east",0\r\n2,M1,401\n3,,3\n');
  assert.equal(r.length, 3); assert.equal(r[0].route_short_name, 'Line "A", east');
  assert.deepEqual(['0', '1', '2', '3', '4', '401', '109', '900', '1200', '700'].map(kindOf), ['tram', 'metro', 'train', 'bus', 'ferry', 'metro', 'train', 'tram', 'ferry', 'bus']);
});

test('RDM JSON topic: the Pport as JSON inside "bytes"', () => {
  const D = new Darwin();
  const inner = {ts:'2026-11-23T20:38:54Z', version:'18.0', uR:{updateOrigin:'Trust', TS:{rid:'202611236702128', uid:'C02128', ssd:'2026-11-23', Location:{tpl:'LEEDSWJ', wtp:'20:17:30', pass:{at:'20:38'}}}}};
  D.ingest(Buffer.from(JSON.stringify({destination:{name:'x'}, messageType:'bytes', bytes:JSON.stringify(inner)})));
  assert.equal(D.msgs, 1); assert.equal(D.trains.size, 1); assert.equal(D.trains.get('202611236702128').locs[0].at, '20:38'); });
test('how late it is at its next calling station, against the public timetable', () => {
  const D = new Darwin(); D.ingest(sched); D.ingest(ts);
  const [t] = D.calls(TPL, Date.parse('2026-11-23T15:25:00Z'), null, NAMES); assert.equal(t.late, 2); // Milton Keynes: expected 15:38, booked 15:36
  const [u] = D.calls(TPL, Date.parse('2026-11-23T15:05:00Z'), null, NAMES); assert.equal(u.late, 2); // Watford next: 15:17 for 15:15
  const D2 = new Darwin(); D2.ingest(sched); const [v] = D2.calls(TPL, Date.parse('2026-11-23T15:05:00Z'), null, NAMES); assert.equal(v.late, null); // no running reports: not known
});
