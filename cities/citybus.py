# Bus route map for a city outside the UK (Berlin, Boston, Helsinki) from its GTFS shapes -> cities/busnet/<lat10>_<lon10>.json
# (same tiles as the UK bus map). Every bus shape inside the box is simplified (~3 m) and cut into segments on a ~1 m grid;
# a segment that another route already drew (either direction) is dropped, so each road is mostly drawn once, and what is
# left is joined back into polylines tile by tile. Nothing is skipped by closeness, so there are no gaps.
#   python3 -I citybus.py feed.zip out_dir s w n e
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace'); _s.stderr.reconfigure(encoding='utf-8', errors='replace')  # Windows console: never crash on a name
import sys, zipfile, csv, io, json, math, os, collections
zf, outdir = sys.argv[1], sys.argv[2]; S, W, N, E = map(float, sys.argv[3:7]); os.makedirs(outdir, exist_ok=True)
z = zipfile.ZipFile(zf); rd = lambda n: csv.DictReader(io.TextIOWrapper(z.open(n), 'utf-8-sig'))
BUS = {'3', '11', '700', '701', '702', '704', '705', '711', '712', '715', '800'}  # buses, trolleybuses (MBTA Silver Line is 3)
routes = {r['route_id'] for r in rd('routes.txt') if r['route_type'] in BUS}
shapes = {t['shape_id'] for t in rd('trips.txt') if t['route_id'] in routes and t.get('shape_id')}
pts = collections.defaultdict(list)
for r in rd('shapes.txt'):
    if r['shape_id'] in shapes: pts[r['shape_id']].append((int(r['shape_pt_sequence']), float(r['shape_pt_lat']), float(r['shape_pt_lon'])))
def dp(p, eps):
    if len(p) < 3: return p
    k = math.cos(math.radians(p[0][0])); a, b = p[0], p[-1]
    ax, ay, bx, by = a[1]*k*111320, a[0]*111320, b[1]*k*111320, b[0]*111320; L = math.hypot(bx-ax, by-ay) or 1e-9; best, bi = 0, 0
    for i in range(1, len(p)-1):
        x, y = p[i][1]*k*111320, p[i][0]*111320; d = abs((bx-ax)*(ay-y) - (ax-x)*(by-ay))/L
        if d > best: best, bi = d, i
    return [a, b] if best <= eps else dp(p[:bi+1], eps)[:-1] + dp(p[bi:], eps)
sys.setrecursionlimit(100000)
seen = set(); tiles = collections.defaultdict(list); nseg = 0
for sid, L in pts.items():
    L.sort(); p = [(round(la, 5), round(lo, 5)) for _, la, lo in L if S < la < N and W < lo < E]
    p = [q for i, q in enumerate(p) if i == 0 or q != p[i-1]]
    if len(p) < 2: continue
    p = dp(p, 3); run, rt = [], None
    for a, b in zip(p, p[1:]):
        key = (a, b) if a < b else (b, a); t = f'{math.floor((a[0]+b[0])/2*10)}_{math.floor((a[1]+b[1])/2*10)}'
        if key in seen:
            if len(run) > 1: tiles[rt].append(run)
            run = []; continue
        seen.add(key); nseg += 1
        if run and t == rt and run[-1] == a: run.append(b)
        else:
            if len(run) > 1: tiles[rt].append(run)
            run, rt = [a, b], t
    if len(run) > 1: tiles[rt].append(run)
# join pieces that meet end to start (fewer, longer polylines draw faster)
for t, polys in tiles.items():
    starts = collections.defaultdict(list)
    for i, q in enumerate(polys): starts[q[0]].append(i)
    used, out = set(), []
    for i, q in enumerate(polys):
        if i in used: continue
        used.add(i); line = list(q)
        while True:
            nxt = next((j for j in starts.get(line[-1], []) if j not in used), None)
            if nxt is None: break
            used.add(nxt); line += polys[nxt][1:]
        out.append([[a, b] for a, b in line])
    with open(os.path.join(outdir, t + '.json'), 'w') as f: json.dump(out, f, separators=(',', ':'))
print(len(shapes), 'shapes,', nseg, 'segments,', len(tiles), 'tiles')
