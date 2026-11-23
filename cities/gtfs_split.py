# Split a big national GTFS into one small GTFS per group of operators, in a single pass over its stop times (the
# Netherlands' is 1.2 GB: reading it once instead of once per operator).
#   python -I cities/gtfs_split.py feed.zip outdir 'name=agency regex' ['name=agency regex' ...]
#   -> outdir/<name>.zip for each group (agency_id + ' ' + agency_name is matched)
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace'); _s.stderr.reconfigure(encoding='utf-8', errors='replace')  # Windows console: never crash on a name
import sys, os, io, csv, re, zipfile
feed, outdir, groups = sys.argv[1], sys.argv[2], [g.split('=', 1) for g in sys.argv[3:]]
os.makedirs(outdir, exist_ok=True)
z = zipfile.ZipFile(feed); rd = lambda n: csv.DictReader(io.TextIOWrapper(z.open(n), 'utf-8-sig'))
ag = {a['agency_id']: a['agency_name'] for a in rd('agency.txt')}
gof = lambda aid: next((n for n, rx in groups if re.search(rx, (aid or '') + ' ' + ag.get(aid or '', ''))), None)
routes = list(rd('routes.txt')); rg = {r['route_id']: gof(r.get('agency_id')) for r in routes}
trips = list(rd('trips.txt')); tg = {t['trip_id']: rg.get(t['route_id']) for t in trips}
outs = {n: zipfile.ZipFile(os.path.join(outdir, n + '.zip'), 'w', zipfile.ZIP_DEFLATED) for n, _ in groups}
def write(name, rows, fields, key):
    for n, zo in outs.items():
        buf = io.StringIO(); w = csv.DictWriter(buf, fieldnames=fields, extrasaction='ignore'); w.writeheader(); w.writerows(r for r in rows if key(r) == n); zo.writestr(name, buf.getvalue())
write('agency.txt', list(rd('agency.txt')), list(ag and next(iter(rd('agency.txt'))).keys()), lambda a: gof(a['agency_id']))
write('routes.txt', routes, list(routes[0].keys()), lambda r: rg[r['route_id']])
write('trips.txt', trips, list(trips[0].keys()), lambda t: tg[t['trip_id']])
shp = {}; stops_of = {n: set() for n in outs}
for t in trips:
    if tg[t['trip_id']] and t.get('shape_id'): shp.setdefault(t['shape_id'], set()).add(tg[t['trip_id']])
fh = {n: zo.open('stop_times.txt', 'w') for n, zo in outs.items()}; tw = {n: io.TextIOWrapper(f, 'utf-8', newline='') for n, f in fh.items()}; ws = {}
for s in rd('stop_times.txt'):
    n = tg.get(s['trip_id'])
    if not n: continue
    if n not in ws: ws[n] = csv.DictWriter(tw[n], fieldnames=list(s.keys()), extrasaction='ignore'); ws[n].writeheader()
    ws[n].writerow(s); stops_of[n].add(s['stop_id'])
for n in outs: tw[n].flush(); tw[n].detach(); fh[n].close()
stops = list(rd('stops.txt')); byid = {s['stop_id']: s for s in stops}
for n in outs:
    for sid in list(stops_of[n]):
        p = byid.get(sid, {}).get('parent_station')
        if p: stops_of[n].add(p)
for n, zo in outs.items():  # a stop two groups share (a station) goes to both
    buf = io.StringIO(); w = csv.DictWriter(buf, fieldnames=list(stops[0].keys()), extrasaction='ignore'); w.writeheader(); w.writerows(s for s in stops if s['stop_id'] in stops_of[n]); zo.writestr('stops.txt', buf.getvalue())
if 'shapes.txt' in z.namelist():
    fh = {n: zo.open('shapes.txt', 'w') for n, zo in outs.items()}; tw = {n: io.TextIOWrapper(f, 'utf-8', newline='') for n, f in fh.items()}; ws = {}
    for s in rd('shapes.txt'):
        for n in shp.get(s['shape_id'], ()):
            if n not in ws: ws[n] = csv.DictWriter(tw[n], fieldnames=list(s.keys()), extrasaction='ignore'); ws[n].writeheader()
            ws[n].writerow(s)
    for n in outs: tw[n].flush(); tw[n].detach(); fh[n].close()
for zo in outs.values(): zo.close()
print({n: os.path.getsize(os.path.join(outdir, n + '.zip'))//1024 for n in outs}, 'KB')
