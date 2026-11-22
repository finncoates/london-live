# Whole bus network of a region from a BODS GTFS zip -> de-duplicated, simplified, tiled: cities/busnet/<lat10>_<lon10>.json
# Each road is drawn once, whatever the number of routes on it (like the river boats). Tiles merge with existing ones.
import sys, zipfile, csv, io, json, math, os, collections
zf, outdir = sys.argv[1], sys.argv[2]; os.makedirs(outdir, exist_ok=True)
z = zipfile.ZipFile(zf); rd = lambda n: csv.DictReader(io.TextIOWrapper(z.open(n), 'utf-8-sig'))
COACH_NOC = {'NATX', 'MEGA', 'SMGB', 'FLIX', 'CTLK', 'SCTL', 'SCLK', 'NXSH'}  # long-distance coaches: not local bus routes
coach_ag = {a['agency_id'] for a in rd('agency.txt') if (a.get('agency_noc') or '') in COACH_NOC or any(w in a['agency_name'] for w in ('National Express', 'Megabus', 'FlixBus', 'Citylink'))}
bus_routes = {r['route_id'] for r in rd('routes.txt') if r['route_type'] in ('3', '700', '702', '704', '715') and r.get('agency_id') not in coach_ag}
shapes = set()
for t in rd('trips.txt'):
    if t['route_id'] in bus_routes and t.get('shape_id'): shapes.add(t['shape_id'])
def dp(p, eps):
    if len(p) < 3: return p
    k = math.cos(math.radians(p[0][0])); a, b = p[0], p[-1]
    ax, ay, bx, by = a[1]*k*111320, a[0]*111320, b[1]*k*111320, b[0]*111320; L = math.hypot(bx-ax, by-ay) or 1e-9; best, bi = 0, 0
    for i in range(1, len(p)-1):
        x, y = p[i][1]*k*111320, p[i][0]*111320; d = abs((bx-ax)*(ay-y) - (ax-x)*(by-ay))/L
        if d > best: best, bi = d, i
    return [a, b] if best <= eps else dp(p[:bi+1], eps)[:-1] + dp(p[bi:], eps)
seen = set(); tiles = collections.defaultdict(list); CELL = 0.0003  # ~30 m
def add(p):
    p = dp(p, 5); run = []; mine = set()
    def flush():
        if len(run) > 1:
            t = f"{math.floor(run[0][0]*10)}_{math.floor(run[0][1]*10)}"; tiles[t].append([[round(a, 5), round(b, 5)] for a, b in run])
    for i in range(1, len(p)):
        a, b = p[i-1], p[i]; L = math.hypot((b[0]-a[0])*111320, (b[1]-a[1])*69000); n = max(1, int(L/25))
        for k in range(1, n+1):
            q0 = (a[0]+(b[0]-a[0])*(k-1)/n, a[1]+(b[1]-a[1])*(k-1)/n); q1 = (a[0]+(b[0]-a[0])*k/n, a[1]+(b[1]-a[1])*k/n)
            ang = math.atan2(q1[0]-q0[0], (q1[1]-q0[1])*0.62) % math.pi; db = int(ang/(math.pi/8)) % 8  # direction (either way) in 8 steps
            key = (round((q0[0]+q1[0])/2/CELL), round((q0[1]+q1[1])/2/CELL/1.6), db)
            # same road = a nearby piece going the same way (a crossing or a side road is never 'the same')
            near = any((key[0]+i2, key[1]+j2, (db+d2) % 8) in seen for i2 in (-1, 0, 1) for j2 in (-1, 0, 1) for d2 in (-1, 0, 1))
            if near:
                flush(); run = []; continue
            mine.add(key)
            if not run: run = [q0]
            run.append(q1)
            if math.floor(run[0][0]*10) != math.floor(q1[0]*10) or math.floor(run[0][1]*10) != math.floor(q1[1]*10): flush(); run = [q1]
    flush(); seen.update(mine)
cur, pts, n = None, [], 0
with z.open('shapes.txt') as f:
    for s in csv.DictReader(io.TextIOWrapper(f, 'utf-8-sig')):
        sid = s['shape_id']
        if sid != cur:
            if cur in shapes and len(pts) > 1: pts.sort(); add([(a, b) for _, a, b in pts]); n += 1
            cur, pts = sid, []
        if sid in shapes: pts.append((int(s['shape_pt_sequence']), float(s['shape_pt_lat']), float(s['shape_pt_lon'])))
    if cur in shapes and len(pts) > 1: pts.sort(); add([(a, b) for _, a, b in pts]); n += 1
tot = 0
for t, polys in tiles.items():
    fn = os.path.join(outdir, t + '.json'); old = json.load(open(fn)) if os.path.exists(fn) else []
    json.dump(old + polys, open(fn, 'w'), separators=(',', ':')); tot += os.path.getsize(fn)
print(n, 'shapes ->', len(tiles), 'tiles', sum(len(p) for v in tiles.values() for p in v), 'points', tot, 'bytes')
