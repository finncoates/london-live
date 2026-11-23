# Tidy the National Rail map built by nr_skel.py (its raw runs, RAW_OUT=…pkl) and write the tiles:
# short pieces left dangling at junctions are dropped, and a line that stops just short of another is joined to it.
#   python3 -I nr_tidy.py allp.pkl outdir
import sys, os, json, math, pickle, collections
import numpy as np
from scipy.spatial import cKDTree
raw, out = sys.argv[1:3]; os.makedirs(out, exist_ok=True)
WORLD = 256 * 2**15
def ll(x, y): return (math.degrees(math.atan(math.sinh(math.pi * (1 - 2*y/WORLD)))), x / WORLD * 360 - 180)
runs = [[(q[0], q[1]) for q in r] for r in pickle.load(open(raw, 'rb'))]
MPP = 1.85  # metres per pixel in Britain (about; ~3 m at the equator scale × cos 52°)
plen = lambda r: sum(math.hypot(b[0]-a[0], b[1]-a[1]) for a, b in zip(r, r[1:]))
def index(runs):
    P = []; O = []
    for i, r in enumerate(runs):
        for a, b in zip(r, r[1:]):
            n = max(1, int(math.hypot(b[0]-a[0], b[1]-a[1]) // 1))
            for t in range(n + 1): P.append((a[0] + (b[0]-a[0])*t/n, a[1] + (b[1]-a[1])*t/n)); O.append(i)
    return cKDTree(np.array(P)), np.array(P), np.array(O)
def touches(tree, O, i, q, rad):
    return any(O[j] != i for j in tree.query_ball_point(q, rad))
# 1. merge runs end to end where they meet exactly (cell edges), so a line's length is its whole length
for it in range(3):
    tree, P, O = index(runs); drop = set(); n0 = len(runs)
    for i, r in enumerate(runs):
        if i in drop: continue
        L = plen(r) * MPP
        if L > 100: continue
        a, b = r[0], r[-1]
        ta, tb = touches(tree, O, i, a, 3), touches(tree, O, i, b, 3)
        if not (ta and tb): drop.add(i)  # a short piece with a loose end: junction clutter
    runs = [r for i, r in enumerate(runs) if i not in drop]
    print('pass', it, 'dropped', n0 - len(runs), flush=True)
# 2. a loose end within ~25 m of another line, roughly ahead: joined to it
tree, P, O = index(runs); add = []
for i, r in enumerate(runs):
    if len(r) < 2: continue
    for end, prev in ((r[-1], r[-2]), (r[0], r[1])):
        if touches(tree, O, i, end, 3): continue
        dx, dy = end[0]-prev[0], end[1]-prev[1]; L = math.hypot(dx, dy) or 1; dx, dy = dx/L, dy/L
        best = None
        for j in tree.query_ball_point(end, 15 / MPP):
            if O[j] == i: continue
            vx, vy = P[j][0]-end[0], P[j][1]-end[1]; d = math.hypot(vx, vy)
            if d < 0.5: continue
            if (vx*dx + vy*dy)/d < math.cos(math.radians(35)): continue
            if best is None or d < best[0]: best = (d, j)
        if best: add.append([end, tuple(P[best[1]])])
runs += add; print(len(add), 'loose ends joined', len(runs), 'runs', flush=True)
def dp(p, eps):
    if len(p) < 3: return p
    a, b = np.array(p[0]), np.array(p[-1]); d = b - a; L = np.hypot(*d) or 1e-9; Q = np.array(p)
    e = np.abs(d[0]*(a[1]-Q[:, 1]) - d[1]*(a[0]-Q[:, 0])) / L; i = int(e.argmax())
    return [p[0], p[-1]] if e[i] <= eps else dp(p[:i+1], eps)[:-1] + dp(p[i:], eps)
T = collections.defaultdict(list); tk = lambda q: f"{math.floor(q[0]*2)}_{math.floor(q[1]*2)}"
for r in runs:
    p = [[round(v, 5) for v in ll(x, y)] for x, y in dp(r, 0.5)]
    T[tk(p[0])].append(p)
for f in os.listdir(out): os.remove(os.path.join(out, f))
for t, ps in T.items(): json.dump(ps, open(os.path.join(out, t + '.json'), 'w'), separators=(',', ':'))
ov = [[[round(v, 4) for v in ll(x, y)] for x, y in dp(r, 26)] for r in runs if plen(r) * MPP > 30]
json.dump([p for p in ov if len(p) > 1], open(os.path.join(out, 'all.json'), 'w'), separators=(',', ':'))
print(len(runs), 'runs,', len(T), 'tiles', os.path.getsize(os.path.join(out, 'all.json')), 'bytes overview')
