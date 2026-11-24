# Bus routes that cut across town instead of following streets: in each network's own bus tiles, straight segments
# longer than 350 m whose middle has two or more of the network's stops within 250 m (a built-up place, where streets
# don't run that straight). Ranks networks by the length of such cuts per km of route.
#   python -I cities/check_buscuts.py [network build folder ...]
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace')
import os, sys, json, math, glob, collections
HERE = os.path.dirname(os.path.abspath(__file__)); B = os.path.join(HERE, '.build')
def m(a, b): return math.hypot((a[0]-b[0])*111320, (a[1]-b[1])*111320*math.cos(math.radians(a[0])))
dirs = sys.argv[1:] or sorted({f.split(os.sep)[-3] for f in glob.glob(os.path.join(B, '*', 'busnet', '*.json'))})
out = []
for d in dirs:
    sf = os.path.join(B, d, 'stops.json')
    if not os.path.exists(sf): continue
    grid = collections.defaultdict(list)
    for s in json.load(open(sf, encoding='utf-8')): grid[(round(s[1]*200), round(s[2]*140))].append((s[1], s[2]))
    def near(p): return sum(1 for dx in (-1, 0, 1) for dy in (-1, 0, 1) for q in grid.get((round(p[0]*200)+dx, round(p[1]*140)+dy), ()) if m(p, q) < 250)
    tot = cut = 0; eg = None
    for f in glob.glob(os.path.join(B, d, 'busnet', '*.json')):
        try: t = json.load(open(f))
        except Exception: continue
        for pl in t:
            for a, b in zip(pl, pl[1:]):
                L = m(a, b); tot += L
                if L > 350 and near(((a[0]+b[0])/2, (a[1]+b[1])/2)) >= 2: cut += L; eg = eg or (a, b, round(L))
    if tot: out.append((cut/tot*1000, cut/1000, tot/1000, d, eg))
out.sort(reverse=True)
for r, c, t, d, eg in out[:int(os.environ.get('N', 60))]: print(f'{r:6.1f} m/km  {c:7.1f} km of {t:8.1f}  {d:<45} {eg}')
