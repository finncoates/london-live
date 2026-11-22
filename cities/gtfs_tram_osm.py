# Tram lines whose timetable has no shapes (e.g. West Midlands Metro in the Bus Open Data GTFS):
# each stop-to-stop hop routed along the OpenStreetMap tram tracks. Writes a city file like manchester.json (lines + stations);
# then run gtfs_sched.py on it for timetable-placed trams.
# usage: python3 gtfs_tram_osm.py feed.zip region.osm.pbf out.json '{"route short name": ["Line name", "#colour", "tram|ferry"], ...}' "Operator" "south,west,north,east"
# (ferries are drawn pier to pier; trams follow the tracks). Then: NAMES='<same json>' gtfs_sched.py feed.zip out.json "0:tram,4:ferry"
import sys, os, re, zipfile, csv, io, json, math, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from route import Router
zf, pbf, out, MAP, op, box = sys.argv[1:7]; box = [float(x) for x in box.split(',')]; MAP = json.loads(MAP)
z = zipfile.ZipFile(zf); rd = lambda n: csv.DictReader(io.TextIOWrapper(z.open(n), 'utf-8-sig'))
routes = {r['route_id']: r['route_short_name'] for r in rd('routes.txt') if r['route_type'] in ('0', '1', '4') and r.get('route_short_name') in MAP}
trips = {t['trip_id']: routes[t['route_id']] for t in rd('trips.txt') if t['route_id'] in routes}
seq = collections.defaultdict(list)
for s in rd('stop_times.txt'):
    if s['trip_id'] in trips: seq[s['trip_id']].append((int(s['stop_sequence']), s['stop_id']))
pats = {(trips[tid],) + tuple(sid for _, sid in sorted(v)) for tid, v in seq.items()}
stops = {s['stop_id']: (float(s['stop_lat']), float(s['stop_lon']), s['stop_name']) for s in rd('stops.txt')}
clean = lambda n: re.sub(r' \((Manchester Metrolink|West Midlands Metro|Sheffield Supertram|Blackpool Tramway|Tyne and Wear Metro|Tyne and Wear Metro Station|Edinburgh Trams|SPT Subway)\)$| SPT Subway Station$| Subway$| Metro Interchange$| \(Metro\)$| Metro Station$| Subway Station$| \(Tram\)$| \(?Tram Stop\)?$| \(Tram\)$| (To|From) (City|Sheffield|Parkgate|Rotherham|Meadowhall|Halfway|Herdings|Hillsborough|Malin Bridge|Middlewood|Cathedral)( [A-Z][a-z]+)*$', '', n)
names = lambda p: {p[0]} | {clean(stops[s][2]) for s in p[1:]}
# keep only the longest patterns: a pattern whose stops are all in a longer one (either direction) adds nothing
pats = sorted(pats, key=len, reverse=True); keep = []
for p in pats:
    if not any(names(p) <= names(k) for k in keep): keep.append(p)
# every station-to-station hop any trip makes must be drawn: hops the kept patterns miss (loops closing, short branches) are added
hop = lambda a, b: (clean(stops[a][2]), clean(stops[b][2]))
have = {frozenset(hop(a, b)) for p in keep for a, b in zip(p[1:], p[2:])}
for p in pats:
    for a, b in zip(p[1:], p[2:]):
        h = frozenset(hop(a, b))
        if len(h) == 2 and h not in have: have.add(h); keep.append((p[0], a, b))
R = Router(pbf, box, kind='metro' if any(v[2:3] == ['metro'] for v in MAP.values()) else 'tram', snap_m=90); RR = None  # tram-trains also use the main-line railway
lines = []; bad = 0
for p in keep:
    pts = []; name, col, kind = (MAP[p[0]] + ['tram'])[:3]; p = p[1:]
    for a, b in zip(p, p[1:]):
        qa, qb = stops[a][:2], stops[b][:2]; seg = R.path(qa, qb) if kind in ('tram', 'tramtrain', 'metro') else None
        if not seg and kind == 'tramtrain':
            RR = RR or Router(pbf, box, kind='tramrail', snap_m=120); seg = RR.path(qa, qb)
        if not seg: seg = [qa, qb]; bad += 1; print('  off track:', stops[a][2], '->', stops[b][2], round(math.hypot((qa[0]-qb[0])*111320, (qa[1]-qb[1])*69000)), 'm')
        pts.extend(seg if not pts else seg[1:])
    lines.append({'name': name, 'kind': 'tram' if kind == 'tramtrain' else kind, 'col': col, 'pts': [[round(x, 5), round(y, 5)] for x, y in pts]})
seen = {}
for p in keep:  # one station per name (platforms in both directions), with every line calling there
    name, col, kind = (MAP[p[0]] + ['tram'])[:3]
    for sid in p[1:]:
        la, lo, nm = stops[sid]; nm = clean(nm)
        st = seen.setdefault(nm, [sid, nm, round(la, 5), round(lo, 5), []])
        kd = 'tram' if kind == 'tramtrain' else kind
        if [name, col, kd] not in st[4]: st[4].append([name, col, kd])
d = {'lines': lines, 'stations': sorted(seen.values(), key=lambda s: s[1]), 'op': op}
json.dump(d, open(out, 'w'), separators=(',', ':'), ensure_ascii=False)
print(len(keep), 'patterns kept', len(lines), 'lines', len(seen), 'stations', bad, 'hops not on track', os.path.getsize(out))
