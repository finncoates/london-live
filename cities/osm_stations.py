# A country's railway stations from OpenStreetMap, for countries whose rail is drawn from OSM but that have no one
# national timetable to take stations from (Poland, Germany, Austria, Italy, Spain): railway=station (and halts),
# not metro, light rail, funicular or heritage ones.
#   python -I cities/osm_stations.py <cc> country.osm.pbf  -> cities/<cc>-stations.json  [[id, name, lat, lon], ...]
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace')
import sys, os, json, osmium
HERE = os.path.dirname(os.path.abspath(__file__)); cc, pbf = sys.argv[1], sys.argv[2]
SKIP = {'subway', 'light_rail', 'monorail', 'funicular', 'tram', 'miniature'}
class H(osmium.SimpleHandler):
    def __init__(h): super().__init__(); h.out = {}
    def take(h, kind, oid, t, lat, lon):
        if t.get('railway') not in ('station', 'halt') or t.get('station') in SKIP or t.get('usage') in ('tourism', 'heritage') or t.get('railway:preserved') == 'yes' or not t.get('name'): return
        if t.get('subway') == 'yes' or t.get('light_rail') == 'yes' and t.get('train') != 'yes': return
        h.out[kind + str(oid)] = [kind + str(oid), t.get('name'), round(lat, 5), round(lon, 5)]
    def node(h, n): h.take('n', n.id, n.tags, n.location.lat, n.location.lon) if n.location.valid() else None
    def area(h, a):
        try:
            pts = [(n.lat, n.lon) for r in a.outer_rings() for n in r]
            if pts: h.take('a', a.orig_id(), a.tags, sum(p[0] for p in pts)/len(pts), sum(p[1] for p in pts)/len(pts))
        except Exception: pass
h = H(); h.apply_file(pbf, locations=True, idx=os.environ.get('OSM_IDX', 'flex_mem'))
# one per name within 300 m (a station drawn both as a point and an area)
seen, out = [], []
for s in sorted(h.out.values(), key=lambda s: s[0][0] != 'n'):
    if any(o[1] == s[1] and abs(o[2] - s[2]) < 0.003 and abs(o[3] - s[3]) < 0.004 for o in seen): continue
    seen.append(s); out.append(s)
out.sort(key=lambda s: s[1])
json.dump(out, open(os.path.join(HERE, cc + '-stations.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print(cc, len(out), 'stations')
