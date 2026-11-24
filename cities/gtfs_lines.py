# Bake a city's rail/metro/tram (and optionally ferry) line shapes from a GTFS zip into a small JSON file.
# usage: python3 gtfs_lines.py feed.zip out.json "0:tram,1:metro,109:train,2:train,4:ferry" [route_short_name_filter_regex]
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace'); _s.stderr.reconfigure(encoding='utf-8', errors='replace')  # Windows console: never crash on a name
import os, sys, zipfile, csv, io, json, math, re, collections
zf, out, typemap = sys.argv[1], sys.argv[2], dict(x.split(':') for x in sys.argv[3].split(','))
COL = {'tram':'#00985F', 'metro':'#FF6319', 'train':'#8C4799', 'ferry':'#00B9E4', 'cable':'#E21836'}
if len(sys.argv) > 4 and sys.argv[4]: COL.update(json.loads(sys.argv[4]))
BOX = [float(x) for x in sys.argv[5].split(',')] if len(sys.argv) > 5 else None  # south,west,north,east
USE_RC = os.environ.get('USE_ROUTE_COLOR') == '1'
z = zipfile.ZipFile(zf)
rd = lambda n: csv.DictReader(io.TextIOWrapper(z.open(n), 'utf-8-sig'))
routes = {}
for r in rd('routes.txt'):
    t = r['route_type']
    if t in typemap: routes[r['route_id']] = (typemap[t], r.get('route_short_name') or r.get('route_long_name'), r.get('route_color'))
count = collections.Counter(); shape_route = {}
for t in rd('trips.txt'):
    if t['route_id'] in routes and t.get('shape_id'):
        count[t['shape_id']] += 1; shape_route[t['shape_id']] = (t['route_id'], t.get('direction_id', '0'))
pts = collections.defaultdict(list)
for s in rd('shapes.txt'):
    if s['shape_id'] in shape_route: pts[s['shape_id']].append((int(s['shape_pt_sequence']), float(s['shape_pt_lat']), float(s['shape_pt_lon'])))
def length(p): return sum(math.hypot((p[i][0]-p[i-1][0])*111320, (p[i][1]-p[i-1][1])*111320*math.cos(math.radians(p[i][0]))) for i in range(1, len(p)))
def dp(p, eps):  # closed loops (a ring line, a circular bus route) split at their farthest point first: measured against
    # a line from a point to itself, the whole loop would collapse to nothing (Copenhagen's M3 did)
    if len(p) > 3 and abs(p[0][0] - p[-1][0]) < 2e-5 and abs(p[0][1] - p[-1][1]) < 3e-5:
        k = max(range(len(p)), key=lambda i: (p[i][0] - p[0][0])**2 + ((p[i][1] - p[0][1])*0.65)**2)
        if 0 < k < len(p) - 1: return _dp_open(p[:k+1], eps)[:-1] + _dp_open(p[k:], eps)
    return _dp_open(p, eps)
_dp_loop = True
def _dp_open(p, eps):  # Douglas-Peucker in metres
    if len(p) < 3: return p
    k = math.cos(math.radians(p[0][0])); a, b = p[0], p[-1]
    ax, ay, bx, by = a[1]*k*111320, a[0]*111320, b[1]*k*111320, b[0]*111320; L = math.hypot(bx-ax, by-ay) or 1e-9
    best, bi = 0, 0
    for i in range(1, len(p)-1):
        x, y = p[i][1]*k*111320, p[i][0]*111320
        d = abs((bx-ax)*(ay-y) - (ax-x)*(by-ay))/L
        if d > best: best, bi = d, i
    if best <= eps: return [a, b]
    return dp(p[:bi+1], eps)[:-1] + dp(p[bi:], eps)
# per route: the most-used shapes (main services), plus every other one that adds at least 300 m of route not yet drawn
# (a branch: tram A to Floirac Dravemont, RER C to Dourdan; judged by length, not share: a long shape with a short
# branch is mostly overlap, and was dropped)
by_route = collections.defaultdict(list)
for sid, (rid, d) in shape_route.items(): by_route[rid].append(sid)
lines = []
GLOBAL = os.environ.get('GLOBAL_DEDUP') == '1'; gkept = set()
for rid, sids in sorted(by_route.items(), key=lambda kv: -sum(count[x] for x in kv[1])):
    kind, name, col = routes[rid]
    sids.sort(key=lambda s: -count[s]); keep = []
    for s in sids[:60]:
        p = [(la, lo) for _, la, lo in sorted(pts[s])]
        if BOX:  # keep the longest run inside the box
            runs, cur = [], []
            for q in p:
                if BOX[0] <= q[0] <= BOX[2] and BOX[1] <= q[1] <= BOX[3]: cur.append(q)
                elif cur: runs.append(cur); cur = []
            if cur: runs.append(cur)
            p = max(runs, key=len) if runs else []
        if len(p) < 2: continue
        # skip shapes that add little to the ones already kept (other direction, short workings)
        kept_pts = gkept if GLOBAL else {(round(la, 3), round(lo, 3)) for q in keep for la, lo in q}
        isnew = [(round(la, 3), round(lo, 3)) not in kept_pts for la, lo in p]
        newlen = sum(length([p[i-1], p[i]]) for i in range(1, len(p)) if isnew[i] and isnew[i-1])
        if (keep or GLOBAL) and newlen < 300: continue
        keep.append(p)
        if GLOBAL: gkept.update((round(la, 3), round(lo, 3)) for la, lo in p)
    for p in keep:
        q = dp(p, float(os.environ.get("EPS", "3")))
        lines.append({'name':name, 'kind':kind, 'col':('#' + col) if (col and USE_RC) else COL[kind], 'pts':[[round(la, 5), round(lo, 5)] for la, lo in q]})
json.dump({'lines':lines}, open(out, 'w'), separators=(',', ':'))
print(len(lines), 'lines', sum(len(l['pts']) for l in lines), 'points', collections.Counter(l['kind'] for l in lines))
