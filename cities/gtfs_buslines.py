# Bus routes of a city (one shape per route & direction, simplified) -> separate file, loaded only when buses are on
import sys, zipfile, csv, io, json, collections, math, os
zf, out = sys.argv[1], sys.argv[2]; box = [float(x) for x in sys.argv[3].split(',')] if len(sys.argv) > 3 else None
z = zipfile.ZipFile(zf); rd = lambda n: csv.DictReader(io.TextIOWrapper(z.open(n), 'utf-8-sig'))
routes = {r['route_id']: r['route_short_name'] or r['route_long_name'] for r in rd('routes.txt') if r['route_type'] == '3'}
cnt = collections.Counter(); best = {}
for t in rd('trips.txt'):
    if t['route_id'] in routes and t.get('shape_id'):
        cnt[t['shape_id']] += 1; best.setdefault((t['route_id'], t.get('direction_id', '0')), []).append(t['shape_id'])
want = {}
for k, sids in best.items():
    s = max(set(sids), key=lambda x: cnt[x]); want[s] = routes[k[0]]
pts = collections.defaultdict(list)
for s in rd('shapes.txt'):
    if s['shape_id'] in want: pts[s['shape_id']].append((int(s['shape_pt_sequence']), float(s['shape_pt_lat']), float(s['shape_pt_lon'])))
def dp(p, eps):
    if len(p) < 3: return p
    k = math.cos(math.radians(p[0][0])); a, b = p[0], p[-1]
    ax, ay, bx, by = a[1]*k*111320, a[0]*111320, b[1]*k*111320, b[0]*111320; L = math.hypot(bx-ax, by-ay) or 1e-9; best, bi = 0, 0
    for i in range(1, len(p)-1):
        x, y = p[i][1]*k*111320, p[i][0]*111320; d = abs((bx-ax)*(ay-y) - (ax-x)*(by-ay))/L
        if d > best: best, bi = d, i
    return [a, b] if best <= eps else dp(p[:bi+1], eps)[:-1] + dp(p[bi:], eps)
lines = []
for sid, name in want.items():
    p = [(la, lo) for _, la, lo in sorted(pts[sid])]
    if box: p = [q for q in p if box[0] <= q[0] <= box[2] and box[1] <= q[1] <= box[3]]
    if len(p) < 2: continue
    lines.append({'name': name, 'kind': 'bus', 'col': '#DC241F', 'pts': [[round(a, 5), round(b, 5)] for a, b in dp(p, 6)]})
json.dump({'lines': lines}, open(out, 'w'), separators=(',', ':'))
print(len(lines), 'bus routes', sum(len(l['pts']) for l in lines), 'points', os.path.getsize(out))
