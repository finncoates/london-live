# Bus route map, cleaned: one line per road corridor.
# The matched route map (busnet2.py) draws every carriageway, slip road and ramp a bus uses, so dual carriageways and
# motorways come out as bundles of near-parallel lines with short stubs and wiggles at junctions. This redraws each
# 0.1-degree tile from that geometry: rasterise on a global pixel grid (~3 m), widen every line so carriageway pairs
# and slip-road bundles merge into one band, fill thin slivers between them, take the centre line (skeleton), drop
# short spurs, smooth and simplify. Tiles are processed with a wide margin and cut exactly on the tile edge, so
# neighbouring tiles meet at the same points (no seams).
#   python3 busnet3.py SRC_DIR OUT_DIR [s w n e] [-j N]
import sys, os, json, math, collections
import numpy as np
from scipy import ndimage as ndi
from skimage.morphology import skeletonize

PY, PX = 37000, 22000          # pixels per degree (lat ~3.0 m, lon ~2.9 m at 55N); 0.1 degree = 3700 x 2200 px exactly
TY, TX = PY // 10, PX // 10
MARGIN = 200                   # px each side (~600 m)
R = 11.0                       # m: half-width of the band each line is widened to (lines up to ~22 m apart merge)
HOLE_W = 9.0                   # m: slivers between lines narrower than ~2x this (inscribed radius) are filled
HOLE_A = 900.0                 # m2: small holes always filled (tiny loops at junctions)
HOLE_MAXEXT = 450.0            # m: holes longer than this are never filled (keeps tiles consistent at seams)
SPUR = 80.0                    # m: dead-end spurs shorter than this are removed
STUB = 250.0                   # m: dead-end spurs up to this long are removed when no bus stop is near their end (a real terminus has one)
STOP_NEAR = 60.0               # m
ISLAND = 80.0                  # m: pieces joined to nothing shorter than this are removed
SMOOTH = 5                     # px half-window of the moving average
DP_EPS = 2.0                   # m
MAXSEG = 80.0                  # m: longest straight piece (the page finds a bus's road by segment midpoints)

STOPS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stops')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from greater_london import in_london
def stops_near(a, b):  # bus stops (0.05-degree tiles) around tile a_b; None when the area has no stop tiles at all
    pts = []; seen = False
    for la in range(a * 2 - 2, a * 2 + 4):
        for lo in range(b * 2 - 2, b * 2 + 4):
            f = os.path.join(STOPS, f'{la}_{lo}.json')
            if os.path.exists(f):
                seen = True
                try: pts += [(s[2], s[3]) for s in json.load(open(f))['stops']]
                except Exception: pass
    return pts if seen else None

def load(src, a, b):
    f = os.path.join(src, f'{a}_{b}.json')
    return json.load(open(f)) if os.path.exists(f) else []

def process(src, a, b):
    r0, c0 = a * TY - MARGIN, b * TX - MARGIN; H, W = TY + 2 * MARGIN, TX + 2 * MARGIN
    lat0 = (a + 0.5) / 10; my = 111320.0 / PY; mx = 111320.0 * math.cos(math.radians(lat0)) / PX
    m = np.zeros((H, W), bool); any_ = False
    for da in (-1, 0, 1):
        for db in (-1, 0, 1):
            for p in load(src, a + da, b + db):
                q = np.array(p, float); rr = q[:, 0] * PY - r0; cc = q[:, 1] * PX - c0
                for i in range(len(q) - 1):
                    y0, x0, y1, x1 = rr[i], cc[i], rr[i + 1], cc[i + 1]
                    if max(y0, y1) < -2 or min(y0, y1) > H + 2 or max(x0, x1) < -2 or min(x0, x1) > W + 2: continue
                    n = int(max(abs(y1 - y0), abs(x1 - x0)) * 2) + 2; t = np.linspace(0, 1, n)
                    ys = (y0 + (y1 - y0) * t).astype(int); xs = (x0 + (x1 - x0) * t).astype(int)
                    k = (ys >= 0) & (ys < H) & (xs >= 0) & (xs < W)
                    if k.any(): m[ys[k], xs[k]] = True; any_ = True
    if not any_: return None
    # crop to occupied area (+ band) to save time; the crop keeps the global grid
    rows = np.flatnonzero(m.any(1)); cols = np.flatnonzero(m.any(0)); pad = int(R / min(my, mx)) + 4
    ra, rb = max(0, rows[0] - pad), min(H, rows[-1] + pad + 1); ca, cb = max(0, cols[0] - pad), min(W, cols[-1] + pad + 1)
    m = m[ra:rb, ca:cb]; r0 += ra; c0 += ca; H, W = m.shape
    border = lambda y, x: (r0 + y < a * TY - MARGIN + 3 or r0 + y > (a + 1) * TY + MARGIN - 4 or c0 + x < b * TX - MARGIN + 3 or c0 + x > (b + 1) * TX + MARGIN - 4)
    d = ndi.distance_transform_edt(~m, sampling=(my, mx)); band = d <= R
    # fill slivers / small holes that don't touch the window edge
    holes = ~band; lab, n = ndi.label(holes)
    if n:
        dh = ndi.distance_transform_edt(holes, sampling=(my, mx))
        idx = np.arange(1, n + 1)
        area = ndi.sum(np.ones_like(lab, np.float32), lab, idx) * my * mx
        inr = ndi.maximum(dh, lab, idx)
        sl = ndi.find_objects(lab)
        fill = np.zeros(n + 1, bool)
        for i in range(n):
            s = sl[i]; ys, xs = s
            ext = max((ys.stop - ys.start) * my, (xs.stop - xs.start) * mx)
            touches = ys.start == 0 or xs.start == 0 or ys.stop == H or xs.stop == W
            # a window edge cut by the crop is not the real window edge only if the hole is inside the band's bbox; holes at the crop edge are open ground
            if touches or ext > HOLE_MAXEXT: continue
            if area[i] < HOLE_A or inr[i] < HOLE_W: fill[i + 1] = True
        band |= fill[lab]
    sk = skeletonize(band)
    stops = stops_near(a, b); st = None
    if stops:
        from scipy.spatial import cKDTree
        st = cKDTree(np.array([((q[0] * PY - r0) * my, (q[1] * PX - c0) * mx) for q in stops]))
    def terminus(y, x):  # a stop near this dead end, or no stop data, or the London boundary (TfL routes carry on)
        if st is None: return True
        if st.query_ball_point((y * my, x * mx), STOP_NEAR): return True
        la, lo = (y + r0 + 0.5) / PY, (x + c0 + 0.5) / PX
        return any(in_london(la + dy / 111320, lo + dx / (111320 * math.cos(math.radians(la)))) for dy in (-150, 0, 150) for dx in (-150, 0, 150))
    return vectorise(sk, r0, c0, my, mx, border, a, b, terminus)

NB = [(-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1)]

def vectorise(sk, r0, c0, my, mx, border, a, b, terminus):
    H, W = sk.shape
    cnt = ndi.convolve(sk.astype(np.uint8), np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]], np.uint8), mode='constant')
    # crossing number: 0->1 transitions round the ring of 8
    P = np.pad(sk, 1).astype(np.int8); ring = [P[1 + dy:H + 1 + dy, 1 + dx:W + 1 + dx] for dy, dx in NB]
    cn = sum(((ring[i] == 0) & (ring[(i + 1) % 8] == 1)).astype(np.int8) for i in range(8))
    isnode = sk & ((cn != 2) | (cnt >= 4) | (cnt <= 1))
    nlab, nn = ndi.label(isnode, structure=np.ones((3, 3)))
    ys, xs = np.nonzero(sk)
    S = set((ys * W + xs).tolist())
    NL = {}; nys, nxs = np.nonzero(isnode)
    for y, x in zip(nys.tolist(), nxs.tolist()): NL[y * W + x] = int(nlab[y, x])
    cen = {}
    if nn:
        cy = ndi.mean(np.arange(H)[:, None] * np.ones((1, W)), nlab, np.arange(1, nn + 1)); cx = ndi.mean(np.ones((H, 1)) * np.arange(W)[None, :], nlab, np.arange(1, nn + 1))
        for i in range(nn): cen[i + 1] = (float(cy[i]), float(cx[i]))
    offs = [dy * W + dx for dy, dx in NB]
    def nbrs(p):
        y, x = divmod(p, W); out = []
        for (dy, dx), o in zip(NB, offs):
            if 0 <= y + dy < H and 0 <= x + dx < W and p + o in S: out.append(p + o)
        return out
    adjn = lambda p, q: abs(p // W - q // W) <= 1 and abs(p % W - q % W) <= 1
    visited = set(); edges = []; seenpair = set(); nextnode = [nn + 1]
    def newnode(p):
        k = nextnode[0]; nextnode[0] += 1; cen[k] = (float(p // W), float(p % W)); return k
    for p, L in NL.items():
        for q in nbrs(p):
            if q in NL:
                if NL[q] != L:
                    pr = (min(p, q), max(p, q))
                    if pr not in seenpair: seenpair.add(pr); edges.append([L, NL[q], [p, q]])
                continue
            if q in visited: continue
            path = [p, q]; visited.add(q); prev, cur = p, q; endL = None
            while True:
                nb = [n for n in nbrs(cur) if n != prev]
                nodes_ = [n for n in nb if n in NL and (NL[n] != L or len(path) > 3)]
                if nodes_:
                    nxt = next((n for n in nodes_ if NL[n] != L), nodes_[0]); path.append(nxt); endL = NL[nxt]; break
                cand = [n for n in nb if n not in NL and n not in visited]
                if not cand: break
                far = [n for n in cand if not adjn(n, prev)]
                nxt = far[0] if far else cand[0]
                for n in cand: visited.add(n)
                path.append(nxt); prev, cur = cur, nxt
            if endL is None: endL = newnode(path[-1])
            edges.append([L, endL, path])
    for p in S:  # closed loops with no node
        if p in NL or p in visited: continue
        path = [p]; visited.add(p); prev, cur = None, p
        while True:
            cand = [n for n in nbrs(cur) if n != prev and n not in NL and n not in visited]
            if not cand: break
            nxt = cand[0]
            for n in cand: visited.add(n)
            path.append(nxt); prev, cur = cur, nxt
        if len(path) > 3: k = newnode(p); path.append(p); edges.append([k, k, path])
    # pixel paths -> metric polylines (x east, y north, metres in a local frame); ends at the node centres
    def pt(p): y, x = divmod(p, W); return (float(y), float(x))
    E = {}
    for i, (u, v, path) in enumerate(edges):
        P_ = [pt(p) for p in path]; P_[0] = cen[u]; P_[-1] = cen[v]; E[i] = [u, v, P_]
    plen = lambda P_: sum(math.hypot((P_[j][0] - P_[j - 1][0]) * my, (P_[j][1] - P_[j - 1][1]) * mx) for j in range(1, len(P_)))
    def deg():
        D = collections.Counter()
        for u, v, _ in E.values(): D[u] += 1; D[v] += 1
        return D
    onborder = lambda k: border(*cen[k])
    def merge2():  # join chains through nodes with exactly two edges
        changed = True
        while changed:
            changed = False; D = deg(); inc = collections.defaultdict(list)
            for i, (u, v, _) in E.items(): inc[u].append(i); inc[v].append(i)
            for k, es in inc.items():
                if D[k] != 2 or len(es) != 2 or es[0] == es[1]: continue
                i, j = es
                if i not in E or j not in E: continue
                u1, v1, P1 = E[i]; u2, v2, P2 = E[j]
                if v1 != k: u1, v1, P1 = v1, u1, P1[::-1]
                if u2 != k: u2, v2, P2 = v2, u2, P2[::-1]
                del E[j]; E[i] = [u1, v2, P1 + P2[1:]]; changed = True; break
    merge2()
    for _ in range(4):
        D = deg(); cut = False
        for i in list(E):
            u, v, P_ = E[i]
            if u == v:
                if plen(P_) < 60: del E[i]; cut = True
                continue
            du, dv = D[u], D[v]
            if du == 1 and dv == 1:
                if plen(P_) < ISLAND and not onborder(u) and not onborder(v): del E[i]; cut = True
                continue
            for e, o in ((u, v), (v, u)):
                if D[e] == 1 and D[o] >= 3 and not onborder(e):
                    L_ = plen(P_)
                    if L_ < SPUR or (L_ < STUB and not terminus(*cen[e])): del E[i]; cut = True; break
        if not cut: break
        merge2()
    # smooth (moving average, ends fixed) -> lat/lon -> cut on the tile edges -> simplify
    out = []
    la0, la1, lo0, lo1 = a / 10, (a + 1) / 10, b / 10, (b + 1) / 10
    for u, v, P_ in E.values():
        A = np.array(P_)
        if len(A) > 2 * SMOOTH + 1:
            cs = np.cumsum(np.vstack([[0, 0], A]), 0); Bm = A.copy()
            for j in range(1, len(A) - 1):
                h = min(SMOOTH, j, len(A) - 1 - j); Bm[j] = (cs[j + h + 1] - cs[j - h]) / (2 * h + 1)
            A = Bm
        LL = np.column_stack([(A[:, 0] + r0 + 0.5) / PY, (A[:, 1] + c0 + 0.5) / PX])
        for piece in clip(LL, la0, la1, lo0, lo1):
            q = dp(piece, DP_EPS, my * PY, mx * PX)
            out.append(capseg(q, my * PY, mx * PX))
    return [[[round(x, 6), round(y, 6)] for x, y in p] for p in out if len(p) > 1]

def clip(LL, la0, la1, lo0, lo1):
    pieces = []; cur = []
    inside = lambda p: la0 <= p[0] < la1 and lo0 <= p[1] < lo1
    for i in range(len(LL)):
        p = tuple(LL[i])
        if i == 0:
            if inside(p): cur = [p]
            continue
        q = tuple(LL[i - 1])
        # Liang-Barsky on segment q->p
        t0, t1 = 0.0, 1.0; dy, dx = p[0] - q[0], p[1] - q[1]; ok = True
        for pp, qq in ((-dy, q[0] - la0), (dy, la1 - q[0]), (-dx, q[1] - lo0), (dx, lo1 - q[1])):
            if pp == 0:
                if qq < 0: ok = False; break
            else:
                t = qq / pp
                if pp < 0: t0 = max(t0, t)
                else: t1 = min(t1, t)
        if not ok or t0 > t1:
            if len(cur) > 1: pieces.append(cur)
            cur = []; continue
        A = (q[0] + dy * t0, q[1] + dx * t0); B = (q[0] + dy * t1, q[1] + dx * t1)
        if t0 > 0 or not cur:
            if len(cur) > 1: pieces.append(cur)
            cur = [A]
        cur.append(B)
        if t1 < 1:
            if len(cur) > 1: pieces.append(cur)
            cur = []
    if len(cur) > 1: pieces.append(cur)
    return pieces

def dp(p, eps, ky, kx):
    if len(p) < 3: return list(p)
    keep = [False] * len(p); keep[0] = keep[-1] = True; st = [(0, len(p) - 1)]
    while st:
        i, j = st.pop(); ax, ay, bx, by = p[i][1] * kx, p[i][0] * ky, p[j][1] * kx, p[j][0] * ky; L = math.hypot(bx - ax, by - ay) or 1e-9; best, bi = 0, -1
        for k in range(i + 1, j):
            x, y = p[k][1] * kx, p[k][0] * ky; d = abs((bx - ax) * (ay - y) - (ax - x) * (by - ay)) / L
            if d > best: best, bi = d, k
        if best > eps: keep[bi] = True; st += [(i, bi), (bi, j)]
    return [q for q, k in zip(p, keep) if k]

def capseg(p, ky, kx):
    out = [p[0]]
    for q in p[1:]:
        a = out[-1]; L = math.hypot((q[0] - a[0]) * ky, (q[1] - a[1]) * kx); n = int(L // MAXSEG) + 1
        for t in range(1, n): out.append((a[0] + (q[0] - a[0]) * t / n, a[1] + (q[1] - a[1]) * t / n))
        out.append(q)
    return out

def work(args):
    src, out, t = args; a, b = map(int, t.split('_'))
    try: res = process(src, a, b)
    except Exception as e: return t, 'ERR ' + repr(e)
    fn = os.path.join(out, t + '.json')
    if res: json.dump([[[round(x, 5), round(y, 5)] for x, y in p] for p in res], open(fn, 'w'), separators=(',', ':')); return t, len(res)
    return t, 0

if __name__ == '__main__':
    args = sys.argv[1:]; j = 4
    if '-j' in args: i = args.index('-j'); j = int(args[i + 1]); del args[i:i + 2]
    src, out = args[0], args[1]; os.makedirs(out, exist_ok=True)
    s, w, n, e = map(float, args[2:6]) if len(args) >= 6 else (-90, -180, 90, 180)
    have = {f[:-5] for f in os.listdir(src) if f.endswith('.json')}
    todo = set()
    for t in have:  # each source tile and its neighbours (a line may spill over a tile edge after cleaning)
        a, b = map(int, t.split('_'))
        if not (s * 10 <= a < n * 10 and w * 10 <= b < e * 10): continue
        for da in (-1, 0, 1):
            for db in (-1, 0, 1):
                if s * 10 <= a + da < n * 10 and w * 10 <= b + db < e * 10: todo.add(f'{a + da}_{b + db}')
    todo = sorted(todo)
    from multiprocessing import Pool
    done = 0
    with Pool(j) as P:
        for t, r in P.imap_unordered(work, [(src, out, t) for t in todo], chunksize=2):
            done += 1
            if isinstance(r, str): print(t, r, flush=True)
            if done % 200 == 0: print(done, '/', len(todo), flush=True)
    print('done', len(todo))
