# Bus route map v2: every bus route is matched onto the OpenStreetMap road network, and the map is the union of the road
# segments any bus uses. Each road is drawn exactly once and nothing is skipped, so there are no gaps and no doubled lines.
#   1) per region:  python3 busnet2.py match region.osm.pbf edges_<region>.pkl feed1.zip [feed2.zip ...]
#   2) at the end:  python3 busnet2.py tiles out_dir edges_*.pkl
# Routes with shapes (GTFS shapes.txt) are matched point by point; routes without shapes are routed stop to stop.
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace'); _s.stderr.reconfigure(encoding='utf-8', errors='replace')  # Windows console: never crash on a name
import sys, os, zipfile, csv, io, json, math, pickle, collections, heapq
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from greater_london import in_london as LON  # Greater London has TfL's own bus routes (the boundary, not a box: Watford, Dartford, Epsom are outside it)
COACH_NOC = {'NATX', 'MEGA', 'SMGB', 'FLIX', 'CTLK', 'SCTL', 'SCLK', 'NXSH'}

COACH_NAMES = {'National Express', 'Megabus', 'megabus', 'FlixBus', 'Flixbus', 'Scottish Citylink', 'Citylink'}
def is_coach(a):  # long-distance coaches only: National Express West Midlands / Coventry are city buses and stay on the bus map
    return (a.get('agency_noc') or '') in COACH_NOC or a['agency_name'].strip() in COACH_NAMES
def feed_routes(zf):
    z = zipfile.ZipFile(zf); rd = lambda n: csv.DictReader(io.TextIOWrapper(z.open(n), 'utf-8-sig'))
    coach = {a['agency_id'] for a in rd('agency.txt') if is_coach(a)}
    bus = {r['route_id'] for r in rd('routes.txt') if r['route_type'] in ('3', '11', '200', '201', '202', '204', '209', '700', '701', '702', '704', '705', '711', '712', '713', '715', '800') and r.get('agency_id') not in coach}
    shapes = set(); pick = collections.defaultdict(list)
    for t in rd('trips.txt'):
        if t['route_id'] not in bus: continue
        if t.get('shape_id'): shapes.add(t['shape_id'])
        else:
            g = pick[(t['route_id'], t.get('direction_id', ''))]
            if len(g) < 4: g.append(t['trip_id'])
    polys = []; seenshape = set()
    if 'shapes.txt' in z.namelist() and shapes:
        acc = collections.defaultdict(list)  # (by shape: Lisbon's Carris lists its shapes' points interleaved, not one shape after another)
        with z.open('shapes.txt') as f:
            for s in csv.DictReader(io.TextIOWrapper(f, 'utf-8-sig')):
                if s['shape_id'] in shapes: acc[s['shape_id']].append((int(s['shape_pt_sequence']), float(s['shape_pt_lat']), float(s['shape_pt_lon'])))
        for sid, pts in acc.items():
            if len(pts) > 1:
                pts.sort(); p = tuple((round(a, 5), round(b, 5)) for _, a, b in pts)
                if p not in seenshape: seenshape.add(p); polys.append(('shape', p))
    want = {tid for g in pick.values() for tid in g}
    if want:
        seq = collections.defaultdict(list)
        with z.open('stop_times.txt') as f:
            for s in csv.DictReader(io.TextIOWrapper(f, 'utf-8-sig')):
                if s['trip_id'] in want: seq[s['trip_id']].append((int(s['stop_sequence']), s['stop_id']))
        need = {sid for v in seq.values() for _, sid in v}
        stp = {s['stop_id']: (float(s['stop_lat']), float(s['stop_lon'])) for s in rd('stops.txt') if s['stop_id'] in need and s.get('stop_lat') and not (abs(float(s['stop_lat'])) < 1 and abs(float(s['stop_lon'])) < 1)}  # (not at 0°, 0°)
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
            if steps > 30000: return None  # (Switzerland's roads are mapped densely: 4,000 steps failed most hops in Lucerne)
            for m, d in adj[n]:
                ng = gc + d
                if ng < g.get(m, 1e18): g[m] = ng; came[m] = n; heapq.heappush(pq, (ng + hx(m), ng, m))
        else: return None
        out_ = [j]
        while out_[-1] != i: out_.append(came[out_[-1]])
        return out_[::-1]
    edges = set(); raw = []; cache = {}; stats = collections.Counter(); OFFS = collections.Counter()
    def addpath(ns):
        for a, b in zip(ns, ns[1:]):
            if a != b: edges.add((a, b) if a < b else (b, a))
    def astar_multi(a, S, T, cap):
        if not S or not T: return None
        cx, cy = sum(lat[t] for t in T)/len(T), sum(lon[t] for t in T)/len(T)
        hx = lambda n: max(0.0, math.hypot((lat[n] - cx) * 111320, (lon[n] - cy) * 111320 * k) - 40)
        g = {}; came = {}; pq = []
        for n in S: c = math.hypot((lat[n] - a[0]) * 111320, (lon[n] - a[1]) * 111320 * k); g[n] = c; heapq.heappush(pq, (c + hx(n), c, n))
        steps = 0; end = None
        while pq:
            f, gc, n = heapq.heappop(pq)
            if gc > g.get(n, 1e18): continue
            if n in T: end = n; break
            if f > cap: return None
            steps += 1
            if steps > 30000: return None
            for m, dd in adj[n]:
                ng = gc + dd
                if ng < g.get(m, 1e18): g[m] = ng; came[m] = n; heapq.heappush(pq, (ng + hx(m), ng, m))
        if end is None: return None
        out_ = [end]
        while out_[-1] in came: out_.append(came[out_[-1]])
        return out_[::-1]
    def link(i, j, d):  # road path between two snapped nodes
        if j in nbr(i): addpath([i, j]); return True
        key = (i, j) if i < j else (j, i); ns = cache.get(key, 0)
        if ns == 0: ns = cache[key] = astar(key[0], key[1], 1.3 * d + 30)  # the road the shape follows, not a detour round a missing link
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
            X = np.array([(q[0]*111320, q[1]*111320*k) for q in pts]); DD, II = R.tree.query(X, k=6, distance_upper_bound=35)
            last = None; miss = []  # last matched (point, node); unmatched points since then
            for q, dds, iis in zip(pts, DD, II):
                cands = [int(i) for d0, i in zip(dds, iis) if d0 < 35]
                if not cands: stats['off road'] += 1; miss.append(q); continue
                if last is None: last = (q, cands[0]); miss = []; continue
                lq = last[0]; dist = math.hypot((q[0]-lq[0])*111320, (q[1]-lq[1])*111320*k)
                # stay on the road we're on: the nearest candidate reachable along the roads from the last one
                hit = None
                if dist < 400:
                    for c in cands:
                        if c == last[1] or link(last[1], c, dist): hit = c; break
                if hit is not None: stats['matched'] += 1; last = (q, hit)
                else:
                    # a stretch of the shape off the roads (cut straight across a block: Bordeaux's TBM shapes): the roads
                    # between the last point on a road and this one, if there's a route not much longer than the cut
                    ns = astar_multi(lq, [last[1]], set(cands), 1.6 * dist + 300) if dist < 3000 else None
                    if ns: addpath(ns); stats['bridged'] += 1; last = (q, ns[-1])
                    else: seq_ = [lq] + miss + [q]; raw.extend(zip(seq_, seq_[1:])); stats['raw'] += 1; last = (q, cands[0])
                miss = []
            if miss and last is not None: seq_ = [last[0]] + miss; raw.extend(zip(seq_, seq_[1:]))
        else:  # stops only: road path stop to stop
            for a, b in zip(p, p[1:]):
                if LON(*a) or LON(*b): continue
                S = R.near(a, 40); T = R.near(b, 40)
                d = math.hypot((b[0]-a[0])*111320, (b[1]-a[1])*111320*k)
                if not S or not T: stats['stop off road'] += 1; OFFS[(round((a if not S else b)[0], 1), round((a if not S else b)[1], 1))] += 1; continue
                key = (a, b); ns = cache.get(key, 0)
                if ns == 0:
                    ns = None; best = None
                    ns = cache[key] = astar_multi(a, S, set(T), 2.5 * d + 400)  # from any road node by the stop to any by the next (the nearest alone is often the other carriageway of a one-way pair: most of Lucerne's hops failed)
                if ns: addpath(ns); stats['stop hops'] += 1
                else:
                    stats['stop hops failed'] += 1
                    if d < 600: raw.append((a, b))  # short hop with no road found: drawn straight rather than missing
    # node ids -> coordinates (graph is per region; coordinates make edges comparable across regions)
    E = {(round(lat[a], 6), round(lon[a], 6), round(lat[b], 6), round(lon[b], 6)) for a, b in edges}
    pickle.dump({'edges': E, 'raw': raw}, open(out, 'wb'))
    print('edges', len(E), 'raw', len(raw), dict(stats), 'stops off road by area', OFFS.most_common(6), flush=True)

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
    # tiny islands (a few metres of road matched on their own, joined to nothing): dropped
    seenc = set()
    for u in list(adj):
        if u in seenc: continue
        comp = [u]; seenc.add(u); i = 0
        while i < len(comp):
            for v in adj[comp[i]]:
                if v not in seenc: seenc.add(v); comp.append(v)
            i += 1
        if len(comp) < 40:
            L = sum(math.hypot((a[0]-b[0])*111320, (a[1]-b[1])*111320*0.6) for a in comp for b in adj[a]) / 2
            if L < 80:
                for a in comp: adj[a] = set()
    for u in [x for x in adj if not adj[x]]: del adj[u]
    # raw pieces (where no road matched): every bit of a bus route farther than 20 m from the drawn roads is drawn as published,
    # so nothing a bus drives is ever missing (strict: sampled every 8 m against the matched road segments themselves)
    from scipy.spatial import cKDTree
    import numpy as np
    kx = 111320*0.6
    S = []; SD = []
    for u in adj:
        for v in adj[u]:
            if u < v:
                L = math.hypot((u[0]-v[0])*111320, (u[1]-v[1])*kx); n = max(1, int(L // 8))
                ux, uy = (v[1]-u[1])*kx/(L or 1), (v[0]-u[0])*111320/(L or 1)
                for t in range(n + 1): S.append(((u[0] + (v[0]-u[0])*t/n)*111320, (u[1] + (v[1]-u[1])*t/n)*kx)); SD.append((ux, uy))
    tree = cKDTree(np.array(S)) if S else None; SD = np.array(SD)
    rawkeep = []; cur = None
    for a, b in raw:
        L = math.hypot((b[0]-a[0])*111320, (b[1]-a[1])*kx)
        if cur is not None and math.hypot((cur[-1][0]-a[0])*111320, (cur[-1][1]-a[1])*kx) > 12: cur = None  # not a continuation
        if L > 1500: cur = None; continue  # a jump in the data, not a road
        n = max(1, int(L // 8)); qs = [(a[0] + (b[0]-a[0])*t/n, a[1] + (b[1]-a[1])*t/n) for t in range(n + 1)]
        if tree is not None and L > 0:  # covered = a drawn road within 20 m running the same way (a side road meeting it doesn't count)
            rx, ry = (b[1]-a[1])*kx/L, (b[0]-a[0])*111320/L
            nb = tree.query_ball_point(np.array([(q[0]*111320, q[1]*kx) for q in qs]), 20)
            far = [not any(abs(SD[j][0]*rx + SD[j][1]*ry) > 0.8 for j in js) for js in nb]
        else: far = [True]*len(qs)
        def nearS(q):  # the nearest drawn point: uncovered pieces start and end exactly on the road they leave / rejoin
            if tree is None: return q
            dd, j = tree.query((q[0]*111320, q[1]*kx)); return (S[j][0]/111320, S[j][1]/kx) if dd < 30 else q
        prevq = None
        for q, f in zip(qs, far):
            if f:
                if cur is not None and cur[-1] == q: prevq = q; continue
                if cur is not None and math.hypot((cur[-1][0]-q[0])*111320, (cur[-1][1]-q[1])*kx) < 12: cur.append(q)
                else:
                    cur = ([nearS(prevq), prevq] if prevq is not None else [nearS(q)]) + [q]; rawkeep.append(cur)
            else:
                if cur is not None and math.hypot((cur[-1][0]-q[0])*111320, (cur[-1][1]-q[1])*kx) < 12: cur.append(q); cur.append(nearS(q))
                cur = None
            prevq = q
    def straightjump(r):  # a long dead-straight piece off every road = a jump in the published shape, not a road
        L = math.hypot((r[0][0]-r[-1][0])*111320, (r[0][1]-r[-1][1])*kx)
        if L < 300: return False
        ax, ay, bx, by = r[0][1]*kx, r[0][0]*111320, r[-1][1]*kx, r[-1][0]*111320
        return max(abs((bx-ax)*(ay-q[0]*111320) - (ax-q[1]*kx)*(by-ay))/L for q in r) < 8
    def onroad(q):
        if tree is None: return False
        dd, _ = tree.query((q[0]*111320, q[1]*kx)); return dd < 25
    def plen(r): return sum(math.hypot((a[0]-b[0])*111320, (a[1]-b[1])*kx) for a, b in zip(r, r[1:]))
    def shadow(r):  # every point of the piece has a drawn road running the same way within 35 m: it's that road, offset
        if tree is None or len(r) < 2: return False
        L = math.hypot((r[-1][0]-r[0][0])*111320, (r[-1][1]-r[0][1])*kx) or 1; rx, ry = (r[-1][1]-r[0][1])*kx/L, (r[-1][0]-r[0][0])*111320/L
        nb = tree.query_ball_point(np.array([(q[0]*111320, q[1]*kx) for q in r]), 25)
        return all(any(abs(SD[j][0]*rx + SD[j][1]*ry) > 0.8 for j in js) for js in nb)
    rawkeep = [r for r in rawkeep if not shadow(r)]
    if os.environ.get('NO_RAW') == '1': rawkeep = []  # shapes that only join the stops (Nantes): their off-road pieces are never real roads
    # a short piece joined to nothing at either end is a stray fragment of the published shape, not a road: dropped
    rawkeep = [r for r in rawkeep if len(r) > 1 and math.hypot((r[0][0]-r[-1][0])*111320, (r[0][1]-r[-1][1])*kx) > 10 and not straightjump(r)
               and (plen(r) > 150 or onroad(r[0]) or onroad(r[-1]))]
    # the kept pieces join the road network: their points are added as edges, ends snapped onto the nearest drawn point within 15 m,
    # so they continue the lines they leave and rejoin (no hairline gaps) and identical pieces collapse into one
    if rawkeep:
        nodes = list(adj); nt = cKDTree(np.array([(u[0]*111320, u[1]*kx) for u in nodes]))
        def snapn(q):
            dd, j = nt.query((q[0]*111320, q[1]*kx)); return nodes[j] if dd < 15 else (round(q[0], 5), round(q[1], 5))
        for r in rawkeep:
            pts = [snapn(r[0])] + [(round(q[0], 5), round(q[1], 5)) for q in r[1:-1]] + [snapn(r[-1])]
            for u, v in zip(pts, pts[1:]):
                if u != v: adj[u].add(v); adj[v].add(u)
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
    T = collections.defaultdict(list)
    tk = lambda q: f"{math.floor(q[0]*10)}_{math.floor(q[1]*10)}"
    for line in [dp(l, 2.5) for l in lines]:
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
