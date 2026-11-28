# A city's buses from its timetable, for a city whose buses aren't in Transitous (Madrid's EMT): one pattern per route
# and stop list (its running times from a typical trip), each with its own road shape (the feed's shapes.txt, thinned
# and polyline-encoded), and every trip's start time per service day. The page moves each bus along its shape.
#   python -I cities/gtfs_sched_bus.py feed.zip out.json "EMT Madrid" Europe/Madrid "#7E8BA3"
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace')
import sys, zipfile, csv, io, json, collections, datetime, math, os
zf, outf, OP, TZ, COL = sys.argv[1:6]
z = zipfile.ZipFile(zf); rd = lambda n: csv.DictReader(io.TextIOWrapper(z.open(n), 'utf-8-sig'))
tos = lambda t: (lambda h, m, s: int(h)*3600 + int(m)*60 + int(s))(*t.strip().split(':'))
routes = {r['route_id']: r['route_short_name'] or r['route_long_name'] for r in rd('routes.txt') if r['route_type'] in ('3', '700', '702', '704', '715')}
trips = {t['trip_id']: (t['route_id'], t['service_id'], t.get('trip_headsign', ''), t.get('shape_id', '')) for t in rd('trips.txt') if t['route_id'] in routes}
stops = {s['stop_id']: (round(float(s['stop_lat']), 5), round(float(s['stop_lon']), 5), s['stop_name']) for s in rd('stops.txt')}
seq = collections.defaultdict(list)
for st in rd('stop_times.txt'):
    if st['trip_id'] in trips and (st['arrival_time'] or st['departure_time']): seq[st['trip_id']].append((int(st['stop_sequence']), st['stop_id'], tos(st['arrival_time'] or st['departure_time'])))
shp = collections.defaultdict(list)
if 'shapes.txt' in z.namelist():
    for r in rd('shapes.txt'): shp[r['shape_id']].append((int(r['shape_pt_sequence']), float(r['shape_pt_lat']), float(r['shape_pt_lon'])))
def m(a, b): return math.hypot((a[0]-b[0])*111320, (a[1]-b[1])*111320*math.cos(math.radians(a[0])))
def rdp(pts, tol=6.0):
    if len(pts) < 3: return pts
    k = math.cos(math.radians(pts[0][0]))*111320; keep = [False]*len(pts); keep[0] = keep[-1] = True; st = [(0, len(pts) - 1)]
    while st:
        a, b = st.pop(); ax, ay = pts[a][1]*k, pts[a][0]*111320; dx, dy = pts[b][1]*k - ax, pts[b][0]*111320 - ay; L = math.hypot(dx, dy); best, bi = -1, -1
        for i in range(a + 1, b):
            px, py = pts[i][1]*k - ax, pts[i][0]*111320 - ay; d = abs(px*dy - py*dx)/L if L else math.hypot(px, py)
            if d > best: best, bi = d, i
        if best > tol: keep[bi] = True; st += [(a, bi), (bi, b)]
    return [p for p, f in zip(pts, keep) if f]
def enc(pts):
    out, pl, po = [], 0, 0
    for la, lo in pts:
        a, o = int(round(la*1e5)), int(round(lo*1e5))
        for v in (a - pl, o - po):
            v = ~(v << 1) if v < 0 else v << 1
            while v >= 0x20: out.append(chr((0x20 | (v & 0x1f)) + 63)); v >>= 5
            out.append(chr(v + 63))
        pl, po = a, o
    return ''.join(out)
FREQ = collections.defaultdict(list)  # a template trip run every headway between two times (EMT's whole timetable is these)
if 'frequencies.txt' in z.namelist() and os.environ.get('IGNORE_FREQ') != '1':  # (IGNORE_FREQ=1: EMT's rows only describe each real trip's hour; its trips have their own times)
    for f in rd('frequencies.txt'):
        if f['trip_id'] in trips: FREQ[f['trip_id']].append((tos(f['start_time']), tos(f['end_time']), max(60, int(f['headway_secs']))))
shape_ix, shapes, pat_ix, patterns, by_service = {}, [], {}, [], collections.defaultdict(list)
for tid, rows in seq.items():
    rows.sort(); rid, sid, head, sh = trips[tid]; t0 = rows[0][2]; ss = tuple(r[1] for r in rows)
    key = (rid, ss)
    if key not in pat_ix:
        si = None; S = None
        if sh in shp:
            if sh not in shape_ix:
                P = [(la, lo) for _, la, lo in sorted(shp[sh])]; shape_ix[sh] = (len(shapes), rdp(P)); shapes.append(enc(shape_ix[sh][1]))
            S, Q = shape_ix[sh]; si = []; j = 0
            for r in rows:  # each stop's nearest shape point, in order
                p = stops[r[1]][:2]; best, bj = 1e9, j
                for k in range(j, min(len(Q), j + 400)):
                    d = m(p, Q[k])
                    if d < best: best, bj = d, k
                si.append(bj); j = bj
        pat_ix[key] = len(patterns)
        patterns.append({'line': routes[rid], 'col': COL, 'kind': 'bus', 'dest': head or stops[rows[-1][1]][2], 'stops': [list(stops[r[1]][:2]) for r in rows],
                         'off': [r[2] - t0 for r in rows], **({'sh': S, 'si': si} if S is not None else {})})
    if tid in FREQ: by_service[sid] += [[pat_ix[key], t] for (a, b, h) in FREQ[tid] for t in range(a, b, h)]
    else: by_service[sid].append([pat_ix[key], t0])
cal = {c['service_id']: c for c in rd('calendar.txt')} if 'calendar.txt' in z.namelist() else {}
exc = collections.defaultdict(dict)
if 'calendar_dates.txt' in z.namelist():
    for c in rd('calendar_dates.txt'): exc[c['date']][c['service_id']] = c['exception_type']
days, lists, ix = {}, [], {}; today = datetime.date.today()
for k in range(21):
    dt = today + datetime.timedelta(days=k); ds = dt.strftime('%Y%m%d'); wd = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'][dt.weekday()]
    run = {sid for sid, c in cal.items() if c['start_date'] <= ds <= c['end_date'] and c[wd] == '1'}
    for sid, e in exc.get(ds, {}).items():
        if e == '1': run.add(sid)
        elif e == '2': run.discard(sid)
    v = sorted(x for sid in run if sid in by_service for x in by_service[sid]); kk = json.dumps(v)
    if kk not in ix: ix[kk] = len(lists); lists.append(v)
    days[ds] = ix[kk]
# each day's start times, compact: per pattern its first time then the gaps, base 36 (the page unpacks them once)
def b36(n):
    a = '0123456789abcdefghijklmnopqrstuvwxyz'; o = ''
    while True:
        n, r = divmod(n, 36); o = a[r] + o
        if not n: return o
listsD = []
for L in lists:
    g = collections.defaultdict(list)
    for pi, t in L: g[pi].append(t)
    listsD.append({str(pi): ','.join(b36(t - (ts[i-1] if i else 0)) for i, t in enumerate(sorted(ts))) for pi, ts in g.items() for ts in [sorted(ts)]})
d = {'lines': [], 'stations': [], 'op': OP, 'sched': {'patterns': patterns, 'shapes': shapes, 'days': days, 'listsD': listsD, 'tz': TZ}}
json.dump(d, open(outf, 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
print(len(patterns), 'patterns', len(shapes), 'shapes', [len(l) for l in lists], 'lists', os.path.getsize(outf)//1024, 'KB')
