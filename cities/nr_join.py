# Close the gaps in the National Rail map (cities/nr tiles from osm_nr.py). Keeping one line per pair of parallel tracks
# leaves station throats and multi-track stretches as staggered pieces that stop short of each other (e.g. at Leeds).
# Each loose end is joined to the nearest point ahead on another line (within 45 m and no sharper than 55° off its own
# direction, or within 90 m straight ahead), so the lines run on without breaks. Ends that meet another line already (tile edges, junctions) are left alone.
#   python3 -I nr_join.py cities/nr        (rewrites the tiles in place; all.json is untouched: at overview zoom there are no gaps)
import sys, os, json, math, glob
import numpy as np
from scipy.spatial import cKDTree
d = sys.argv[1]; K = 0.6  # metres per degree of longitude ≈ 111320*K in Britain
files = [f for f in glob.glob(os.path.join(d, '*.json')) if not f.endswith('all.json')]
tiles = {f: json.load(open(f)) for f in files}
lines = [(f, i, p) for f, ps in tiles.items() for i, p in enumerate(ps)]
xy = lambda q: (q[1]*111320*K, q[0]*111320)
pts, owner = [], []
for li, (_, _, p) in enumerate(lines):
    for a, b in zip(p, p[1:]):
        (ax, ay), (bx, by) = xy(a), xy(b); n = max(1, int(math.hypot(bx-ax, by-ay)//4))
        for t in range(n + 1): pts.append((ax + (bx-ax)*t/n, ay + (by-ay)*t/n)); owner.append(li)
pts = np.array(pts); owner = np.array(owner); tree = cKDTree(pts)
inv = lambda x, y: [round(y/111320, 5), round(x/(111320*K), 5)]
added = 0
for li, (f, i, p) in enumerate(lines):
    for end, prev in ((p[-1], p[-2]), (p[0], p[1])):
        ex, ey = xy(end); px, py = xy(prev); dx, dy = ex-px, ey-py; L = math.hypot(dx, dy) or 1; dx, dy = dx/L, dy/L
        near = tree.query_ball_point((ex, ey), 90)
        if any(owner[j] != li and math.hypot(pts[j][0]-ex, pts[j][1]-ey) < 3 for j in near): continue  # already meets a line
        best = None
        for j in near:
            if owner[j] == li: continue
            vx, vy = pts[j][0]-ex, pts[j][1]-ey; r = math.hypot(vx, vy)
            if r < 1 or (vx*dx + vy*dy)/r < math.cos(math.radians(55 if r <= 45 else 20)): continue  # further away: only straight ahead
            if best is None or r < best[0]: best = (r, j)
        if best:
            tiles[f].append([end, inv(*pts[best[1]])]); added += 1
for f, ps in tiles.items(): json.dump(ps, open(f, 'w'), separators=(',', ':'))
print(len(lines), 'lines,', added, 'gaps joined')
