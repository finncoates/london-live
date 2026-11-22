# Bus route map v2: every bus route is matched onto the OpenStreetMap road network, and the map is the union of the road
# segments any bus uses. Each road is drawn exactly once and nothing is skipped, so there are no gaps and no doubled lines.
#   1) per region:  python3 busnet2.py match region.osm.pbf edges_<region>.pkl feed1.zip [feed2.zip ...]
#   2) at the end:  python3 busnet2.py tiles out_dir edges_*.pkl
# Routes with shapes (GTFS shapes.txt) are matched point by point; routes without shapes are routed stop to stop.
import sys, os, zipfile, csv, io, json, math, pickle, collections, heapq
import numpy as np

LON = lambda a, b: 51.28 < a < 51.70 and -0.52 < b < 0.34  # London has TfL's own bus routes
COACH_NOC = {'NATX', 'MEGA', 'SMGB', 'FLIX', 'CTLK', 'SCTL', 'SCLK', 'NXSH'}

def feed_routes(zf):
    z = zipfile.ZipFile(zf); rd = lambda n: csv.DictReader(io.TextIOWrapper(z.open(n), 'utf-8-sig'))
    coach = {a['agency_id'] for a in rd('agency.txt') if (a.get('agency_noc') or '') in COACH_NOC or any(w in a['agency_name'] for w in ('National Express', 'Megabus', 'FlixBus', 'Citylink'))}
    bus = {r['route_id'] for r in rd('routes.txt') if r['route_type'] in ('3', '700', '702', '704', '715') and r.get('agency_id') not in coach}
    shapes = set(); pick = collections.defaultdict(list)
    for t in rd('trips.txt'):
        if t['route_id'] not in bus: continue
        if t.get('shape_id'): shapes.add(t['shape_id'])
        else:
            g = pick[(t['route_id'], t.get('direction_id', ''))]
            if len(g) < 4: g.append(t['trip_id'])
    polys = []; seenshape = set()
    if 'shapes.txt' in z.namelist() and shapes:
        cur, pts = None, []
        def done():
            if cur in shapes and len(pts) > 1:
                pts.sort(); p = tuple((round(a, 5), round(b, 5)) for _, a, b in pts)
                if p not in seenshape: seenshape.add(p); polys.append(('shape', p))
        with z.open('shapes.txt') as f:
            for s in csv.DictReader(io.TextIOWrapper(f, 'utf-8-sig')):
                if s['shape_id'] != cur: done(); cur, pts = s['shape_id'], []
                if s['shape_id'] in shapes: pts.append((int(s['shape_pt_sequence']), float(s['shape_pt_lat']), float(s['shape_pt_lon'])))
            done()
    want = {tid for g in pick.values() for tid in g}
    if want:
        seq = collections.defaultdict(list)
        with z.open('stop_times.txt') as f:
            for s in csv.DictReader(io.TextIOWrapper(f, 'utf-8-sig')):
                if s['trip_id'] in want: seq[s['trip_id']].append((int(s['stop_sequence']), s['stop_id']))
        need = {sid for v in seq.values() for _, sid in v}
        stp = {s['stop_id']: (float(s['stop_lat']), float(s['stop_lon'])) for s in rd('stops.txt') if s['stop_id'] in need and s.get('stop_lat')}
        done2 = set()
        for v in seq.values():
            v.sort(); key = tuple(sid for _, sid in v)
            if key in done2: continue
            done2.add(key); p = tuple(stp[s] for s in key if s in stp)
            if len(p) > 1: polys.append(('stops', p))
    return polys

def match(pbf, out, zips):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from route import Router
    polys = [x for zf in zips for x in feed_routes(zf)]
    allp = [q for _, p in polys for q in p if not LON(*q)]
    la = sorted(q[0] for q in allp); lo = sorted(q[1] for q in allp)
    box = (la[int(len(la)*0.001)] - 0.05, lo[int(len(lo)*0.001)] - 0.08, la[int(len(la)*0.999)] + 0.05, lo[int(len(lo)*0.999)] + 0.08)
    print(len(polys), 'routes', sum(1 for k, _ in polys if k == 'stops'), 'without shapes; box', [round(x, 2) for x in box], flush=True)
    R = Router(pbf, box); lat, lon, adj, k = R.lat, R.lon, R.adj, R.k
    nb = [None] * len(adj)
    def nbr(i):
        s = nb[i]
        if s is None: s = nb[i] = {m: d for m, d in adj[i]}
        return s
    def astar(i, j, cap):
        if i == j: return [i]
        hx = lambda n: math.hypot((lat[n] - lat[j]) * 111320, (lon[n] - lon[j]) * 111320 * k)
        g = {i: 0.0}; came = {}; pq = [(hx(i), 0.0, i)]; steps = 0
        while pq:
            f, gc, n = heapq.heappop(pq)
            if n == j: break
            if gc > g.get(n, 1e18): continue
            if f > cap: return None
            steps += 1
            if steps > 4000: return None
            for m, d in adj[n]:
                ng = gc + d
                if ng < g.get(m, 1e18): g[m] = ng; came[m] = n; heapq.heappush(pq, (ng + hx(m), ng, m))
        else: return None
        out_ = [j]
        while out_[-1] != i: out_.append(came[out_[-1]])
        return out_[::-1]
    edges = set(); raw = []; cache = {}; stats = collections.Counter()
    def addpath(ns):
        for a, b in zip(ns, ns[1:]):
            if a != b: edges.add((a, b) if a < b else (b, a))
    def link(i, j, d):  # road path between two snapped nodes
        if j in nbr(i): addpath([i, j]); return True
        key = (i, j) if i < j else (j, i); ns = cache.get(key, 0)
        if ns == 0: ns = cache[key] = astar(key[0], key[1], 2.0 * d + 80) or astar(key[0], key[1], 4.0 * d + 300)
        if ns: addpath(ns); return True
        return False
    for n_, (kind, p) in enumerate(polys):
        if n_ % 2000 == 0: print(' ', n_, len(edges), 'edges', flush=True)
        if kind == 'shape':  # densify to ~25 m, snap each point to the road, join neighbours along the road
            pts = [p[0]]
            for a, b in zip(p, p[1:]):
                L = math.hypot((b[0]-a[0])*111320, (b[1]-a[1])*111320*k); n = max(1, int(L // 25))
                for t in range(1, n + 1): pts.append((a[0] + (b[0]-a[0])*t/n, a[1] + (b[1]-a[1])*t/n))
            pts = [q for q in pts if not LON(*q)]
            if len(pts) < 2: continue
            X = np.array([(q[0]*111320, q[1]*111320*k) for q in pts]); dd, ii = R.tree.query(X, distance_upper_bound=35)
            last = None; miss = []  # last matched (point, node); unmatched points since then
            for q, d0, i in zip(pts, dd, ii):
                if not d0 < 35: stats['off road'] += 1; miss.append(q); continue
                i = int(i)
                if last is not None and last[1] != i:
                    lq = last[0]; dist = math.hypot((q[0]-lq[0])*111320, (q[1]-lq[1])*111320*k)
                    if dist < 400 and link(last[1], i, dist): stats['matched'] += 1
                    else:
                        seq_ = [lq] + miss + [q]; raw.extend(zip(seq_, seq_[1:])); stats['raw'] += 1
                elif last is None and miss:
                    raw.extend(zip(miss + [q], (miss + [q])[1:]))
                last = (q, i); miss = []
            if miss and last is not None: seq_ = [last[0]] + miss; raw.extend(zip(seq_, seq_[1:]))
        else:  # stops only: road path stop to stop
            for a, b in zip(p, p[1:]):
                if LON(*a) or LON(*b): continue
                S = R.near(a, 40); T = R.near(b, 40)
                d = math.hypot((b[0]-a[0])*111320, (b[1]-a[1])*111320*k)
                if not S or not T: stats['stop off road'] += 1; continue
                key = (a, b); ns = cache.get(key, 0)
                if ns == 0:
                    ns = None; best = None
                    si = min(S, key=lambda n: (lat[n]-a[0])**2 + ((lon[n]-a[1])*k)**2); ti = min(T, key=lambda n: (lat[n]-b[0])**2 + ((lon[n]-b[1])*k)**2)
                    ns = cache[key] = astar(si, ti, 2.5 * d + 400)
                if ns: addpath(ns); stats['stop hops'] += 1
                else: stats['stop hops failed'] += 1
    # node ids -> coordinates (graph is per region; coordinates make edges comparable across regions)
    E = {(round(lat[a], 6), round(lon[a], 6), round(lat[b], 6), round(lon[b], 6)) for a, b in edges}
    pickle.dump({'edges': E, 'raw': raw}, open(out, 'wb'))
    print('edges', len(E), 'raw', len(raw), dict(stats), flush=True)

def dp(p, eps):
    if len(p) < 3: return p
    k = math.cos(math.radians(p[0][0])); a, b = p[0], p[-1]
    ax, ay, bx, by = a[1]*k*111320, a[0]*111320, b[1]*k*111320, b[0]*111320; L = math.hypot(bx-ax, by-ay) or 1e-9; best, bi = 0, 0
    for i in range(1, len(p)-1):
        x, y = p[i][1]*k*111320, p[i][0]*111320; d = abs((bx-ax)*(ay-y) - (ax-x)*(by-ay))/L
        if d > best: best, bi = d, i
    return [a, b] if best <= eps else dp(p[:bi+1], eps)[:-1] + dp(p[bi:], eps)

def tiles(outdir, files):
    E = set(); raw = []
    for f in files:
        d = pickle.load(open(f, 'rb')); E |= {((a, b), (c, e)) for a, b, c, e in d['edges']}; raw += d['raw']
    adj = collections.defaultdict(set)
    for u, v in E:
        if u != v: adj[u].add(v); adj[v].add(u)
    # stray stubs: short dead ends (a point snapped into a side street) are removed, a few times over
    L = lambda u, v: math.hypot((u[0]-v[0])*111320, (u[1]-v[1])*111320*0.6)
    for _ in range(3):
        cut = 0
        for u in [x for x in adj if len(adj[x]) == 1]:
            path = [u]; prev = None; cur = u; length = 0
            while len(adj[cur]) <= 2 and length < 40:
                nxt = [x for x in adj[cur] if x != prev]
                if not nxt: break
                length += L(cur, nxt[0]); prev, cur = cur, nxt[0]; path.append(cur)
            if length < 40 and len(adj[cur]) >= 3:
                for a, b in zip(path, path[1:]): adj[a].discard(b); adj[b].discard(a)
                cut += 1
        if not cut: break
    for u in [x for x in adj if not adj[x]]: del adj[u]
    used = set(); lines = []
    def walk(u, v):
        line = [u, v]; used.add((u, v) if u < v else (v, u))
        while len(adj[v]) == 2:
            w = next(x for x in adj[v] if x != line[-2])
            e = (v, w) if v < w else (w, v)
            if e in used: break
            used.add(e); line.append(w); v = w
        return line
    for u in list(adj):
        if len(adj[u]) != 2:
            for v in adj[u]:
                if ((u, v) if u < v else (v, u)) not in used: lines.append(walk(u, v))
    for u in list(adj):  # closed loops
        for v in adj[u]:
            if ((u, v) if u < v else (v, u)) not in used: lines.append(walk(u, v))
    # raw pieces (where no road matched): keep those not alongside a matched road
    cell = lambda q: (round(q[0] / 0.0004), round(q[1] / 0.0006))
    near = set(cell(u) for u in adj)
    rawkeep = []
    for a, b in raw:
        m = ((a[0]+b[0])/2, (a[1]+b[1])/2); c = cell(m)
        if not any((c[0]+i, c[1]+j) in near for i in (-1, 0, 1) for j in (-1, 0, 1)): rawkeep.append([a, b])
    T = collections.defaultdict(list)
    tk = lambda q: f"{math.floor(q[0]*10)}_{math.floor(q[1]*10)}"
    for line in [dp(l, 2.5) for l in lines] + rawkeep:
        run = [line[0]]
        for q in line[1:]:
            run.append(q)
            if tk(q) != tk(run[0]): T[tk(run[0])].append(run); run = [q]
        if len(run) > 1: T[tk(run[0])].append(run)
    os.makedirs(outdir, exist_ok=True)
    for f in os.listdir(outdir):
        if f.endswith('.json'): os.remove(os.path.join(outdir, f))
    tot = 0
    for t, polys in T.items():
        fn = os.path.join(outdir, t + '.json'); json.dump([[[round(a, 5), round(b, 5)] for a, b in p] for p in polys], open(fn, 'w'), separators=(',', ':')); tot += os.path.getsize(fn)
    print(len(E), 'road segments ->', len(lines), 'lines,', len(rawkeep), 'unmatched pieces kept ->', len(T), 'tiles', tot, 'bytes')

if __name__ == '__main__':
    if sys.argv[1] == 'match': match(sys.argv[2], sys.argv[3], sys.argv[4:])
    else: tiles(sys.argv[2], sys.argv[3:])
