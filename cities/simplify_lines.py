# Lines thinned without visible change: points within TOL metres of the straight line between their neighbours are
# dropped (Douglas-Peucker). Lines put on the track from OpenStreetMap have a point every few metres, straight
# stretches included; Paris's file was 1.9 MB. Stations are untouched; the file is rewritten only if it shrinks.
#   python -I cities/simplify_lines.py [--tol 2] cities/fr-paris.json [...]   (--dry: report only)
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace')
import json, math, os, sys
args = sys.argv[1:]; TOL = 2.0; DRY = '--dry' in args
if '--tol' in args: i = args.index('--tol'); TOL = float(args[i+1]); del args[i:i+2]
files = [a for a in args if a != '--dry']
def rdp(pts, tol):
    if len(pts) < 3: return pts
    k = math.cos(math.radians(pts[0][0])) * 111320; ky = 111320
    keep = [False]*len(pts); keep[0] = keep[-1] = True; stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop(); ax, ay = pts[a][1]*k, pts[a][0]*ky; bx, by = pts[b][1]*k, pts[b][0]*ky; dx, dy = bx - ax, by - ay; L = math.hypot(dx, dy)
        best, bi = -1, -1
        for i in range(a + 1, b):
            px, py = pts[i][1]*k - ax, pts[i][0]*ky - ay
            d = abs(px*dy - py*dx)/L if L else math.hypot(px, py)
            if d > best: best, bi = d, i
        if best > tol: keep[bi] = True; stack += [(a, bi), (bi, b)]
    return [p for p, f in zip(pts, keep) if f]
for f in files:
    d = json.load(open(f, encoding='utf-8')); n0 = n1 = 0
    if not isinstance(d, dict) or not isinstance(d.get('lines'), list): continue
    for l in d['lines']:
        P = l.get('pts');
        if not P: continue
        multi = isinstance(P[0][0], list)
        pcs = P if multi else [P]; out = []
        for pc in pcs: n0 += len(pc); q = rdp(pc, TOL); n1 += len(q); out.append(q)
        l['pts'] = out if multi else out[0]
    before = os.path.getsize(f); txt = json.dumps(d, separators=(',', ':'), ensure_ascii=False)
    after = len(txt.encode('utf-8'))
    print(f'{os.path.basename(f):45s} points {n0} -> {n1}  {before//1024} -> {after//1024} KB', flush=True)
    if not DRY and after < before:
        with open(f + '.tmp', 'w', encoding='utf-8') as o: o.write(txt)
        os.replace(f + '.tmp', f)
