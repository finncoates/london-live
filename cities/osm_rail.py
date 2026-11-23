# A country's passenger railway from OpenStreetMap (railway=rail, main and branch lines; no sidings, yards, heritage or
# freight-only lines), one line per pair of parallel tracks, as Britain's (osm_nr.py) — for countries whose timetables
# have no track shapes (Belgium, Switzerland…).
#   python -I cities/osm_rail.py <cc> country.osm.pbf "south,west,north,east"  -> cities/.build/rail/<cc>.json
# then rail_tiles.py rebuilds the shared tiles.
import sys, os, json, math, subprocess, osmium
HERE = os.path.dirname(os.path.abspath(__file__))
cc, pbf, box = sys.argv[1], sys.argv[2], [float(x) for x in sys.argv[3].split(',')]
class H(osmium.SimpleHandler):
    def __init__(h): super().__init__(); h.ways = []
    def way(h, w):
        t = w.tags
        if t.get('railway') != 'rail' or t.get('service') or t.get('usage') in ('industrial', 'military', 'tourism', 'test', 'freight') or t.get('railway:preserved') == 'yes': return
        if t.get('usage') not in ('main', 'branch', None): return
        try: p = [(round(n.lat, 5), round(n.lon, 5)) for n in w.nodes]
        except osmium.InvalidLocationError: return
        if not any(box[0] <= q[0] <= box[2] and box[1] <= q[1] <= box[3] for q in p): return
        h.ways.append(p)
hh = H(); hh.apply_file(pbf, locations=True, idx=os.environ.get('OSM_IDX', 'flex_mem'))
k = math.cos(math.radians((box[0] + box[2])/2)); C = 25
def cells(a, b):
    L = math.hypot((b[0]-a[0])*111320, (b[1]-a[1])*111320*k); n = max(1, int(L // 20)); ang = int((math.atan2(b[0]-a[0], (b[1]-a[1])*k) % math.pi)/(math.pi/8)) % 8
    return [(round((a[0] + (b[0]-a[0])*t/n)*111320/C), round((a[1] + (b[1]-a[1])*t/n)*111320*k/C), ang) for t in range(n + 1)]
seen = set(); keep = []
for p in sorted(hh.ways, key=len, reverse=True):  # keep a way only where no kept track runs alongside it (25 m, same way)
    run = []; mine = set()
    for a, b in zip(p, p[1:]):
        cs = cells(a, b)
        if all(any((c[0]+i, c[1]+j, (c[2]+d) % 8) in seen for i in (-1, 0, 1) for j in (-1, 0, 1) for d in (-1, 0, 1)) for c in cs):
            if len(run) > 1: keep.append(run)
            run = []; continue
        mine.update(cs); run = run or [a]; run.append(b)
    if len(run) > 1: keep.append(run)
    seen |= mine
os.makedirs(os.path.join(HERE, '.build', 'rail'), exist_ok=True)
json.dump([[[a, b] for a, b in p] for p in keep], open(os.path.join(HERE, '.build', 'rail', cc + '.json'), 'w'), separators=(',', ':'))
print(cc, len(hh.ways), 'ways ->', len(keep), 'kept runs')
subprocess.run([sys.executable, '-I', os.path.join(HERE, 'rail_tiles.py')], check=True)
