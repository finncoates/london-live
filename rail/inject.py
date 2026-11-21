#!/usr/bin/env python3
"""Copy rail/client.part.js into both pages (between markers) and apply the small engine changes
National Rail needs. Safe to run again: the client block is replaced, engine edits are skipped once done.
Usage: python3 rail/inject.py [index.html journey/index.html ...]"""
import sys, os
here = os.path.dirname(os.path.abspath(__file__))
client = open(os.path.join(here, 'client.part.js')).read().rstrip() + '\n'
START, END = '// <rail-client>\n', '// </rail-client>\n'

EDITS = [  # (old, new) — engine changes, applied once
  ("const DWELL = {tube:25, dlr:20, elizabeth:40, overground:35, tram:20, bus:15};",
   "const DWELL = {tube:25, dlr:20, elizabeth:40, overground:35, tram:20, bus:15, rail:45};"),
  ("const SPEED = {tube:12, dlr:10, elizabeth:17, overground:13, tram:7, bus:6};",
   "const SPEED = {tube:12, dlr:10, elizabeth:17, overground:13, tram:7, bus:6, rail:22};"),
  ("    const ids = ACTIVE.filter(l => l.mode !== 'bus').map(l => l.id);",            # TfL status: TfL lines only
   "    const ids = ACTIVE.filter(l => l.mode !== 'bus' && !l.rail).map(l => l.id);"),
  ("  const ids = ACTIVE.filter(l => shown(l) && l.layer).map(l=>l.id);",              # TfL arrivals: TfL lines only
   "  const ids = ACTIVE.filter(l => shown(l) && l.layer && !l.rail).map(l=>l.id);"),
  ("    if(t.anon || t0 - t.seen > REFRESH*2.5){ trains.delete(k); gone.push(t); }",  # rail trains are managed by refreshRail
   "    if(t.rail) continue;\n    if(t.anon || t0 - t.seen > REFRESH*2.5){ trains.delete(k); gone.push(t); }"),
  ("  for(const l of ACTIVE){ l.count = 0; if(!failed.has(l.id)) store.set('segt:'+l.id, l.seg, 30*864e5); }\n  for(const t of trains.values()) if(t0 - t.seen < REFRESH*1.5) BY[t.line].count++;",
   "  for(const l of ACTIVE){ if(l.rail) continue; l.count = 0; if(!failed.has(l.id)) store.set('segt:'+l.id, l.seg, 30*864e5); }\n  for(const t of trains.values()) if(!t.rail && t0 - t.seen < REFRESH*1.5) BY[t.line].count++;"),
  ("  if(!prev || !l.stops[prev]) return snapAt(l, next);",                           # not yet at its first stop
   "  if(!prev || prev === next || !l.stops[prev]) return snapAt(l, next);"),
  ("  let f = Math.min(1, Math.max(0, 1 - remain/segTime(l, prev, next)));",           # rail: real timetable between stops
   "  const segT = t.rail && t.ahead ? (() => { const i = t.ahead.findIndex(a => a[0] === next && a[1] === arr); return i > 0 ? Math.max(30, (arr - t.ahead[i-1][1])/1000 - DWELL.rail/2) : segTime(l, prev, next); })() : segTime(l, prev, next);\n  let f = Math.min(1, Math.max(0, 1 - remain/segT));"),
  ("    const l = BY[t.line]; if(!l.on || !shown(l) || wall - t.seen > REFRESH*1.5) continue;",
   "    const l = BY[t.line]; if(!l.on || !shown(l) || wall - t.seen > (t.rail ? 150000 : REFRESH*1.5)) continue;"),
]
ANCHORS = ['// ====================================================================================\n// Journey app',
           '// ====================================================================================\n// Live trains page']

for path in sys.argv[1:] or ['index.html', 'journey/index.html']:
    h = open(path).read()
    for old, new in EDITS:
        if new in h: continue
        assert h.count(old) == 1, (path, old[:70], h.count(old))
        h = h.replace(old, new)
    if START in h:
        i, j = h.index(START), h.index(END) + len(END)
        h = h[:i] + START + client + END + h[j:]
    else:
        a = next(a for a in ANCHORS if a in h)
        h = h.replace(a, START + client + END + '\n' + a, 1)
    open(path, 'w').write(h)
    print('ok', path)
