# How complete each network's bus map is: the share of its bus stops more than 60 m from any drawn bus road (the
# shared tiles in cities/busnet). A network whose routes didn't match the roads, or were left out, shows up here.
#   python -I cities/check_bus.py [network build folder ...]
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace')
import os, sys, json, math, glob, collections
HERE = os.path.dirname(os.path.abspath(__file__)); B = os.path.join(HERE, '.build')
tiles = {}
def tile(k):
    if k not in tiles:
        f = os.path.join(HERE, 'busnet', f'{k[0]}_{k[1]}.json'); g = collections.defaultdict(list)
        if os.path.exists(f):
            for pl in json.load(open(f)):
                for a, b in zip(pl, pl[1:]):
                    for t in (a, b, ((a[0]+b[0])/2, (a[1]+b[1])/2)): g[(round(t[0]*400), round(t[1]*400))].append((a, b))
        tiles[k] = g
    return tiles[k]
def seg_d(p, a, b):
    c = math.cos(math.radians(p[0])); ax, ay, bx, by, px, py = a[1]*c, a[0], b[1]*c, b[0], p[1]*c, p[0]
    dx, dy = bx-ax, by-ay; L2 = dx*dx + dy*dy; t = max(0, min(1, ((px-ax)*dx + (py-ay)*dy)/L2)) if L2 else 0
    return math.hypot(ax + dx*t - px, ay + dy*t - py)*111320
def near(p):
    k = (math.floor(p[0]*10), math.floor(p[1]*10)); g = tile(k); cx, cy = round(p[0]*400), round(p[1]*400); best = 1e9
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for a, b in g.get((cx+dx, cy+dy), ()): best = min(best, seg_d(p, a, b))
    return best
dirs = sys.argv[1:] or [os.path.basename(os.path.dirname(f)) for f in glob.glob(os.path.join(B, '*', 'stops.json'))]
out = []
for d in dirs:
    f = os.path.join(B, d, 'stops.json')
    if not os.path.exists(f): continue
    st = json.load(open(f, encoding='utf-8'))
    if not st: continue
    far = [s for s in st if near((s[1], s[2])) > 60]
    out.append((len(far)/len(st), len(far), len(st), d, far[:3]))
out.sort(reverse=True)
for share, n, t, d, eg in out[:int(os.environ.get('N', 60))]: print(f'{share*100:5.1f}%  {n:5d} of {t:5d}  {d:<45} {[(e[0], e[1], e[2]) for e in eg][:2]}')
