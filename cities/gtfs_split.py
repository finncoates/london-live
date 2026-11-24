# Split a big national GTFS into one small GTFS per group of operators, in a single pass over its stop times (the
# Netherlands' is 1.2 GB: reading it once instead of once per operator).
#   python -I cities/gtfs_split.py feed.zip outdir 'name=agency regex' ['name=agency regex' ...]
#   -> outdir/<name>.zip for each group (agency_id + ' ' + agency_name is matched)
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace'); _s.stderr.reconfigure(encoding='utf-8', errors='replace')  # Windows console: never crash on a name
import sys, os, io, csv, re, zipfile, shutil
feed, outdir, groups = sys.argv[1], sys.argv[2], [g.split('=', 1) for g in sys.argv[3:]]
os.makedirs(outdir, exist_ok=True)
z = zipfile.ZipFile(feed); rd = lambda n: csv.DictReader(io.TextIOWrapper(z.open(n), 'utf-8-sig'))
ag = {a['agency_id']: a['agency_name'] for a in rd('agency.txt')}
gof = lambda aid: next((n for n, rx in groups if not rx.startswith('@') and re.search(rx, (aid or '') + ' ' + ag.get(aid or '', ''))), None)
def gor(r):  # a group is an operator regex, or '@lo-hi': a range of route types (Switzerland's lake boats and mountain lifts)
    for n, rx in groups:
        if rx.startswith('@'):
            lo, _, hi = rx[1:].partition('-')
            if int(lo) <= int(r['route_type']) <= int(hi or lo): return n
        elif re.search(rx, (r.get('agency_id') or '') + ' ' + ag.get(r.get('agency_id') or '', '')): return n
routes = list(rd('routes.txt')); rg = {r['route_id']: gor(r) for r in routes}
tg = {}; tf = None  # trips streamed (Switzerland's are 375 MB): their groups first, then written out
for t in rd('trips.txt'):
    if tf is None: tf = list(t.keys())
    n = rg.get(t['route_id'])
    if n: tg[t['trip_id']] = n
outs = {n: zipfile.ZipFile(os.path.join(outdir, n + '.zip'), 'w', zipfile.ZIP_DEFLATED) for n, _ in groups}
def write(name, rows, fields, key):
    for n, zo in outs.items():
        buf = io.StringIO(); w = csv.DictWriter(buf, fieldnames=fields, extrasaction='ignore'); w.writeheader(); w.writerows(r for r in rows if key(r) == n); zo.writestr(name, buf.getvalue())
used_ag = {n: {r.get('agency_id') for r in routes if rg[r['route_id']] == n} for n in outs}
AG = list(rd('agency.txt'))
for n, zo in outs.items():  # an operator in two groups (trams and buses) goes to both
    buf = io.StringIO(); w = csv.DictWriter(buf, fieldnames=list(AG[0].keys()), extrasaction='ignore'); w.writeheader(); w.writerows(a for a in AG if a['agency_id'] in used_ag[n] or (len(AG) == 1 and used_ag[n])); zo.writestr('agency.txt', buf.getvalue())
write('routes.txt', routes, list(routes[0].keys()), lambda r: rg[r['route_id']])
shp = {}; stops_of = {n: set() for n in outs}
fh = {n: zo.open('trips.txt', 'w') for n, zo in outs.items()}; tw = {n: io.TextIOWrapper(f, 'utf-8', newline='') for n, f in fh.items()}
ws = {n: csv.DictWriter(tw[n], fieldnames=tf, extrasaction='ignore') for n in outs}
for w in ws.values(): w.writeheader()
for t in rd('trips.txt'):
    n = tg.get(t['trip_id'])
    if not n: continue
    ws[n].writerow(t)
    if t.get('shape_id'): shp.setdefault(t['shape_id'], set()).add(n)
for n in outs: tw[n].flush(); tw[n].detach(); fh[n].close()
for name in ('calendar.txt', 'calendar_dates.txt'):  # (service days, whole, to every group)
    if name in z.namelist():
        for zo in outs.values():
            with z.open(name) as src, zo.open(name, 'w') as dst: shutil.copyfileobj(src, dst)
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
