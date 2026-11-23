# National Rail map from the train services themselves (OpenStreetMap route=train relations): each service is drawn
# along the exact tracks it uses, longest services first; a stretch that runs alongside a line already drawn (the other
# track of a pair, fast and slow lines…) is not drawn again, and where a service leaves that line its own track is
# drawn from the point it parts, so junctions follow the real curves. Lines no service uses (freight, gaps in the OSM
# service data) are added afterwards the same way, if long enough.
#   python3 -I nr_routes.py rails_all.pkl rels.pkl outdir
import sys, os, json, math, pickle, collections
WP, RP, out = sys.argv[1:4]; os.makedirs(out, exist_ok=True)
W = {wid: (t, p) for wid, t, p in pickle.load(open(WP, 'rb'))}
R = pickle.load(open(RP, 'rb'))
COVER = 30.0; PAR = 70.0; STEP = 8.0; ANG = math.cos(math.radians(30)); CELL = 25.0
def drawable(t):
    return t.get('railway') == 'rail' and t.get('ref') != 'XRC' and not (t.get('tunnel') and 'Elizabeth' in (t.get('name') or ''))
def chain(ways):  # ordered way node lists -> continuous paths [(node, lat, lon)…]
    paths = []; cur = []; first = 0
    for nodes in ways:
        if not cur: cur = list(nodes); first = len(nodes); continue
        if cur[-1][0] == nodes[0][0]: cur += nodes[1:]
        elif cur[-1][0] == nodes[-1][0]: cur += nodes[::-1][1:]
        elif len(cur) == first and cur[0][0] in (nodes[0][0], nodes[-1][0]):
            cur = cur[::-1]; cur += (nodes if cur[-1][0] == nodes[0][0] else nodes[::-1])[1:]
        else: paths.append(cur); cur = list(nodes); first = len(nodes)
    if cur: paths.append(cur)
    return [p for p in paths if len(p) > 1]
xy = lambda la, lo: (lo * 111320 * math.cos(math.radians(la)), la * 111320)
def resample(p):  # every ~8 m along the path: (x, y, lat, lon)
    out = []
    for (_, la1, lo1), (_, la2, lo2) in zip(p, p[1:]):
        a = xy(la1, lo1); b = xy(la2, lo2); n = max(1, int(math.hypot(b[0]-a[0], b[1]-a[1]) // STEP))
        for k in range(n): t = k/n; out.append((a[0] + (b[0]-a[0])*t, a[1] + (b[1]-a[1])*t, la1 + (la2-la1)*t, lo1 + (lo2-lo1)*t))
    la, lo = p[-1][1], p[-1][2]; x, y = xy(la, lo); out.append((x, y, la, lo)); return out
G = collections.defaultdict(list)  # drawn samples: cell -> [(x, y, dx, dy, lat, lon)]
def near(x, y):
    cx, cy = int(x // CELL), int(y // CELL)
    for i in (-1, 0, 1):
        for j in (-1, 0, 1): yield from G.get((cx+i, cy+j), ())
def covered(x, y, dx, dy):  # the nearest drawn sample running the same way within COVER m (or None)
    best = None
    for q in near(x, y):
        d = math.hypot(q[0]-x, q[1]-y)
        if d < COVER and abs(q[2]*dx + q[3]*dy) >= ANG and (best is None or d < best[0]): best = (d, q)
    return best
def add(S):
    for k, s in enumerate(S):
        a = S[max(0, k-1)]; b = S[min(len(S)-1, k+1)]; dx, dy = b[0]-a[0], b[1]-a[1]; L = math.hypot(dx, dy) or 1
        G[(int(s[0] // CELL), int(s[1] // CELL))].append((s[0], s[1], dx/L, dy/L, s[2], s[3]))
runs = []
def draw(S, minlen):
    n = len(S); cov = [None]*n
    for k in range(n):
        a = S[max(0, k-1)]; b = S[min(n-1, k+1)]; dx, dy = b[0]-a[0], b[1]-a[1]; L = math.hypot(dx, dy) or 1
        cov[k] = covered(S[k][0], S[k][1], dx/L, dy/L)
    k = 0; new = []
    while k < n:
        if cov[k]: k += 1; continue
        j = k
        while j < n and not cov[j]: j += 1
        i0, i1 = k, j  # uncovered samples k..j-1
        def beside(t):  # within PAR m of anything drawn
            x, y = S[t][0], S[t][1]; cx, cy = int(x // CELL), int(y // CELL); R_ = int(PAR // CELL) + 1
            return any(math.hypot(q[0]-x, q[1]-y) < PAR for i in range(-R_, R_+1) for j in range(-R_, R_+1) for q in G.get((cx+i, cy+j), ()))
        parallel = i0 > 0 and i1 < n and all(beside(t) for t in range(i0, i1, 3))  # leaves a line and rejoins it, never far from it: another track of the same railway
        if not parallel and ((i1 - i0) * STEP >= minlen or (i0 == 0 and i1 == n)):
            # start/end where the service is closest to the line it leaves/joins (looking back up to ~60 m), joined to that line
            # where it leaves / joins a drawn line: blend from that line onto its own track over a gentle stretch
            # (≥150 m, longer the further apart), like a real turnout; no hooks or sharp corners
            def blend(rng):  # rng: covered sample indexes, from the drawn line towards the new part
                out = []; m = len(rng)
                for k, t in enumerate(rng):
                    w = (k + 1) / (m + 1); w = w*w*(3 - 2*w); q = cov[t][1]
                    out.append((q[0] + (S[t][0]-q[0])*w, q[1] + (S[t][1]-q[1])*w, q[4] + (S[t][2]-q[4])*w, q[5] + (S[t][3]-q[5])*w))
                return out
            def span(t0, step_):  # covered samples next to the new part, enough for a gentle blend
                off = cov[t0][0]; want = max(150.0, off * 18) / STEP; out = []; t = t0
                while 0 <= t < n and cov[t] and len(out) < want: out.append(t); t += step_
                return out
            pre = []; post = []
            if i0 > 0:
                r_ = span(i0 - 1, -1)[::-1]; q = cov[r_[0]][1]; pre = [(q[0], q[1], q[4], q[5])] + blend(r_)
            if i1 < n:
                r_ = span(i1, 1); q = cov[r_[-1]][1]; post = blend(r_[::-1])[::-1] + [(q[0], q[1], q[4], q[5])]
            seg = pre + S[i0:i1] + post
            if len(seg) > 1: new.append(seg)
        k = j
    for seg in new: add(seg); runs.append([(s[2], s[3]) for s in seg])
# 1. the services, longest first
paths = []
for rid, t, mem in R:
    ways = [[(n, la, lo) for n, la, lo in W[ref][1]] for ty, ref, role in mem if ty == 'w' and role in ('', 'forward', 'backward', 'main', 'line') and ref in W and drawable(W[ref][0])]
    for p in chain(ways): paths.append(resample(p))
paths.sort(key=len, reverse=True); print(len(paths), 'service paths', flush=True)
for i, S in enumerate(paths):
    draw(S, 40)
    if i % 200 == 0: print(i, len(runs), 'runs', flush=True)
# 2. running lines no service in the data uses (freight, missing services): only long uncovered stretches
def keep(t):
    return drawable(t) and not t.get('service') and t.get('railway:preserved') != 'yes' and t.get('usage') in ('main', 'branch', None)
# OSM splits a line into many short ways (bridges, junctions): join them end to end through points where just two meet
xw = [p for wid, (t, p) in W.items() if keep(t) and len(p) > 1]
ends = collections.defaultdict(list)
for i, p in enumerate(xw): ends[p[0][0]].append(i); ends[p[-1][0]].append(i)
used = set(); chains = []
for i in range(len(xw)):
    if i in used: continue
    used.add(i); c = list(xw[i])
    for _ in (0, 1):
        while True:
            nb = [j for j in ends[c[-1][0]] if j not in used]
            if len(ends[c[-1][0]]) != 2 or not nb: break
            j = nb[0]; used.add(j); q = xw[j]; c += (q if q[0][0] == c[-1][0] else q[::-1])[1:]
        c = c[::-1]
    chains.append(c)
print(len(xw), 'unused-line ways ->', len(chains), 'chains', flush=True)
extra = [resample(p) for p in chains]
extra = [S for S in extra if 49.8 < S[0][2] < 61 and S[0][3] > -8.7]
extra.sort(key=len, reverse=True); n0 = len(runs)
for S in extra: draw(S, 600)  # long enough to be a line of its own, not a platform road or a siding
print(len(runs) - n0, 'runs from lines without services', flush=True)
# output: 0.5° tiles (~1 m detail) + overview
def dp(p, eps):  # p in lat/lon, eps in metres
    if len(p) < 3: return p
    k = math.cos(math.radians(p[0][0])); ax, ay, bx, by = p[0][1]*k*111320, p[0][0]*111320, p[-1][1]*k*111320, p[-1][0]*111320
    L = math.hypot(bx-ax, by-ay) or 1e-9; best, bi = 0, 0
    for i in range(1, len(p)-1):
        x, y = p[i][1]*k*111320, p[i][0]*111320; d = abs((bx-ax)*(ay-y) - (ax-x)*(by-ay))/L
        if d > best: best, bi = d, i
    return [p[0], p[-1]] if best <= eps else dp(p[:bi+1], eps)[:-1] + dp(p[bi:], eps)
sys.setrecursionlimit(100000)
T = collections.defaultdict(list); tk = lambda q: f"{math.floor(q[0]*2)}_{math.floor(q[1]*2)}"
for r in runs:
    p = [[round(a, 5), round(b, 5)] for a, b in dp(r, 1.0)]; run = [p[0]]
    for q in p[1:]:
        run.append(q)
        if tk(q) != tk(run[0]): T[tk(run[0])].append(run); run = [q]
    if len(run) > 1: T[tk(run[0])].append(run)
for f in os.listdir(out): os.remove(os.path.join(out, f))
for t, ps in T.items(): json.dump(ps, open(os.path.join(out, t + '.json'), 'w'), separators=(',', ':'))
ov = [[[round(a, 4), round(b, 4)] for a, b in dp(r, 80)] for r in runs]
json.dump([p for p in ov if len(p) > 1], open(os.path.join(out, 'all.json'), 'w'), separators=(',', ':'))
print(len(runs), 'runs,', len(T), 'tiles', os.path.getsize(os.path.join(out, 'all.json')), 'bytes overview', flush=True)
