# Which OpenStreetMap extract to snap each city's lines with: every city file whose trams/metros still have straight
# hops over 450 m, grouped under the smallest Geofabrik extract that holds all of its lines (Berlin under 'berlin', not
# all of Germany). Prints one line per extract: <pbf url> <city files...>, for cities/.build/snap_all.sh.
#   python -I cities/snap_plan.py [cities/x.json ...]   (default: every city file)
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace')
import os, sys, json, math, glob
HERE = os.path.dirname(os.path.abspath(__file__))
def m(a, b): return math.hypot((a[0]-b[0])*111320, (a[1]-b[1])*111320*math.cos(math.radians(a[0])))
def pieces(l): return l['pts'] if isinstance(l['pts'][0][0], list) else [l['pts']]
def inside(ring, lon, lat):  # ray casting; ring of [lon, lat]
    c = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1)*(lat - y1)/((y2 - y1) or 1e-12) + x1: c = not c
    return c
idx = json.load(open(os.path.join(HERE, '.build', 'osm', 'index-v1.json'), encoding='utf-8'))['features']
def area(f):
    xs = [p[0] for poly in f['geometry']['coordinates'] for p in poly[0]]; ys = [p[1] for poly in f['geometry']['coordinates'] for p in poly[0]]
    return (max(xs) - min(xs))*(max(ys) - min(ys))
idx = sorted([f for f in idx if f['geometry'] and f['properties']['urls'].get('pbf')], key=area)
def holds(f, pts):
    return all(any(inside(poly[0], q[1], q[0]) for poly in f['geometry']['coordinates']) for q in pts)
groups = {}
files = sys.argv[1:] or sorted(glob.glob(os.path.join(HERE, '*.json')))
for fn in files:
    try: d = json.load(open(fn, encoding='utf-8'))
    except Exception: continue
    if not isinstance(d, dict) or not isinstance(d.get('lines'), list): continue
    pts, n = [], 0
    for l in d['lines']:
        if l.get('kind') not in ('tram', 'metro') or not l.get('pts'): continue
        for pc in pieces(l):
            for a, b in zip(pc, pc[1:]):
                if m(a, b) > 450: n += 1; pts += [a, b]
    if n < 5: continue
    # the hops' corners and middle (enough to test the extract holds them, fast)
    la = [q[0] for q in pts]; lo = [q[1] for q in pts]
    test = [[min(la), min(lo)], [min(la), max(lo)], [max(la), min(lo)], [max(la), max(lo)], [sum(la)/len(la), sum(lo)/len(lo)]]
    f = next((f for f in idx if holds(f, test)), None)
    if not f: print('# no extract holds', os.path.basename(fn), file=sys.stderr); continue
    groups.setdefault(f['properties']['urls']['pbf'], []).append(os.path.relpath(fn, os.path.dirname(HERE)).replace('\\', '/'))
for url, fs in groups.items(): print(url, *fs)
