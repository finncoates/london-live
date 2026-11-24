# Shapes for a timetable that has none, as straight lines from stop to stop — right only for lines that do run straight
# between their stations (Zagreb's funicular and the Sljeme cable car), so the city's line file can draw them.
#   python -I cities/gtfs_straight_shapes.py in.zip out.zip
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace')
import sys, zipfile, csv, io, collections
src, dst = sys.argv[1:3]
zi = zipfile.ZipFile(src); N = {n.split('/')[-1]: n for n in zi.namelist()}
rd = lambda n: list(csv.DictReader(io.TextIOWrapper(zi.open(N[n]), 'utf-8-sig')))
stops = {s['stop_id']: s for s in rd('stops.txt')}
seq = collections.defaultdict(list)
for st in rd('stop_times.txt'): seq[st['trip_id']].append((int(st['stop_sequence']), st['stop_id']))
trips = rd('trips.txt'); shapes = {}; tcols = list(trips[0].keys()) + ([] if 'shape_id' in trips[0] else ['shape_id'])
for t in trips:
    key = tuple(s for _, s in sorted(seq[t['trip_id']]))
    t['shape_id'] = shapes.setdefault(key, 'straight-%d' % len(shapes))
def csvs(rows, cols):
    o = io.StringIO(); w = csv.DictWriter(o, cols, extrasaction='ignore'); w.writeheader(); w.writerows(rows); return o.getvalue()
with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as zo:
    for n, full in N.items():
        if n.endswith('.txt') and n not in ('trips.txt', 'shapes.txt'): zo.writestr(n, zi.read(full))
    zo.writestr('trips.txt', csvs(trips, tcols))
    pts = [{'shape_id': sid, 'shape_pt_lat': stops[s]['stop_lat'], 'shape_pt_lon': stops[s]['stop_lon'], 'shape_pt_sequence': i}
           for key, sid in shapes.items() for i, s in enumerate(key)]
    zo.writestr('shapes.txt', csvs(pts, ['shape_id', 'shape_pt_lat', 'shape_pt_lon', 'shape_pt_sequence']))
print(len(shapes), 'straight shapes ->', dst)
