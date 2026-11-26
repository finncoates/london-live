# Metro lines a timetable lacks (Madrid's Line 3 and Ramal: not in its last open feed), from OpenStreetMap's route
# relations, added to a city file: each direction's track joined end to end, its stations, in the given colours.
#   python -I cities/osm_metro_lines.py region.osm.pbf cities/x.json "Metro de Madrid" '{"L3": ["3", "#FFD000"], "R": ["R", "#7F8C9E"]}' [names]
#   (OSM ref: [line name in the file, colour]; names: every station renamed after the OSM metro station within 150 m, accents and all)
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace')
import sys, json, math, osmium
pbf, out, network, want = sys.argv[1], sys.argv[2], sys.argv[3], json.loads(sys.argv[4])
rels = {}  # ref -> [(way ids in order, [stop node ids], name)]
for r in osmium.FileProcessor(pbf, osmium.osm.RELATION).with_filter(osmium.filter.KeyFilter('route')):
    t = r.tags
    if t.get('route') != 'subway' or network.lower() not in (t.get('network', '') + ' ' + t.get('operator', '')).lower(): continue
    ref = t.get('ref', '')
    if ref not in want: continue
    ways = [m.ref for m in r.members if m.type == 'w' and m.role in ('', 'forward', 'backward')]
    stops = [m.ref for m in r.members if m.type == 'n' and m.role.startswith('stop')]
    rels.setdefault(ref, []).append((ways, stops, t.get('name', '')))
need_w = {w for v in rels.values() for ws, _, _ in v for w in ws}; wn = {}
for w in osmium.FileProcessor(pbf, osmium.osm.WAY).with_filter(osmium.filter.IdFilter(need_w)): wn[w.id] = [n.ref for n in w.nodes]
need_n = {n for v in wn.values() for n in v} | {s for v in rels.values() for _, ss, _ in v for s in ss}; loc, nm = {}, {}
for n in osmium.FileProcessor(pbf, osmium.osm.NODE).with_filter(osmium.filter.IdFilter(need_n)):
    if n.location.valid(): loc[n.id] = (round(n.location.lat, 6), round(n.location.lon, 6)); nm[n.id] = n.tags.get('name', '')
def chain(ws):  # the ways joined end to end, each turned the way that continues the last
    pts = []
    for w in ws:
        ns = wn.get(w)
        if not ns: continue
        if pts and ns[-1] == pts[-1]: ns = ns[::-1]
        elif pts and ns[0] != pts[-1] and ns[-1] != pts[-1] and len(pts) == len(wn.get(ws[0], [])) and (ns[0] == pts[0] or ns[-1] == pts[0]): pts = pts[::-1]; ns = ns if ns[0] == pts[-1] else ns[::-1]
        pts += ns[1:] if pts and ns[0] == pts[-1] else ns
    return [list(loc[n]) for n in pts if n in loc]
d = json.load(open(out, encoding='utf-8')); add = 0
for ref, (lname, col) in want.items():
    for ws, ss, name in rels.get(ref, [])[:2]:  # (both directions: drawn as one where they share the tunnel)
        pts = chain(ws)
        if len(pts) > 2: d['lines'].append({'name': lname, 'kind': 'metro', 'col': col, 'pts': pts}); add += 1
    seen = set()
    for ws, ss, name in rels.get(ref, []):
        for s in ss:
            if s in loc and nm.get(s) and nm[s] not in seen:
                seen.add(nm[s]); la, lo = loc[s]
                hit = next((st for st in d['stations'] if st[1].lower() == nm[s].lower() or math.hypot((st[2] - la)*111, (st[3] - lo)*85) < 0.15), None)
                if hit: hit[4].append([lname, col, 'metro']) if not any(x[0] == lname for x in hit[4]) else None
                else: d['stations'].append([f'osm{s}', nm[s], la, lo, [[lname, col, 'metro']]])
if len(sys.argv) > 5 and sys.argv[5] == 'names':  # the stations' own names, from OSM's metro stations nearby
    OS = []
    for n in osmium.FileProcessor(pbf, osmium.osm.NODE).with_filter(osmium.filter.KeyFilter('railway', 'public_transport')):
        t = n.tags
        if n.location.valid() and t.get('name') and (t.get('station') == 'subway' or t.get('subway') == 'yes') and (t.get('railway') == 'station' or t.get('public_transport') == 'station'): OS.append((n.location.lat, n.location.lon, t['name']))
    ren = 0
    for st in d['stations']:
        best = min(OS, key=lambda o: math.hypot((o[0] - st[2])*111, (o[1] - st[3])*85), default=None)
        if best and math.hypot((best[0] - st[2])*111, (best[1] - st[3])*85) < 0.15 and best[2] != st[1]: st[1] = best[2]; ren += 1
    print(len(OS), 'OSM metro stations;', ren, 'renamed')
print({k: len(v) for k, v in rels.items()}, add, 'lines added;', len(d['stations']), 'stations')
json.dump(d, open(out, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
