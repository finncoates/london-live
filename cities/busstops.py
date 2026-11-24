# Every bus stop outside London with its timetable, from the Bus Open Data regional GTFS:
#   python3 busstops.py out_dir region1.zip region2.zip ...
# out_dir/<lat20>_<lon20>.json (0.05° tiles) = {"stops": [[id, name, lat, lon, [route indexes]]...],
#   "routes": [[line, operator, colour]...], "deps": {stop id: {"w": [weekday times...], "sa": [...], "su": [...]}}}
# times: [minutes after midnight, route index, destination index]; "dests": [names]  (a typical weekday / Saturday / Sunday)
import sys, os, zipfile, csv, io, json, math, collections, datetime
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from greater_london import in_london as LON  # Greater London has TfL's own bus routes (the boundary, not a box: Watford, Dartford, Epsom are outside it)
T = collections.defaultdict(lambda: {'stops': {}, 'routes': {}, 'dests': {}, 'deps': collections.defaultdict(lambda: {'w': [], 'sa': [], 'su': []})})
today = datetime.date.today()
def day_of(wd):  # the next date with this weekday (0 = Monday)
    return today + datetime.timedelta(days=(wd - today.weekday()) % 7 + 7)
for zf in sys.argv[2:]:
    z = zipfile.ZipFile(zf); rd = lambda n: csv.DictReader(io.TextIOWrapper(z.open(n), 'utf-8-sig'))
    ag = {a['agency_id']: a['agency_name'] for a in rd('agency.txt')}
    routes = {r['route_id']: (r['route_short_name'] or r.get('route_long_name', ''), ag.get(r['agency_id'], ''), r.get('route_color') or '') for r in rd('routes.txt') if r['route_type'] in ('3', '11', '700', '701', '702', '704', '705', '711', '712', '715', '800')}
    cal = {c['service_id']: c for c in rd('calendar.txt')} if 'calendar.txt' in z.namelist() else {}
    exc = collections.defaultdict(dict)
    if 'calendar_dates.txt' in z.namelist():
        for c in rd('calendar_dates.txt'): exc[c['service_id']][c['date']] = c['exception_type']
    def runs(sid, d):
        ds = d.strftime('%Y%m%d'); e = exc.get(sid, {}).get(ds)
        if e == '1': return True
        if e == '2': return False
        c = cal.get(sid); wd = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'][d.weekday()]
        return bool(c and c['start_date'] <= ds <= c['end_date'] and c[wd] == '1')
    days = {'w': day_of(2), 'sa': day_of(5), 'su': day_of(6)}  # a Wednesday, a Saturday, a Sunday (each kept compactly)
    trips = {}
    for t in rd('trips.txt'):
        if t['route_id'] not in routes: continue
        which = [k for k, d in days.items() if runs(t['service_id'], d)]
        if which: trips[t['trip_id']] = (t['route_id'], which, t.get('trip_headsign') or '')
    stops = {s['stop_id']: (s['stop_name'], float(s['stop_lat']), float(s['stop_lon'])) for s in rd('stops.txt') if s.get('stop_lat')}
    last = {}; rows = collections.defaultdict(list)
    with z.open('stop_times.txt') as f:
        for s in csv.DictReader(io.TextIOWrapper(f, 'utf-8-sig')):
            tid = s['trip_id']
            if tid not in trips: continue
            rows[tid].append((int(s['stop_sequence']), s['stop_id'], s['departure_time'] or s['arrival_time']))
    for tid, rs in rows.items():
        rs.sort(); rid, which, head = trips[tid]; dest = head or stops.get(rs[-1][1], ('',))[0]
        for seq, sid, tm in rs[:-1]:  # not the last stop (it ends there)
            st = stops.get(sid)
            if not st or LON(st[1], st[2]) or not tm: continue
            h, m, _ = tm.split(':'); mins = int(h)*60 + int(m)
            key = f"{math.floor(st[1]*20)}_{math.floor(st[2]*20)}"; t = T[key]
            ri = t['routes'].setdefault((routes[rid][0], routes[rid][1], routes[rid][2]), len(t['routes']))
            di = t['dests'].setdefault(dest, len(t['dests']))
            if sid not in t['stops']: t['stops'][sid] = [sid, st[0], round(st[1], 5), round(st[2], 5), set()]
            t['stops'][sid][4].add(ri)
            for k in which: t['deps'][sid][k].append((mins, ri, di))
    print(zf, len(trips), 'trips', flush=True)
for key, t in T.items():
    deps = {}
    for sid, d in t['deps'].items():  # per day: one flat list [min, route, dest, min, route, dest, ...], minutes as deltas (small numbers)
        o2 = {}
        for k, v in d.items():
            if not v: continue
            # one string per day: each departure = minute delta, route, destination in base 36, ',' separated
            v = sorted(set(v)); parts = []; prev = 0
            b36 = lambda n: '0' if n == 0 else ''.join('0123456789abcdefghijklmnopqrstuvwxyz'[(n // 36**i) % 36] for i in range(int(math.log(n, 36)) + 1, -1, -1)).lstrip('0') or '0'
            for mi, ri, di in v: parts.append(b36(mi - prev) + '.' + b36(ri) + '.' + b36(di)); prev = mi
            o2[k] = ','.join(parts)
        if o2.get('su') == o2.get('sa'): o2.pop('su', None)  # same as Saturday
        deps[sid] = o2
    o = {'stops': [[a, b, c, e, sorted(f)] for a, b, c, e, f in t['stops'].values()],
         'routes': [list(r) for r, _ in sorted(t['routes'].items(), key=lambda x: x[1])]}
    if os.environ.get('DEPS') == '1': o['dests'] = [d for d, _ in sorted(t['dests'].items(), key=lambda x: x[1])]; o['deps'] = deps  # timetables (large): only when asked
    json.dump(o, open(os.path.join(out, key + '.json'), 'w'), separators=(',', ':'), ensure_ascii=False)
print(len(T), 'tiles', sum(os.path.getsize(os.path.join(out, f)) for f in os.listdir(out)) // 1000000, 'MB')
