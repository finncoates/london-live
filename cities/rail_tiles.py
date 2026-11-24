# Rebuild the National Rail map tiles (cities/nr/<lat*2>_<lon*2>.json and the overview all.json) from Britain's own
# (git, BASE: before any other country) + every other country's railway lines (cities/.build/rail/<cc>.json: a list of
# polylines [[lat, lon], ...], made by fr_rail.py for France, rail_gtfs.py for the Netherlands…).
#   python -I cities/rail_tiles.py
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace'); _s.stderr.reconfigure(encoding='utf-8', errors='replace')  # Windows console: never crash on a name
import os, json, math, subprocess, collections, sys
# one writer at a time: two builds merging into the same shared tiles at once corrupt them (Windows: 'Invalid argument')
import time as _t, atexit as _ax
_LOCK = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.build', 'merge.lock'); _t0 = _t.time()
while True:
    try: _fd = os.open(_LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY); break
    except FileExistsError:
        if _t.time() - os.path.getmtime(_LOCK) > 1800: os.remove(_LOCK)  # left by a crashed run
        _t.sleep(2)
_ax.register(lambda: (os.close(_fd), os.remove(_LOCK)))
HERE = os.path.dirname(os.path.abspath(__file__)); BASE = '6c9aa8ce'; R = os.path.join(HERE, '.build', 'rail'); os.makedirs(R, exist_ok=True)
sys.setrecursionlimit(100000)
def dp(p, eps):  # closed loops (a ring line, a circular bus route) split at their farthest point first: measured against
    # a line from a point to itself, the whole loop would collapse to nothing (Copenhagen's M3 did)
    if len(p) > 3 and abs(p[0][0] - p[-1][0]) < 2e-5 and abs(p[0][1] - p[-1][1]) < 3e-5:
        k = max(range(len(p)), key=lambda i: (p[i][0] - p[0][0])**2 + ((p[i][1] - p[0][1])*0.65)**2)
        if 0 < k < len(p) - 1: return _dp_open(p[:k+1], eps)[:-1] + _dp_open(p[k:], eps)
    return _dp_open(p, eps)
_dp_loop = True
def _dp_open(p, eps):  # Douglas-Peucker, metres
    if len(p) < 3: return p
    k = math.cos(math.radians(p[0][0])); a, b = p[0], p[-1]
    ax, ay, bx, by = a[1]*k*111320, a[0]*111320, b[1]*k*111320, b[0]*111320; L2 = math.hypot(bx-ax, by-ay) or 1e-9; best, bi = 0, 0
    for i in range(1, len(p)-1):
        x, y = p[i][1]*k*111320, p[i][0]*111320; d = abs((bx-ax)*(ay-y) - (ax-x)*(by-ay))/L2
        if d > best: best, bi = d, i
    return [a, b] if best <= eps else dp(p[:bi+1], eps)[:-1] + dp(p[bi:], eps)
lines = []
for f in sorted(os.listdir(R)):
    if f.endswith('.json'): lines += [[tuple(q) for q in l] for l in json.load(open(os.path.join(R, f)))]
# a line ending just short of another (a junction or crossover dropped as a parallel duplicate: the Garonne crossing at
# Bordeaux showed a 35 m gap) is joined on to the nearest point of the other within 60 m
def _m(a, b): return math.hypot((a[0]-b[0])*111320, (a[1]-b[1])*111320*math.cos(math.radians(a[0])))
_G = collections.defaultdict(list)
for i, l in enumerate(lines):
    for q in l: _G[(round(q[0]*1500), round(q[1]*1000))].append((q, i))
def _ang(a, b): return math.atan2(b[0]-a[0], (b[1]-a[1])*math.cos(math.radians(a[0])))
def _near(q, i, prev):  # (only straight on from the line's last piece, within 30°: not across to a parallel track)
    best = None; h = _ang(prev, q)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for r, j in _G.get((round(q[0]*1500)+dx, round(q[1]*1000)+dy), ()):
                if j == i: continue
                d = _m(q, r)
                if d < 60 and (best is None or d < best[0]) and (d <= 0.5 or abs((_ang(q, r) - h + math.pi) % (2*math.pi) - math.pi) < math.radians(30)): best = (d, r)
    return best
joined = 0
for i, l in enumerate(lines):
    if len(l) < 2: continue
    a = _near(l[0], i, l[1]); b = _near(l[-1], i, l[-2])
    if a and a[0] > 0.5: l.insert(0, a[1]); joined += 1
    if b and b[0] > 0.5: l.append(b[1]); joined += 1
print(joined, 'line ends joined to a neighbour')
T = collections.defaultdict(list); tk = lambda q: f'{math.floor(q[0]*2)}_{math.floor(q[1]*2)}'
for l in lines:  # cut where a line crosses into the next 0.5° tile, sharing the crossing point (no gaps)
    q = dp(l, 8); run = [q[0]]
    for pt in q[1:]:
        run.append(pt)
        if tk(pt) != tk(run[0]): T[tk(run[0])].append(run); run = [pt]
    if len(run) > 1: T[tk(run[0])].append(run)
nrd = os.path.join(HERE, 'nr')
git = lambda f: subprocess.run(['git', '-C', HERE, 'show', f'{BASE}:cities/nr/{f}'], capture_output=True, text=True)
INBASE = set(subprocess.run(['git', '-C', HERE, 'ls-tree', '--name-only', f'{BASE}:cities/nr/'], capture_output=True, text=True).stdout.split())
for t, ps in T.items():
    b = git(t + '.json') if t + '.json' in INBASE else None; old = json.loads(b.stdout) if b and b.returncode == 0 else []
    json.dump(old + [[[a, c] for a, c in p] for p in ps], open(os.path.join(nrd, t + '.json'), 'w'), separators=(',', ':'))
base = json.loads(git('all.json').stdout)
ov = [[[round(a, 4), round(c, 4)] for a, c in dp(l, 80)] for l in lines]
json.dump(base + [p for p in ov if len(p) > 1], open(os.path.join(nrd, 'all.json'), 'w'), separators=(',', ':'))
print(len(lines), 'lines from', ', '.join(f[:-5] for f in sorted(os.listdir(R)) if f.endswith('.json')), '->', len(T), 'tiles')
