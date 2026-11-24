# A country's railway stations from a train timetable whose shapes are missing (Belgium's SNCB, Portugal's CP), for
# the National Rail map's station dots: every stop a train calls at, as its parent station.
#   python -I cities/gtfs_rail_stations.py <cc> feed.zip   -> cities/<cc>-stations.json  [id, name, lat, lon]
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace')
import os, sys, json, zipfile, csv, io
HERE = os.path.dirname(os.path.abspath(__file__)); cc, feed = sys.argv[1:3]
z = zipfile.ZipFile(feed); N = {n.split('/')[-1]: n for n in z.namelist()}; rd = lambda n: csv.DictReader(io.TextIOWrapper(z.open(N[n]), 'utf-8-sig'))
TRAIN = {'2'} | {str(t) for t in range(100, 118)}
train = {r['route_id'] for r in rd('routes.txt') if r['route_type'] in TRAIN}
trips = {t['trip_id'] for t in rd('trips.txt') if t['route_id'] in train}
used = set()
for s in rd('stop_times.txt'):
    if s['trip_id'] in trips: used.add(s['stop_id'])
S = {s['stop_id']: s for s in rd('stops.txt')}; st = {}
for sid in used:
    s = S.get(sid)
    if not s: continue
    p = S.get(s.get('parent_station') or '') or s
    if p.get('stop_lat'): st[p['stop_id']] = [p['stop_id'], p['stop_name'], round(float(p['stop_lat']), 5), round(float(p['stop_lon']), 5)]
L = sorted(st.values(), key=lambda x: x[1])
json.dump(L, open(os.path.join(HERE, f'{cc}-stations.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print(cc, len(L), 'stations')
