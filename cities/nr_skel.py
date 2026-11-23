# National Rail network as one centreline per railway corridor, following the real tracks (OpenStreetMap railway=rail).
# All passenger-line tracks are painted on a fine grid (Web Mercator zoom 15: ~3 m pixels), widened so that tracks
# running side by side (double / quadruple track, station throats) merge, then thinned to their centreline
# (skeleton) and traced back into lines. Junction curves, branches and corridors stay where the tracks are, with no gaps.
#   python3 -I nr_skel.py rails_all.pkl outdir        (rails_all.pkl: [(way id, tags, [(node, lat, lon)…])…])
#   -> outdir/<lat2>_<lon2>.json (0.5° tiles) + outdir/all.json (overview, ~80 m)
import sys, os, json, math, pickle, collections
import numpy as np
from scipy import ndimage
from skimage.morphology import skeletonize
from skimage.draw import line as dline
W, out = sys.argv[1:3]; os.makedirs(out, exist_ok=True)
R_M = float(os.environ.get('R_M', '14')); C_M = float(os.environ.get('C_M', '35')); HOLE_M2 = float(os.environ.get('HOLE_M2', '40000')); SIG_M = float(os.environ.get('SIG_M', '10'))  # tracks closer than ~2×this merge into one corridor
WORLD = 256 * 2**15
px = lambda la, lo: ((lo + 180) / 360 * WORLD, (1 - math.log(math.tan(math.radians(la)) + 1/math.cos(math.radians(la))) / math.pi) / 2 * WORLD)
def ll(x, y): return (math.degrees(math.atan(math.sinh(math.pi * (1 - 2*y/WORLD)))), x / WORLD * 360 - 180)
def keep(t):
    if t.get('railway') != 'rail' or t.get('service') or t.get('railway:preserved') == 'yes': return False
    if t.get('usage') not in ('main', 'branch', None): return False
    if t.get('ref') == 'XRC' or (t.get('tunnel') and 'Elizabeth' in (t.get('name') or '')): return False  # Elizabeth line core tunnels: drawn in purple
    return True
ways = [[px(la, lo) for _, la, lo in p] for _, t, p in pickle.load(open(W, 'rb')) if keep(t)]
ways = [w for w in ways if len(w) > 1 and 49.8 < ll(*w[0])[0] < 61 and ll(*w[0])[1] > -8.7]
print(len(ways), 'ways', flush=True)
CELL = 0.1; MARGIN = 340  # px (~1 km: wide enough that both sides of a cell edge see the same shapes, so lines meet there)
cells = collections.defaultdict(list)
for i, w in enumerate(ways):
    for a, b in zip(w, w[1:]):
        for q in (a, b, ((a[0]+b[0])/2, (a[1]+b[1])/2)):
            la, lo = ll(*q); cells[(math.floor(la/CELL), math.floor(lo/CELL))].append(i)
N8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
def dp(p, eps):
    if len(p) < 3: return p
    a, b = np.array(p[0]), np.array(p[-1]); d = b - a; L = np.hypot(*d) or 1e-9; P = np.array(p)
    e = np.abs(d[0]*(a[1]-P[:, 1]) - d[1]*(a[0]-P[:, 0])) / L; i = int(e.argmax())
    return [p[0], p[-1]] if e[i] <= eps else dp(p[:i+1], eps)[:-1] + dp(p[i:], eps)
BOX = [float(v) for v in os.environ['BOX'].split(',')] if os.environ.get('BOX') else None  # s,w,n,e: a test area only
def cell(key):
    ci, cj = key; allp = []
    x0, y1 = px(ci*CELL, cj*CELL); x1, y0 = px((ci+1)*CELL, (cj+1)*CELL)  # cell in pixels (y grows south)
    X0, Y0 = int(x0) - MARGIN, int(y0) - MARGIN; X1, Y1 = int(x1) + MARGIN, int(y1) + MARGIN
    mpp = 40075016.7 * math.cos(math.radians((ci+0.5)*CELL)) / WORLD; r = R_M / mpp
    img = np.zeros((Y1-Y0, X1-X0), bool)
    # every way near this cell (its neighbours' too, for the margin)
    near = set()
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1): near |= set(cells.get((ci+di, cj+dj), []))
    for i in near:
        w = ways[i]
        for a, b in zip(w, w[1:]):
            rr, cc = dline(int(round(a[1]-Y0)), int(round(a[0]-X0)), int(round(b[1]-Y0)), int(round(b[0]-X0)))
            ok = (rr >= 0) & (rr < img.shape[0]) & (cc >= 0) & (cc < img.shape[1]); img[rr[ok], cc[ok]] = True
    if not img.any(): return []
    # work only on the part of the window that has tracks (padded well beyond the widening)
    ys_, xs_ = np.nonzero(img); pad = int(2*(r + C_M/mpp)) + 8
    cy0, cy1 = max(0, ys_.min() - pad), min(img.shape[0], ys_.max() + pad + 1); cx0, cx1 = max(0, xs_.min() - pad), min(img.shape[1], xs_.max() + pad + 1)
    img = img[cy0:cy1, cx0:cx1]; Y0 += cy0; X0 += cx0
    blob = ndimage.distance_transform_edt(~img) <= r
    # close narrow gaps between corridors that run close together (station fans like Clapham Junction): dilate, then erode back
    c = C_M / mpp; big = ndimage.distance_transform_edt(~blob) <= c; blob = ndimage.distance_transform_edt(big) > c
    # fill small enclosed holes (between tracks in a station); big loops (triangles of lines, curves) stay
    lab, nl = ndimage.label(~blob); sizes = ndimage.sum(np.ones_like(lab), lab, range(nl + 1)); edge = set(np.unique(np.r_[lab[0], lab[-1], lab[:, 0], lab[:, -1]]).tolist())
    small = [k for k in range(1, nl + 1) if k not in edge and sizes[k] * mpp * mpp < HOLE_M2]
    if small: blob |= np.isin(lab, small)
    sk = skeletonize(blob)
    ys, xs = np.nonzero(sk); S = set(zip(ys.tolist(), xs.tolist()))
    nb = lambda q: [(q[0]+a, q[1]+b) for a, b in N8 if (q[0]+a, q[1]+b) in S]
    deg = {q: len(nb(q)) for q in S}
    # trace edges between nodes (degree != 2)
    seen = set(); edges = []
    def walk(a, b):
        e = [a, b]; seen.add(frozenset((a, b)))
        while deg[e[-1]] == 2:
            n = [q for q in nb(e[-1]) if q != e[-2] and frozenset((e[-1], q)) not in seen]
            if not n: break
            seen.add(frozenset((e[-1], n[0]))); e.append(n[0])
        return e
    for q in S:
        if deg[q] != 2:
            for n in nb(q):
                if frozenset((q, n)) not in seen: edges.append(walk(q, n))
    for q in S:  # closed loops
        for n in nb(q):
            if frozenset((q, n)) not in seen: edges.append(walk(q, n))
    # prune short spurs (corners of the widened tracks), twice
    for _ in range(2):
        ends = collections.Counter(); [ends.update((e[0], e[-1])) for e in edges]
        dgn = collections.Counter()
        for e in edges: dgn[e[0]] += 1; dgn[e[-1]] += 1
        edges = [e for e in edges if not ((dgn[e[0]] == 1) != (dgn[e[-1]] == 1) and len(e) * mpp < 3.2 * R_M)]
    # merge edges through degree-2 joints left by pruning
    dgn = collections.defaultdict(list)
    for k, e in enumerate(edges): dgn[e[0]].append(k); dgn[e[-1]].append(k)
    used = set(); lines = []
    for k, e in enumerate(edges):
        if k in used: continue
        used.add(k); ln = list(e)
        for side in (0, 1):
            while True:
                end = ln[-1]; nx = [j for j in dgn[end] if j not in used]
                if len(dgn[end]) != 2 or not nx: break
                j = nx[0]; used.add(j); f = edges[j]; ln += (f if f[0] == end else f[::-1])[1:]
            ln.reverse()
        lines.append(ln)
    # keep the parts inside this cell (one pixel beyond, so neighbouring cells meet)
    inside = lambda q: x0 <= q[1]+X0 < x1 and y0 <= q[0]+Y0 < y1
    sig = SIG_M / mpp
    def smooth(ln):  # Gaussian along the line (no pixel steps); the ends stay put so lines still meet at junctions
        if len(ln) < 5: return [(float(q[1]), float(q[0])) for q in ln]
        A = np.array(ln, float); n = len(A); sg = min(sig, n / 4)
        S = np.c_[ndimage.gaussian_filter1d(A[:, 1], sg, mode='nearest'), ndimage.gaussian_filter1d(A[:, 0], sg, mode='nearest')]
        k = np.arange(n); w = np.clip(np.minimum(k, n - 1 - k) / (2*sg), 0, 1)[:, None]
        B = A[:, ::-1] * (1 - w) + S * w
        return [tuple(q) for q in B]
    for ln in lines:
        sm = smooth(ln); run = []; ln = [(sm[k][0]+X0+0.5, sm[k][1]+Y0+0.5, inside(q)) for k, q in enumerate(ln)]
        for k, q in enumerate(ln):
            if q[2]:
                if not run and k: run.append(ln[k-1])
                run.append(q)
            elif run: run.append(q); allp.append(run) if len(run) > 1 else None; run = []
        if len(run) > 1: allp.append(run)
    return allp
from multiprocessing import Pool
keys = [k for k in cells if not BOX or (BOX[0] - 1e-9 <= k[0]*CELL < BOX[2] and BOX[1] - 1e-9 <= k[1]*CELL < BOX[3])]
allp = []
with Pool(int(os.environ.get('PROCS', '4'))) as pool:
    for n, r in enumerate(pool.imap_unordered(cell, keys, chunksize=4)):
        allp += r
        if n % 200 == 0: print(n, '/', len(keys), 'cells', flush=True)
T = collections.defaultdict(list); tk = lambda q: f"{math.floor(q[0]*2)}_{math.floor(q[1]*2)}"; ov = []
for run in allp:
    p = dp([(x, y) for x, y, _ in run], 0.7)  # ~2 m
    p = [[round(v, 5) for v in ll(x, y)] for x, y in p]
    T[tk(p[0])].append(p)  # a run never leaves its 0.1° cell by more than a pixel, so it sits in one 0.5° tile
for f in os.listdir(out): os.remove(os.path.join(out, f))
for t, ps in T.items(): json.dump(ps, open(os.path.join(out, t + '.json'), 'w'), separators=(',', ':'))
# overview: the runs joined end to end where they meet, simplified to ~80 m
ov = [[[round(v, 4) for v in ll(x, y)] for x, y in dp([(x, y) for x, y, _ in run], 26)] for run in allp]
json.dump([p for p in ov if len(p) > 1], open(os.path.join(out, 'all.json'), 'w'), separators=(',', ':'))
print(len(allp), 'runs,', len(T), 'tiles', os.path.getsize(os.path.join(out, 'all.json')), 'bytes overview', flush=True)
