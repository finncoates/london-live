# National Rail network of Great Britain (OpenStreetMap: railway=rail, main and branch lines; no sidings, yards or heritage)
#   python3 osm_nr.py uk.osm.pbf outdir      -> outdir/<lat2>_<lon2>.json (0.5° tiles, ~8 m detail) + outdir/all.json (overview, ~80 m)
import sys, os, json, math, collections, osmium
pbf, out = sys.argv[1:3]; os.makedirs(out, exist_ok=True)
class H(osmium.SimpleHandler):
    def __init__(h): super().__init__(); h.ways = []
    def way(h, w):
        t = w.tags
        if t.get('railway') != 'rail' or t.get('service') or t.get('usage') in ('industrial', 'military', 'tourism', 'test') or t.get('railway:preserved') == 'yes': return
        if t.get('usage') not in ('main', 'branch', None): return
        try: p = [(round(n.lat, 5), round(n.lon, 5)) for n in w.nodes]
        except osmium.InvalidLocationError: return
        if p[0][0] < 49.8 or p[0][1] < -8.7: return
        h.ways.append(p)
hh = H(); hh.apply_file(pbf, locations=True, idx=os.environ.get('OSM_IDX', 'flex_mem'))
# one line per pair of parallel tracks: keep a way only if no already-kept track runs alongside it (within 25 m, same direction)
k = 0.6
def dp(p, eps):
    if len(p) < 3: return p
    ax, ay, bx, by = p[0][1]*k*111320, p[0][0]*111320, p[-1][1]*k*111320, p[-1][0]*111320; L = math.hypot(bx-ax, by-ay) or 1e-9; best, bi = 0, 0
    for i in range(1, len(p)-1):
        x, y = p[i][1]*k*111320, p[i][0]*111320; d = abs((bx-ax)*(ay-y) - (ax-x)*(by-ay))/L
        if d > best: best, bi = d, i
    return [p[0], p[-1]] if best <= eps else dp(p[:bi+1], eps)[:-1] + dp(p[bi:], eps)
seen = set(); C = 25
def cells(a, b):
    L = math.hypot((b[0]-a[0])*111320, (b[1]-a[1])*111320*k); n = max(1, int(L // 20)); ang = int((math.atan2(b[0]-a[0], (b[1]-a[1])*k) % math.pi)/(math.pi/8)) % 8
    return [(round((a[0] + (b[0]-a[0])*t/n)*111320/C), round((a[1] + (b[1]-a[1])*t/n)*111320*k/C), ang) for t in range(n + 1)]
keep = []
for p in sorted(hh.ways, key=len, reverse=True):
    run = []; mine = set()
    for a, b in zip(p, p[1:]):
        cs = cells(a, b)
        if all(any((c[0]+i, c[1]+j, (c[2]+d) % 8) in seen for i in (-1, 0, 1) for j in (-1, 0, 1) for d in (-1, 0, 1)) for c in cs):
            if len(run) > 1: keep.append(run)
            run = []; continue
        mine.update(cs); run = run or [a]; run.append(b)
    if len(run) > 1: keep.append(run)
    seen |= mine
T = collections.defaultdict(list); tk = lambda q: f"{math.floor(q[0]*2)}_{math.floor(q[1]*2)}"
for p in keep:
    p = dp(p, 8); run = [p[0]]
    for q in p[1:]:
        run.append(q)
        if tk(q) != tk(run[0]): T[tk(run[0])].append(run); run = [q]
    if len(run) > 1: T[tk(run[0])].append(run)
for f in os.listdir(out): os.remove(os.path.join(out, f))
for t, ps in T.items(): json.dump(ps, open(os.path.join(out, t + '.json'), 'w'), separators=(',', ':'))
ov = [[[round(a, 4), round(b, 4)] for a, b in dp(p, 80)] for p in keep if len(p) > 1]
json.dump([p for p in ov if len(p) > 1], open(os.path.join(out, 'all.json'), 'w'), separators=(',', ':'))
print(len(hh.ways), 'ways ->', len(keep), 'kept runs,', len(T), 'tiles,', os.path.getsize(os.path.join(out, 'all.json')), 'bytes overview')
