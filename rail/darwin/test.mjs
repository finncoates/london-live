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
<ns5:Location tpl="WATFDJ" wta="15:14" wtd="15:15" pta="15:14" ptd="15:15"><ns5:arr at="15:16"/><ns5:dep at="15:17"/></ns5:Location>
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
