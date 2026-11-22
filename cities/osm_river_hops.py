import json, math, urllib.request
ways = [w for w in json.load(open('rails.json')) if w['r'] == 'river']
def d(a, b): return math.hypot((a[0]-b[0])*111320, (a[1]-b[1])*111320*math.cos(math.radians(a[0])))
# join the Thames ways end to end into one long line (west -> east)
segs = [w['p'] for w in ways if len(w['p']) > 1]; segs.sort(key=lambda p: min(p[0][1], p[-1][1]))
line = list(segs.pop(0)); 
if line[0][1] > line[-1][1]: line.reverse()
while segs:
    best = None
    for i, s in enumerate(segs):
        for rev in (False, True):
            q = s[::-1] if rev else s; g = d(line[-1], q[0])
            if best is None or g < best[0]: best = (g, i, q)
    g, i, q = best; segs.pop(i)
    if g < 3000: line += q[1:]
cum = [0]
for i in range(1, len(line)): cum.append(cum[-1] + d(line[i-1], line[i]))
def proj(p):
    best = (1e18, 0)
    for i in range(1, len(line)):
        a, b = line[i-1], line[i]; kx = math.cos(math.radians(p[0]))
        ax, ay, bx, by, px, py = a[1]*kx, a[0], b[1]*kx, b[0], p[1]*kx, p[0]
        dx, dy = bx-ax, by-ay; L2 = dx*dx+dy*dy or 1e-12; t = max(0, min(1, ((px-ax)*dx+(py-ay)*dy)/L2))
        q = [a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t]; dd = d(q, p)
        if dd < best[0]: best = (dd, cum[i-1] + (cum[i]-cum[i-1])*t, i, q)
    return best
T = json.load(open('/home/user/london-live/cities/london-tracks.json'))
for lid in ['rb1', 'rb4', 'rb6', 'woolwich-ferry']:
    stops = {}; pairs = set()
    for direction in ('outbound', 'inbound'):
        j = json.load(urllib.request.urlopen(urllib.request.Request(f'https://api.tfl.gov.uk/Line/{lid}/Route/Sequence/{direction}', headers={'User-Agent':'x'})))
        for seq in j.get('stopPointSequences', []):
            for s in seq['stopPoint']: stops[s['id']] = (s['lat'], s['lon'])
        for r in j.get('orderedLineRoutes', []):
            ids = r['naptanIds']
            for i in range(1, len(ids)): pairs.add(tuple(sorted((ids[i-1], ids[i]))))
    out = []
    for a, b in pairs:
        if a not in stops or b not in stops: continue
        pa, pb = stops[a], stops[b]; A, B = proj(pa), proj(pb)
        if A[0] > 600 or B[0] > 600 or lid in ('rb4', 'woolwich-ferry') and abs(A[1]-B[1]) < 900:  # crossings: straight over the water
            out.append([a, b, [list(pa), list(pb)]]); continue
        lo, hi = sorted([A, B], key=lambda x: x[1]); mid = [p for k, p in enumerate(line) if lo[1] < cum[k] < hi[1]]
        pts = [list(pa if lo is A else pb), lo[3]] + mid + [hi[3], list(pb if lo is A else pa)]
        if lo is not A: pts.reverse()
        out.append([a, b, [[round(x, 5), round(y, 5)] for x, y in pts]])
    T[lid] = out; print(lid, len(pairs), 'hops', len(out))
json.dump(T, open('/home/user/london-live/cities/london-tracks.json', 'w'), separators=(',', ':'))
