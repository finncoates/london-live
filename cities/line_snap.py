# Straight hops in a city's lines put back on the track: where a timetable's shape is coarse (Bordeaux's trams A and E
# cut diagonally across the Garonne from Porte de Bourgogne; Paris's Transilien K, P, N; Corsica's railway), each hop
# much longer than the line's usual spacing is routed along OpenStreetMap's track (tram/light rail for trams, rail for
# trains, subway for metros) and spliced in. A hop the router can't follow sensibly is left as it was.
#   python -I cities/line_snap.py region.osm.pbf cities/fr-bordeaux.json [more city files in that region]
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace')
import os, sys, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from route import Router
pbf, files = sys.argv[1], sys.argv[2:]
def m(a, b): return math.hypot((a[0]-b[0])*111320, (a[1]-b[1])*111320*math.cos(math.radians(a[0])))
KIND = {'tram':'tram', 'train':'tramrail', 'metro':'metro'}
for f in files:
    d = json.load(open(f, encoding='utf-8')); todo = []
    for l in d['lines']:
        if l['kind'] not in KIND or len(l['pts']) < 4: continue
        hops = [m(a, b) for a, b in zip(l['pts'], l['pts'][1:])]; med = sorted(hops)[len(hops)//2]
        for i, h in enumerate(hops):  # (a line drawn station to station, median hop over 250 m: every hop; Lisbon's Metro)
            if h > max(1200, 10*med) or (med > 250 and h > 250): todo.append((l, i))
    if not todo: print(os.path.basename(f), 'no straight hops'); continue
    la = [q[0] for l, _ in todo for q in l['pts']]; lo = [q[1] for l, _ in todo for q in l['pts']]
    box = (min(la) - 0.02, min(lo) - 0.03, max(la) + 0.02, max(lo) + 0.03); routers = {}
    fixed = 0
    for l, i in sorted(todo, key=lambda x: -x[1]):  # from the end, so earlier indexes stay valid
        k = KIND[l['kind']]; r = routers.get(k) or routers.setdefault(k, Router(pbf, box, k, snap_m=80))
        a, b = l['pts'][i], l['pts'][i+1]; p = r.path(tuple(a), tuple(b))
        if not p or len(p) < 3: continue
        L = sum(m(p[j-1], p[j]) for j in range(1, len(p)))
        if L > 1.6*m(a, b) + 500: continue  # a detour, not the same line
        l['pts'][i+1:i+1] = [[round(x, 5), round(y, 5)] for x, y in p[1:-1]]; fixed += 1
    for _k in range(20):  # written whole then swapped in, retried: Windows refuses a file another process has open
        try:
            with open(f + '.tmp', 'w', encoding='utf-8') as o_: json.dump(d, o_, separators=(',', ':'), ensure_ascii=False)
            os.replace(f + '.tmp', f); break
        except OSError: __import__('time').sleep(0.5)
    print(os.path.basename(f), fixed, 'of', len(todo), 'straight hops put on the track', flush=True)
