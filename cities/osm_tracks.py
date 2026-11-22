import json, math, heapq, urllib.request, collections, sys, os
ways = json.load(open('rails.json'))
LINES = {'tube': 'bakerloo,central,circle,district,hammersmith-city,jubilee,metropolitan,northern,piccadilly,victoria,waterloo-city',
         'overground': 'liberty,lioness,mildmay,suffragette,weaver,windrush', 'elizabeth': 'elizabeth', 'dlr': 'dlr', 'tram': 'tram'}
ALLOW = {'tube': {'subway', 'rail'}, 'overground': {'rail'}, 'elizabeth': {'rail', 'subway'}, 'dlr': {'light_rail', 'rail'}, 'tram': {'tram', 'light_rail'}}
def d(a, b): return math.hypot((a[0]-b[0])*111320, (a[1]-b[1])*111320*math.cos(math.radians(a[0])))
def graph(types):
    adj = collections.defaultdict(list); pos = {}
    for w in ways:
        if w['r'] not in types: continue
        for i in range(1, len(w['id'])):
            a, b = w['id'][i-1], w['id'][i]; pos[a] = w['p'][i-1]; pos[b] = w['p'][i]; L = d(w['p'][i-1], w['p'][i])
            adj[a].append((b, L)); adj[b].append((a, L))
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
    return [n for _, n in sorted(out)[:25]]
def route(adj, pos, A, B, limit):
    src = set(A); dst = set(B); dist = {n: 0 for n in A}; prev = {}; pq = [(0, n) for n in A]; heapq.heapify(pq)
    while pq:
        c, u = heapq.heappop(pq)
        if c > dist.get(u, 1e18): continue
        if u in dst:
            path = [u]
            while path[-1] in prev: path.append(prev[path[-1]])
            return c, [pos[x] for x in reversed(path)]
        if c > limit: return None
        for v, w in adj[u]:
            nc = c + w
            if nc < dist.get(v, 1e18): dist[v] = nc; prev[v] = u; heapq.heappush(pq, (nc, v))
    return None
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
        LIM = {'ratio':1.3 if under else 1.7, 'turn':75 if under else (170 if mode == 'tram' else 140), 'end':250 if under else 300}
        for a, b in pairs:
            if a not in stops or b not in stops: continue
            pa, pb = stops[a], stops[b]; straight = d(pa, pb); good = None
            for (adj, pos, grid) in ([SUBG, (adj0, pos0, grid0)] if mode == 'tube' else [(adj0, pos0, grid0)]):
                for r in (250, 500):
                    A, B = near(grid, pos, pa, r), near(grid, pos, pb, r)
                    res = route(adj, pos, A, B, straight*1.7 + 400) if A and B else None
                    if not res: continue
                    path = res[1]
                    ia = min(range(len(path)), key=lambda k: d(path[k], pa)); ib = min(range(len(path)), key=lambda k: d(path[k], pb))
                    if ib > ia: path = path[ia:ib+1]
                    if d(path[0], pa) > LIM['end'] or d(path[-1], pb) > LIM['end']: continue
                    # stations are points on the surface: start/end on the track itself, not with a jog out to the station dot
                    pts = dp([list(x) for x in path]) if len(path) > 1 else None
                    if not pts or len(pts) < 2: continue
                    pts = [list(pa)] + pts[1:-1] + [list(pb)] if len(pts) > 2 else [list(pa), list(pb)]
                    L = sum(d(pts[k-1], pts[k]) for k in range(1, len(pts)))
                    if L <= straight*LIM['ratio'] + 120 and maxturn(pts) < LIM['turn']: good = pts; break
                if good: break
            if good: segs.append([a, b, [[round(x, 5), round(y, 5)] for x, y in good]]); stats['ok'] += 1
            else: stats['straight'] += 1; stats['straight:' + lid] += 1
        out[lid] = segs
        print(lid, len(pairs), 'pairs', sum(1 for s in segs), 'on track', flush=True)
json.dump(out, open('/home/user/london-live/cities/london-tracks.json', 'w'), separators=(',', ':'))
print(stats.most_common(30), os.path.getsize('/home/user/london-live/cities/london-tracks.json'))
