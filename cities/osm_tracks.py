import json, math, heapq, itertools, urllib.request, collections, sys, os
ways = json.load(open('rails.json'))
LINES = {'tube': 'bakerloo,central,circle,district,hammersmith-city,jubilee,metropolitan,northern,piccadilly,victoria,waterloo-city',
         'overground': 'liberty,lioness,mildmay,suffragette,weaver,windrush', 'elizabeth': 'elizabeth', 'dlr': 'dlr', 'tram': 'tram', 'river': 'rb1,rb4,rb6,woolwich-ferry'}
ALLOW = {'tube': {'subway', 'rail'}, 'overground': {'rail'}, 'elizabeth': {'rail', 'subway'}, 'dlr': {'light_rail', 'rail'}, 'tram': {'tram', 'light_rail'}, 'river': {'river'}}
def d(a, b): return math.hypot((a[0]-b[0])*111320, (a[1]-b[1])*111320*math.cos(math.radians(a[0])))
def graph(types):
    adj = collections.defaultdict(list); pos = {}
    for w in ways:
        if w['r'] not in types: continue
        for i in range(1, len(w['id'])):
            a, b = w['id'][i-1], w['id'][i]; pa_, pb_ = w['p'][i-1], w['p'][i]; pos[a] = pa_; pos[b] = pb_; L = d(pa_, pb_); n = max(1, int(L // 30))
            last = a
            for k in range(1, n + 1):  # extra points every ~30 m on long straight track, so stations find the track right under them
                if k < n: cur = ('v', a, b, k); pos[cur] = [pa_[0] + (pb_[0]-pa_[0])*k/n, pa_[1] + (pb_[1]-pa_[1])*k/n]
                else: cur = b
                adj[last].append((cur, L/n)); adj[cur].append((last, L/n)); last = cur
    grid = collections.defaultdict(list)
    for n, p in pos.items(): grid[(int(p[0]*500), int(p[1]*300))].append(n)
    return adj, pos, grid
def near(grid, pos, p, r=250):
    gi, gj = int(p[0]*500), int(p[1]*300); out = []
    for i in range(gi-2, gi+3):
        for j in range(gj-2, gj+3):
            for n in grid.get((i, j), []):
                k = d(pos[n], p)
                if k < r: out.append((k, n))
    return [n for _, n in sorted(out)[:120]]
def route(adj, pos, A, B, limit, pa=None, pb=None):
    # start near station a, end near station b: the distance from each station to its track node counts (no skipping past the station)
    dist = {n: (d(pos[n], pa) if pa else 0) for n in A}; prev = {}; cnt = itertools.count(); pq = [(c, next(cnt), n) for n, c in dist.items()]; heapq.heapify(pq)
    dst = set(B); best = None
    while pq:
        c, _, u = heapq.heappop(pq)
        if c > dist.get(u, 1e18): continue
        if best and c >= best[0]: break
        if u in dst:
            tot = c + (d(pos[u], pb) if pb else 0)
            if not best or tot < best[0]: best = (tot, u)
        if c > limit: break
        for v, w in adj[u]:
            nc = c + w
            if nc < dist.get(v, 1e18): dist[v] = nc; prev[v] = u; heapq.heappush(pq, (nc, next(cnt), v))
    if not best: return None
    path = [best[1]]
    while path[-1] in prev: path.append(prev[path[-1]])
    return best[0], [pos[x] for x in reversed(path)]
ANCH = {}
def anchor(grid, pos, q):
    k = (id(grid), round(q[0], 6), round(q[1], 6))
    if k not in ANCH:
        nn = near(grid, pos, q, 60); ANCH[k] = (round(pos[nn[0]][0], 6), round(pos[nn[0]][1], 6)) if nn else None
    return ANCH[k]
def proj(path, q):  # nearest point on the polyline to q: (segment index, point)
    k = math.cos(math.radians(q[0])); best = None
    for i in range(1, len(path)):
        a, b = path[i-1], path[i]; ax, ay = (a[1]-q[1])*k, a[0]-q[0]; dx, dy = (b[1]-a[1])*k, b[0]-a[0]; L2 = dx*dx + dy*dy or 1e-18
        t = max(0, min(1, -(ax*dx + ay*dy)/L2)); x, y = ax + dx*t, ay + dy*t; dd = x*x + y*y
        if best is None or dd < best[0]: best = (dd, i, (round(a[0] + (b[0]-a[0])*t, 6), round(a[1] + (b[1]-a[1])*t, 6)))
    return best[1], best[2]
def cut(path, q, end):  # trim the path at the station's projection: end=0 keeps what follows it, end=1 what precedes it
    if len(path) < 2: return path
    i, p = proj(path, q)
    return [p] + list(path[i:]) if end == 0 else list(path[:i]) + [p]
def dp(p, eps=3):
    if len(p) < 3: return p
    k = math.cos(math.radians(p[0][0])); a, b = p[0], p[-1]
    ax, ay, bx, by = a[1]*k*111320, a[0]*111320, b[1]*k*111320, b[0]*111320; L = math.hypot(bx-ax, by-ay) or 1e-9
    best, bi = 0, 0
    for i in range(1, len(p)-1):
        x, y = p[i][1]*k*111320, p[i][0]*111320; dd = abs((bx-ax)*(ay-y) - (ax-x)*(by-ay))/L
        if dd > best: best, bi = dd, i
    if best <= eps: return [a, b]
    return dp(p[:bi+1], eps)[:-1] + dp(p[bi:], eps)
out = {}; stats = collections.Counter()
SUBG = graph({'subway'})
for mode, ids in LINES.items():
    adj0, pos0, grid0 = graph(ALLOW[mode])
    for lid in ids.split(','):
        pairs = {}; stops = {}
        for direction in ('outbound', 'inbound'):
            j = json.load(urllib.request.urlopen(urllib.request.Request(f'https://api.tfl.gov.uk/Line/{lid}/Route/Sequence/{direction}', headers={'User-Agent':'Mozilla/5.0 london-live-build'})))
            for seq in j.get('stopPointSequences', []):
                for s in seq['stopPoint']: stops[s['id']] = (s['lat'], s['lon'])
            for r in j.get('orderedLineRoutes', []):
                ids_ = r['naptanIds']
                for i in range(1, len(ids_)):
                    a, b = sorted((ids_[i-1], ids_[i])); pairs[(a, b)] = 1
        segs = []
        def maxturn(q):
            m = 0
            for k in range(1, len(q)-1):
                a1 = math.atan2(q[k][0]-q[k-1][0], (q[k][1]-q[k-1][1])*0.62); a2 = math.atan2(q[k+1][0]-q[k][0], (q[k+1][1]-q[k][1])*0.62)
                t = abs(math.atan2(math.sin(a2-a1), math.cos(a2-a1)))
                if min(d(q[k-1], q[k]), d(q[k], q[k+1])) > 15: m = max(m, t)
            return math.degrees(m)
        under = mode == 'tube' and lid != 'metropolitan'
        LIM = {'ratio':1.3 if under else (3.0 if mode == 'river' else 1.7), 'turn':75 if under else (179 if mode in ('tram', 'river') else 140), 'end':250 if under else (500 if mode == 'river' else 300)}
        for a, b in pairs:
            if a not in stops or b not in stops: continue
            pa, pb = stops[a], stops[b]; straight = d(pa, pb); good = None
            for (adj, pos, grid) in ([SUBG, (adj0, pos0, grid0)] if mode == 'tube' else [(adj0, pos0, grid0)]):
                for r in ((400, 700) if mode == 'river' else (250, 500)):
                    A, B = near(grid, pos, pa, r), near(grid, pos, pb, r)
                    res = route(adj, pos, A, B, straight*(3.2 if mode == 'river' else 1.7) + 400, pa, pb) if A and B else None
                    if not res: continue
                    path = res[1]
                    ia = min(range(len(path)), key=lambda k: d(path[k], pa)); ib = min(range(len(path)), key=lambda k: d(path[k], pb))
                    if ib > ia: path = path[ia:ib+1]
                    if d(path[0], pa) > LIM['end'] or d(path[-1], pb) > LIM['end']: continue
                    # start/end where the station projects onto the track (no jog out to the station pin, no V at the station)
                    path = cut(path, pa, 0); path = cut(path, pb, 1)
                    # every hop at a station starts/ends at the same point: the nearest point of track to the station
                    for end, st_ in ((0, pa), (1, pb)):
                        an = anchor(SUBG[2], SUBG[1], st_) if mode == 'tube' else anchor(grid0, pos0, st_)  # one anchor per station and line type
                        if an is None: continue
                        e = path[0] if end == 0 else path[-1]
                        if d(e, an) < 25: path = ([an] + list(path[1:])) if end == 0 else (list(path[:-1]) + [an])
                        else: path = ([an] + list(path)) if end == 0 else (list(path) + [an])
                    pts = dp([list(x) for x in path]) if len(path) > 1 else None
                    if not pts or len(pts) < 2: continue
                    L = sum(d(pts[k-1], pts[k]) for k in range(1, len(pts)))
                    if L <= straight*LIM['ratio'] + 120 and maxturn(pts) < LIM['turn']: good = pts; break
                if good: break
            if good: segs.append([a, b, [[round(x, 5), round(y, 5)] for x, y in good]]); stats['ok'] += 1
            else: stats['straight'] += 1; stats['straight:' + lid] += 1
        out[lid] = segs
        print(lid, len(pairs), 'pairs', sum(1 for s in segs), 'on track', flush=True)
json.dump(out, open('/home/user/london-live/cities/london-tracks.json', 'w'), separators=(',', ':'))
print(stats.most_common(30), os.path.getsize('/home/user/london-live/cities/london-tracks.json'))
