# Add the stations of a city's rail/metro/tram lines to its cities/<city>.json (from the same GTFS feed).
# usage: python3 gtfs_stations.py feed.zip city.json "0:tram,1:metro,..." [south,west,north,east]
# Each station: [id, name, lat, lon, [[line name, colour, kind], ...]]   (id = parent station id, for departures)
import sys, zipfile, csv, io, json, collections, os
zf, jf, typemap = sys.argv[1], sys.argv[2], dict(x.split(':') for x in sys.argv[3].split(','))
BOX = [float(x) for x in sys.argv[4].split(',')] if len(sys.argv) > 4 else None
z = zipfile.ZipFile(zf); rd = lambda n: csv.DictReader(io.TextIOWrapper(z.open(n), 'utf-8-sig'))
data = json.load(open(jf)); colour = {}
for l in data['lines']: colour.setdefault((l['name'], l['kind']), l['col'])
routes = {r['route_id']: (typemap[r['route_type']], r.get('route_short_name') or r.get('route_long_name')) for r in rd('routes.txt') if r['route_type'] in typemap}
pick = {}  # a few trips per (route, shape): enough to see every stop
for t in rd('trips.txt'):
    if t['route_id'] in routes:
        k = (t['route_id'], t.get('shape_id') or t.get('direction_id'))
        if k not in pick: pick[k] = t['trip_id']
trip_route = {tid: rid for (rid, _), tid in pick.items()}
stop_lines = collections.defaultdict(set)
for st in rd('stop_times.txt'):
    rid = trip_route.get(st['trip_id'])
    if rid: stop_lines[st['stop_id']].add(rid)
stops = {s['stop_id']: s for s in rd('stops.txt')}
stations = {}
for sid, rids in stop_lines.items():
    s = stops.get(sid); 
    if not s: continue
    p = stops.get(s.get('parent_station') or '') or s
    lat, lon = float(p['stop_lat']), float(p['stop_lon'])
    if BOX and not (BOX[0] <= lat <= BOX[2] and BOX[1] <= lon <= BOX[3]): continue
    e = stations.setdefault(p['stop_id'], {'name': p['stop_name'], 'lat': lat, 'lon': lon, 'lines': set(), 'child': collections.Counter()})
    e['child'][s['stop_name']] += 1
    for rid in rids: e['lines'].add(routes[rid][::-1])
# platforms' own names when the station's is a long form (e.g. HSL "Kampin metroasema" → "Kamppi")
for e in stations.values():
    if e['child'] and os.environ.get('CHILD_NAMES') == '1': e['name'] = e['child'].most_common(1)[0][0]
# same name within 250 m = one station (two platforms of a tram stop)
import math
merged = {}
for sid, e in sorted(stations.items()):
    key = None
    for k, m in merged.items():
        if m['name'] == e['name'] and math.hypot((m['lat']-e['lat'])*111320, (m['lon']-e['lon'])*111320*math.cos(math.radians(e['lat']))) < 250: key = k; break
    if key: merged[key]['lines'] |= e['lines']
    else: merged[sid] = e
stations = merged
out = []
for sid, e in stations.items():
    lines = sorted(e['lines'], key=lambda x: (['metro','train','tram','ferry'].index(x[1]) if x[1] in ['metro','train','tram','ferry'] else 9, x[0]))
    out.append([sid, e['name'], round(e['lat'], 5), round(e['lon'], 5), [[n, colour.get((n, k), ''), k] for n, k in lines]])
data['stations'] = out
json.dump(data, open(jf, 'w'), separators=(',', ':'), ensure_ascii=False)
print(len(out), 'stations', os.path.getsize(jf), 'bytes')
