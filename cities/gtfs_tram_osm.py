# Tram lines whose timetable has no shapes (e.g. West Midlands Metro in the Bus Open Data GTFS):
# each stop-to-stop hop routed along the OpenStreetMap tram tracks. Writes a city file like manchester.json (lines + stations);
# then run gtfs_sched.py on it for timetable-placed trams.
# usage: ONLY='^Metro$' python3 gtfs_tram_osm.py feed.zip region.osm.pbf out.json "Line name" "#colour" "Operator" "south,west,north,east"
import sys, os, re, zipfile, csv, io, json, math, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from route import Router
zf, pbf, out, name, col, op, box = sys.argv[1:8]; box = [float(x) for x in box.split(',')]
z = zipfile.ZipFile(zf); rd = lambda n: csv.DictReader(io.TextIOWrapper(z.open(n), 'utf-8-sig'))
ONLY = re.compile(os.environ.get('ONLY', '.'))
routes = {r['route_id'] for r in rd('routes.txt') if r['route_type'] == '0' and ONLY.search(r.get('route_short_name') or r.get('route_long_name') or '')}
trips = {t['trip_id'] for t in rd('trips.txt') if t['route_id'] in routes}
seq = collections.defaultdict(list)
for s in rd('stop_times.txt'):
    if s['trip_id'] in trips: seq[s['trip_id']].append((int(s['stop_sequence']), s['stop_id']))
pats = {tuple(sid for _, sid in sorted(v)) for v in seq.values()}
stops = {s['stop_id']: (float(s['stop_lat']), float(s['stop_lon']), s['stop_name']) for s in rd('stops.txt')}
clean = lambda n: re.sub(r' \((Manchester Metrolink|West Midlands Metro)\)$| \(?Tram Stop\)?$', '', n)
names = lambda p: {clean(stops[s][2]) for s in p}
# keep only the longest patterns: a pattern whose stops are all in a longer one (either direction) adds nothing
pats = sorted(pats, key=len, reverse=True); keep = []
for p in pats:
    if not any(names(p) <= names(k) for k in keep): keep.append(p)
R = Router(pbf, box, kind='tram', snap_m=90)
lines = []; bad = 0
for p in keep:
    pts = []
    for a, b in zip(p, p[1:]):
        qa, qb = stops[a][:2], stops[b][:2]; seg = R.path(qa, qb)
        if not seg: seg = [qa, qb]; bad += 1; print('  off track:', stops[a][2], '->', stops[b][2], round(math.hypot((qa[0]-qb[0])*111320, (qa[1]-qb[1])*69000)), 'm')
        pts.extend(seg if not pts else seg[1:])
    lines.append({'name': name, 'kind': 'tram', 'col': col, 'pts': [[round(x, 5), round(y, 5)] for x, y in pts]})
used = {sid for p in keep for sid in p}; seen = {}
for sid in used:  # one station per name (platforms in both directions)
    la, lo, nm = stops[sid]; nm = clean(nm)
    if nm not in seen: seen[nm] = [sid, nm, round(la, 5), round(lo, 5), [[name, col, 'tram']]]
d = {'lines': lines, 'stations': sorted(seen.values(), key=lambda s: s[1]), 'op': op}
json.dump(d, open(out, 'w'), separators=(',', ':'), ensure_ascii=False)
print(len(keep), 'patterns kept', len(lines), 'lines', len(seen), 'stations', bad, 'hops not on track', os.path.getsize(out))
