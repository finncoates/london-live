# Whole bus network of a region from a BODS GTFS zip -> de-duplicated, simplified, tiled: cities/busnet/<lat10>_<lon10>.json
# Each road is drawn once, whatever the number of routes on it (like the river boats). Tiles merge with existing ones.
import sys, zipfile, csv, io, json, math, os, collections
zf, outdir = sys.argv[1], sys.argv[2]; os.makedirs(outdir, exist_ok=True)
z = zipfile.ZipFile(zf); rd = lambda n: csv.DictReader(io.TextIOWrapper(z.open(n), 'utf-8-sig'))
COACH_NOC = {'NATX', 'MEGA', 'SMGB', 'FLIX', 'CTLK', 'SCTL', 'SCLK', 'NXSH'}  # long-distance coaches: not local bus routes
coach_ag = {a['agency_id'] for a in rd('agency.txt') if (a.get('agency_noc') or '') in COACH_NOC or any(w in a['agency_name'] for w in ('National Express', 'Megabus', 'FlixBus', 'Citylink'))}
bus_routes = {r['route_id'] for r in rd('routes.txt') if r['route_type'] in ('3', '11', '200', '201', '202', '204', '209', '700', '701', '702', '704', '705', '711', '712', '713', '715', '800') and r.get('agency_id') not in coach_ag}
shapes = set()
for t in rd('trips.txt'):
    if t['route_id'] in bus_routes and t.get('shape_id'): shapes.add(t['shape_id'])
def dp(p, eps):  # closed loops (a ring line, a circular bus route) split at their farthest point first: measured against
    # a line from a point to itself, the whole loop would collapse to nothing (Copenhagen's M3 did)
    if len(p) > 3 and abs(p[0][0] - p[-1][0]) < 2e-5 and abs(p[0][1] - p[-1][1]) < 3e-5:
        k = max(range(len(p)), key=lambda i: (p[i][0] - p[0][0])**2 + ((p[i][1] - p[0][1])*0.65)**2)
        if 0 < k < len(p) - 1: return _dp_open(p[:k+1], eps)[:-1] + _dp_open(p[k:], eps)
    return _dp_open(p, eps)
_dp_loop = True
def _dp_open(p, eps):
    if len(p) < 3: return p
    k = math.cos(math.radians(p[0][0])); a, b = p[0], p[-1]
    ax, ay, bx, by = a[1]*k*111320, a[0]*111320, b[1]*k*111320, b[0]*111320; L = math.hypot(bx-ax, by-ay) or 1e-9; best, bi = 0, 0
    for i in range(1, len(p)-1):
        x, y = p[i][1]*k*111320, p[i][0]*111320; d = abs((bx-ax)*(ay-y) - (ax-x)*(by-ay))/L
        if d > best: best, bi = d, i
    return [a, b] if best <= eps else dp(p[:bi+1], eps)[:-1] + dp(p[bi:], eps)
seen = set(); tiles = collections.defaultdict(list); CELL = 0.0003  # ~30 m
SKIPMIN = 6  # pieces of 25 m: shared stretches shorter than ~150 m are drawn anyway
def add(p):
    p = dp(p, 5); pieces = []
    for i in range(1, len(p)):
        a, b = p[i-1], p[i]; L = math.hypot((b[0]-a[0])*111320, (b[1]-a[1])*69000); n = max(1, int(L/25))
        for k in range(1, n+1):
            q0 = (a[0]+(b[0]-a[0])*(k-1)/n, a[1]+(b[1]-a[1])*(k-1)/n); q1 = (a[0]+(b[0]-a[0])*k/n, a[1]+(b[1]-a[1])*k/n)
            ang = math.atan2(q1[0]-q0[0], (q1[1]-q0[1])*0.62) % math.pi; db = int(ang/(math.pi/8)) % 8  # direction (either way) in 8 steps
            key = (round((q0[0]+q1[0])/2/CELL), round((q0[1]+q1[1])/2/CELL/1.6), db)
            # same road = a nearby piece going the same way (a crossing or a side road is never 'the same')
            near = any((key[0]+i2, key[1]+j2, (db+d2) % 8) in seen for i2 in (-1, 0, 1) for j2 in (-1, 0, 1) for d2 in (-1, 0, 1))
            pieces.append([q0, q1, key, near])
    # a short 'already drawn' stretch is usually a parallel street brushing past, not a shared road: draw it (no gaps)
    k = 0
    while k < len(pieces):
        if pieces[k][3]:
            e = k
            while e < len(pieces) and pieces[e][3]: e += 1
            if e - k < SKIPMIN:
                for x in range(k, e): pieces[x][3] = False
            k = e
        else: k += 1
    run = []; mine = set()
    def flush():
        if len(run) > 1:
            t = f"{math.floor(run[0][0]*10)}_{math.floor(run[0][1]*10)}"; tiles[t].append([[round(a, 5), round(b, 5)] for a, b in run])
    for q0, q1, key, near in pieces:
        if near:
            flush(); run = []; continue
        mine.add(key)
        if not run: run = [q0]
        run.append(q1)
        if math.floor(run[0][0]*10) != math.floor(q1[0]*10) or math.floor(run[0][1]*10) != math.floor(q1[1]*10): flush(); run = [q1]
    flush(); seen.update(mine)
if os.environ.get('MERGE') == '1':  # roads already in the tiles (other regions/feeds) count as drawn
    for fn in os.listdir(outdir):
        for poly in json.load(open(os.path.join(outdir, fn))):
            for i in range(1, len(poly)):
                q0, q1 = poly[i-1], poly[i]; ang = math.atan2(q1[0]-q0[0], (q1[1]-q0[1])*0.62) % math.pi
                seen.add((round((q0[0]+q1[0])/2/CELL), round((q0[1]+q1[1])/2/CELL/1.6), int(ang/(math.pi/8)) % 8))
cur, pts, n = None, [], 0
if os.environ.get('SHAPES') == '0': shapes = set()
with z.open('shapes.txt') as f:
    for s in csv.DictReader(io.TextIOWrapper(f, 'utf-8-sig')):
        sid = s['shape_id']
        if sid != cur:
            if cur in shapes and len(pts) > 1: pts.sort(); add([(a, b) for _, a, b in pts]); n += 1
            cur, pts = sid, []
        if sid in shapes: pts.append((int(s['shape_pt_sequence']), float(s['shape_pt_lat']), float(s['shape_pt_lon'])))
    if cur in shapes and len(pts) > 1: pts.sort(); add([(a, b) for _, a, b in pts]); n += 1
if os.environ.get('NOSHAPE') == '1':  # operators that publish no route shapes: draw the route stop to stop
    LON = lambda a, b: 51.28 < a < 51.70 and -0.52 < b < 0.34  # London has TfL's own bus routes
    pick = collections.defaultdict(list)
    for t in rd('trips.txt'):
        if t['route_id'] in bus_routes and not t.get('shape_id'):
            g = pick[(t['route_id'], t.get('direction_id', ''))]
            if len(g) < 4: g.append(t['trip_id'])
    want = {tid for g in pick.values() for tid in g}
    seq = collections.defaultdict(list)
    with z.open('stop_times.txt') as f:
        for s in csv.DictReader(io.TextIOWrapper(f, 'utf-8-sig')):
            if s['trip_id'] in want: seq[s['trip_id']].append((int(s['stop_sequence']), s['stop_id']))
    need = {sid for v in seq.values() for _, sid in v}
    stp = {s['stop_id']: (float(s['stop_lat']), float(s['stop_lon'])) for s in rd('stops.txt') if s['stop_id'] in need and s.get('stop_lat')}
    done = set(); m = 0; PAIR = {}; ROUTED = [0, 0]; R = None
    if os.environ.get('PBF'):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from route import Router
        la = [q[0] for q in stp.values() if not LON(*q)]; lo = [q[1] for q in stp.values() if not LON(*q)]
        R = Router(os.environ['PBF'], (min(la) - 0.02, min(lo) - 0.03, max(la) + 0.02, max(lo) + 0.03))
    for tid, v in seq.items():
        v.sort(); key = tuple(sid for _, sid in v)
        if key in done: continue
        done.add(key); p0 = [stp[sid] for sid in key if sid in stp]
        p = []  # follow the roads between stops (straight only where no road path is found)
        for q0, q1 in zip(p0, p0[1:]):
            if LON(*q0) or LON(*q1): seg = None
            else:
                pk = (q0, q1); seg = PAIR.get(pk, 0)
                if seg == 0: seg = PAIR[pk] = R.path(q0, q1) if R else None
                if seg is None: ROUTED[1] += 1
                else: ROUTED[0] += 1
            if not p: p.append(q0)
            if seg: p.extend(seg[1:])
            elif math.hypot((q1[0]-q0[0])*111320, (q1[1]-q0[1])*69000) > 700: p.extend([None, q1])  # no road found: leave a gap, never a chord across town
            else: p.append(q1)
        part = []
        for q in p:
            if q is None or LON(*q): 
                if len(part) > 1: add(part)
                part = []
            elif not part or math.hypot((q[0]-part[-1][0])*111320, (q[1]-part[-1][1])*69000) < 4000: part.append(q)
            else:
                if len(part) > 1: add(part)
                part = [q]
        if len(part) > 1: add(part); m += 1
    print('stop-to-stop routes', m, 'road-routed pairs', ROUTED[0], 'straight', ROUTED[1])
tot = 0
for t, polys in tiles.items():
    fn = os.path.join(outdir, t + '.json'); old = json.load(open(fn)) if os.path.exists(fn) else []
    json.dump(old + polys, open(fn, 'w'), separators=(',', ':')); tot += os.path.getsize(fn)
print(n, 'shapes ->', len(tiles), 'tiles', sum(len(p) for v in tiles.values() for p in v), 'points', tot, 'bytes')
