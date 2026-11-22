# A tram network from OpenStreetMap alone (lines + stops), for systems with no open timetable (e.g. Nottingham NET):
#   python3 osm_tramnet.py region.osm.pbf out.json "Name" "#colour" "south,west,north,east"
import sys, json, osmium, collections
pbf, out, name, col, box = sys.argv[1:6]; s, w, n, e = map(float, box.split(','))
inb = lambda la, lo: s < la < n and w < lo < e
class H(osmium.SimpleHandler):
    def __init__(h): super().__init__(); h.ways = []; h.stops = {}
    def node(h, nd):
        if nd.tags.get('railway') == 'tram_stop' and inb(nd.location.lat, nd.location.lon):
            nm = nd.tags.get('name')
            if nm and nm not in h.stops: h.stops[nm] = (round(nd.location.lat, 5), round(nd.location.lon, 5))
    def way(h, wy):
        if wy.tags.get('railway') != 'tram' or wy.tags.get('service') in ('yard', 'siding', 'crossover'): return
        try: p = [(round(x.lat, 5), round(x.lon, 5)) for x in wy.nodes]
        except osmium.InvalidLocationError: return
        if any(inb(*q) for q in p): h.ways.append(p)
import os
hh = H(); hh.apply_file(pbf, locations=True, idx=os.environ.get('OSM_IDX', 'flex_mem'))
# join ways end to end into long runs (both tracks are kept: drawn as one line at map scale)
ends = collections.defaultdict(list)
for i, p in enumerate(hh.ways): ends[p[0]].append(i); ends[p[-1]].append(i)
used = set(); lines = []
for i, p in enumerate(hh.ways):
    if i in used: continue
    used.add(i); run = list(p)
    for _ in range(2):
        while True:
            nx = [j for j in ends[run[-1]] if j not in used]
            if len(ends[run[-1]]) != 2 or not nx: break
            j = nx[0]; used.add(j); q = hh.ways[j]; run += (q if q[0] == run[-1] else q[::-1])[1:]
        run.reverse()
    lines.append({'name': name, 'kind': 'tram', 'col': col, 'pts': [list(q) for q in run]})
st = [[nm, nm, la, lo, [[name, col, 'tram']]] for nm, (la, lo) in sorted(hh.stops.items())]
json.dump({'lines': lines, 'stations': st, 'op': name, 'osmOnly': True}, open(out, 'w'), separators=(',', ':'))
print(len(hh.ways), 'ways ->', len(lines), 'runs,', len(st), 'stops')
