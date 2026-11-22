# Compact scheduled-vehicle timetable: patterns (stop list + offsets) and start times per service day.
# usage: gtfs_sched.py feed.zip city.json "0:tram"   -> adds d.sched = {patterns:[{line, col, kind, stops:[[lat,lon]..], off:[s..], dest}], days:{YYYYMMDD:[[pattern, start_s], ...]}}
import sys, zipfile, csv, io, json, collections, datetime
zf, jf, typemap = sys.argv[1], sys.argv[2], dict(x.split(':') for x in sys.argv[3].split(','))
z = zipfile.ZipFile(zf); rd = lambda n: csv.DictReader(io.TextIOWrapper(z.open(n), 'utf-8-sig'))
d = json.load(open(jf)); col = {l['name']: l['col'] for l in d['lines']}
import os, re
ONLY = re.compile(os.environ['ONLY']) if os.environ.get('ONLY') else None  # e.g. ONLY='^Metro$': just these route names
routes = {r['route_id']: r.get('route_short_name') or r.get('route_long_name') for r in rd('routes.txt') if r['route_type'] in typemap and (not ONLY or ONLY.search(r.get('route_short_name') or r.get('route_long_name') or ''))}
trips = {t['trip_id']: (t['route_id'], t['service_id'], t.get('trip_headsign', '')) for t in rd('trips.txt') if t['route_id'] in routes}
stops = {s['stop_id']: (round(float(s['stop_lat']), 5), round(float(s['stop_lon']), 5), s['stop_name']) for s in rd('stops.txt')}
seq = collections.defaultdict(list)
tos = lambda t: (lambda h, m, s: int(h)*3600 + int(m)*60 + int(s))(*t.split(':'))
for st in rd('stop_times.txt'):
    if st['trip_id'] in trips: seq[st['trip_id']].append((int(st['stop_sequence']), st['stop_id'], tos(st['arrival_time'] or st['departure_time'])))
pat_index = {}; patterns = []; by_service = collections.defaultdict(list)
for tid, rows in seq.items():
    rows.sort(); rid, sid, head = trips[tid]; t0 = rows[0][2]
    key = (routes[rid], tuple(r[1] for r in rows), tuple(r[2] - t0 for r in rows))
    if key not in pat_index:
        pat_index[key] = len(patterns)
        patterns.append({'line': routes[rid], 'col': col.get(routes[rid], '#7A1F3D'), 'kind': 'tram', 'stops': [list(stops[r[1]][:2]) for r in rows],
                         'off': [r[2] - t0 for r in rows], 'dest': re.sub(r' \((Manchester Metrolink|West Midlands Metro)\)$| \(?Tram Stop\)?$', '', stops[rows[-1][1]][2])})
    by_service[sid].append([pat_index[key], t0])
# which services run on each of the next 21 days
cal = {c['service_id']: c for c in rd('calendar.txt')} if 'calendar.txt' in z.namelist() else {}
exc = collections.defaultdict(dict)
for c in rd('calendar_dates.txt'): exc[c['date']][c['service_id']] = c['exception_type']
days = {}; today = datetime.date.today()
for k in range(21):
    dt = today + datetime.timedelta(days=k); ds = dt.strftime('%Y%m%d'); wd = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'][dt.weekday()]
    run = set()
    for sid, c in cal.items():
        if c['start_date'] <= ds <= c['end_date'] and c[wd] == '1': run.add(sid)
    for sid, e in exc.get(ds, {}).items():
        if e == '1': run.add(sid)
        elif e == '2': run.discard(sid)
    days[ds] = sorted(x for sid in run if sid in by_service for x in by_service[sid])
lists = []; ix = {}
for k, v in days.items():
    kk = json.dumps(v)
    if kk not in ix: ix[kk] = len(lists); lists.append(v)
    days[k] = ix[kk]
d['sched'] = {'patterns': patterns, 'days': days, 'lists': lists, 'tz': 'Europe/London'}
json.dump(d, open(jf, 'w'), separators=(',', ':'), ensure_ascii=False)
import os; print(len(patterns), 'patterns', len(lists), os.path.getsize(jf))
