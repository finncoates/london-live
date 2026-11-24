# Build a French city for the live map from its open GTFS timetable (transport.data.gouv.fr):
#   cities/fr-<id>.json   its metro / tram / local train / ferry / cable / funicular lines (official colours) + stations
#   cities/busnet/*.json  its bus routes, merged into the shared 0.1° bus tiles (never overwriting other networks)
#   cities/fr-index.json  the city's entry (name, box, files, bus colour) that the map loads at startup
#
#   python -I cities/fr_build.py <id> "<Name>" <gtfs url or local zip> [--agency REGEX] [--box s,w,n,e] [--bus "#hex,#hex"] [--work DIR]
#
# --agency keeps only the routes of matching operators (agency_id or agency_name), to take one city out of a regional
# bundle (Lyon's TCL from the Auvergne-Rhône-Alpes one). --box limits everything to an area; by default the area is
# that of the city's own stops. Lines are drawn in the timetable's own route colours.
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace'); _s.stderr.reconfigure(encoding='utf-8', errors='replace')  # Windows console: never crash on a name
import sys, os, re, io, csv, json, zipfile, subprocess, collections, math, urllib.request, shutil, argparse, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
BASE = '6c9aa8ce'  # the last commit before French cities: its bus tiles are the UK's own
ap = argparse.ArgumentParser(); ap.add_argument('id'); ap.add_argument('name'); ap.add_argument('src')
ap.add_argument('--agency'); ap.add_argument('--box'); ap.add_argument('--bus', default='#7E8BA3,#97A6BF'); ap.add_argument('--work')
ap.add_argument('--types', help='override the type map, e.g. "0:tram,1:metro"'); ap.add_argument('--nobus', action='store_true')
ap.add_argument('--drop', help='regex of line names to leave out (e.g. ^TER$: drawn by the national rail map)')
ap.add_argument('--country', default='fr', help='two-letter prefix of the city file (fr-paris.json, nl-amsterdam.json)')
ap.add_argument('--nolines', action='store_true', help='buses only (no city line file, no map entry of its own)')
ap.add_argument('--roads', default='auto', help='bus routes matched onto OpenStreetMap roads: auto (when the shapes are missing or only join the stops), on, off')
ap.add_argument('--colour', help='NAME=#hex,... for lines the timetable gives no colour (Luas Green, DART)')
ap.add_argument('--kind', help='NAME=kind,... e.g. "ORLYVAL=metro"'); ap.add_argument('--rename', help='NAME=New name,...')
a = ap.parse_args()
work = a.work or os.path.join(HERE, '.build', a.id)  # kept (git-ignored): downloads and each city's own bus routes
os.makedirs(work, exist_ok=True)
feed = os.path.join(work, 'feed.zip')
if os.path.exists(a.src): feed = a.src
elif not os.path.exists(feed):
    req = urllib.request.Request(a.src, headers={'user-agent':'LondonLive/1.0 (+https://github.com/finncoates/london-live)'})
    with urllib.request.urlopen(req, timeout=600) as r, open(feed, 'wb') as f: shutil.copyfileobj(r, f)
z = zipfile.ZipFile(feed)
names = {n.split('/')[-1]: n for n in z.namelist()}  # some feeds put the files in a folder
rd = lambda n: csv.DictReader(io.TextIOWrapper(z.open(names[n]), 'utf-8-sig'))

# 1. one operator out of a bundle (or all of it), as a clean GTFS of its own
agencies = {r.get('agency_id', ''): r.get('agency_name', '') for r in rd('agency.txt')} if 'agency.txt' in names else {}
routes = [r for r in rd('routes.txt') if not a.agency or re.search(a.agency, (r.get('agency_id') or '') + ' ' + agencies.get(r.get('agency_id') or '', ''), re.I)]
if not routes: sys.exit('no routes match')
rids = {r['route_id'] for r in routes}
KEEP = ('route_id', 'service_id', 'trip_id', 'trip_headsign', 'direction_id', 'shape_id')  # only what the tools read: big feeds' trips (TEC, De Lijn) don't fit in memory whole
trips = [{k: t.get(k, '') for k in KEEP} for t in rd('trips.txt') if t['route_id'] in rids]; tids = {t['trip_id'] for t in trips}; sids = {t.get('shape_id') for t in trips}
need_stops = set()
sub = os.path.join(work, 'city.zip')
with zipfile.ZipFile(sub, 'w', zipfile.ZIP_DEFLATED) as out:
    def write(name, rows, fields):
        buf = io.StringIO(); w = csv.DictWriter(buf, fieldnames=fields, extrasaction='ignore'); w.writeheader(); w.writerows(rows); out.writestr(name, buf.getvalue())
    write('routes.txt', routes, list(routes[0].keys()))
    write('trips.txt', trips, list(trips[0].keys()))
    with out.open('stop_times.txt', 'w') as fh: # streamed: a big city's stop times don't fit in memory at once
        txt = io.TextIOWrapper(fh, 'utf-8', newline=''); w = None
        for s in rd('stop_times.txt'):
            if s['trip_id'] not in tids: continue
            if w is None: w = csv.DictWriter(txt, fieldnames=list(s.keys()), extrasaction='ignore'); w.writeheader()
            w.writerow(s); need_stops.add(s['stop_id'])
        txt.flush(); txt.detach()
    stops = list(rd('stops.txt')); byid = {s['stop_id']: s for s in stops}
    for sid in list(need_stops):
        p = byid.get(sid, {}).get('parent_station')
        if p: need_stops.add(p)
    write('stops.txt', [s for s in stops if s['stop_id'] in need_stops], list(stops[0].keys()))
    if 'shapes.txt' in names:
        sh = [s for s in rd('shapes.txt') if s['shape_id'] in sids]
        if sh: write('shapes.txt', sh, list(sh[0].keys()))
    if agencies: out.writestr('agency.txt', z.read(names['agency.txt']))

# 2. the area: the box given, or where the city's stops are (trimmed of the odd far-away stop)
if a.box: S, W, N, E = map(float, a.box.split(','))
else:
    la = sorted(float(byid[s]['stop_lat']) for s in need_stops if s in byid and byid[s]['stop_lat']); lo = sorted(float(byid[s]['stop_lon']) for s in need_stops if s in byid and byid[s]['stop_lon'])
    q = lambda v, f: v[min(len(v) - 1, max(0, int(len(v)*f)))]
    if not la or not lo: sys.exit('no stops with a place in this timetable')
    S, N, W, E = q(la, 0.005) - 0.02, q(la, 0.995) + 0.02, q(lo, 0.005) - 0.03, q(lo, 0.995) + 0.03
box = f'{S:.3f},{W:.3f},{N:.3f},{E:.3f}'

# 3. which route types are which kind of line (basic and extended GTFS types)
def kind(t):
    t = int(t)
    if t in (0, 5) or 900 <= t < 1000: return 'tram'
    if t in (1, 12) or 400 <= t < 500: return 'metro'
    if t == 7 or 1400 <= t < 1500: return 'metro'   # funiculars: drawn like a short metro line
    if t == 2 or 100 <= t < 200: return 'train'
    if t == 4 or 1000 <= t < 1300: return 'ferry'
    if t == 6 or 1300 <= t < 1400: return 'cable'
    return None
types = collections.Counter(r['route_type'] for r in routes)
tmap = a.types or ','.join(f'{t}:{kind(t)}' for t in types if kind(t))
has_shapes = 'shapes.txt' in zipfile.ZipFile(sub).namelist()
colours = sum(1 for r in routes if (r.get('route_color') or '').strip() not in ('', 'FFFFFF', 'ffffff', '000000'))
report = {'id':a.id, 'name':a.name, 'routes':len(routes), 'types':dict(types), 'typemap':tmap, 'shapes':has_shapes, 'coloured_routes':colours, 'box':box}
def shape_quality():
    zz = zipfile.ZipFile(sub); rr = lambda n: csv.DictReader(io.TextIOWrapper(zz.open(n), 'utf-8-sig'))
    if 'shapes.txt' not in zz.namelist(): return None
    bus = {r['route_id'] for r in rr('routes.txt') if r['route_type'] in ('3', '11', '200', '201', '202', '204', '209', '700', '701', '702', '704', '705', '711', '712', '715', '800')}
    bs = {t.get('shape_id') for t in rr('trips.txt') if t['route_id'] in bus and t.get('shape_id')}
    if not bs: return None
    gaps = []; last = {}
    for q in rr('shapes.txt'):
        if q['shape_id'] not in bs: continue
        p = (float(q['shape_pt_lat']), float(q['shape_pt_lon'])); o = last.get(q['shape_id']); last[q['shape_id']] = p
        if o: gaps.append(math.hypot((p[0]-o[0])*111320, (p[1]-o[1])*111320*math.cos(math.radians(p[0]))))
    if gaps: shape_quality.long = sum(g for g in gaps if g > 400)/(sum(gaps) or 1)  # share of the shapes' length in straight jumps (Rouen: partly stop-to-stop)
    gaps.sort(); return gaps[len(gaps)//2] if gaps else None
shape_quality.long = 0
def shapeless_share():  # bus trips with no shape at all (Strasbourg: most of them): those routes would be missing
    zz = zipfile.ZipFile(sub); rr = lambda n: csv.DictReader(io.TextIOWrapper(zz.open(n), 'utf-8-sig'))
    bus = {r['route_id'] for r in rr('routes.txt') if r['route_type'] in ('3', '11', '200', '201', '202', '204', '209', '700', '701', '702', '704', '705', '711', '712', '715', '800')}
    t = [bool(x.get('shape_id')) for x in rr('trips.txt') if x['route_id'] in bus]
    return (len(t) - sum(t))/len(t) if t else 0
def region_pbf():  # the smallest Geofabrik extract that covers the whole city
    od = os.path.join(HERE, '.build', 'osm'); os.makedirs(od, exist_ok=True); ix = os.path.join(od, 'index-v1.json')
    if not os.path.exists(ix): urllib.request.urlretrieve('https://download.geofabrik.de/index-v1.json', ix)
    def inside(pt, poly):
        x, y, c = pt[1], pt[0], False
        for ring in poly:
            for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
                if (y1 > y) != (y2 > y) and x < (x2 - x1)*(y - y1)/(y2 - y1) + x1: c = not c
        return c
    best = None; centre = None  # (centre: the smallest region holding the centre, the fallback when only a huge extract covers the area)
    for f in json.load(open(ix, encoding='utf-8'))['features']:
        g = f.get('geometry'); url = f['properties'].get('urls', {}).get('pbf')
        if not g or not url: continue
        polys = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
        if not f['properties'].get('parent'): continue  # a whole continent (Europe: 30 GB) is never the answer
        mid = ((S + N)/2, (W + E)/2); inset = [((mid[0] + y)/2, (mid[1] + x)/2) for y in (S, N) for x in (W, E)]
        if any(inside(mid, pl) for pl in polys):  # the city's centre (Lille's area reaches into Belgium)...
            xs = [c[0] for pl in polys for c in pl[0]]; ys = [c[1] for pl in polys for c in pl[0]]; area = (max(xs)-min(xs))*(max(ys)-min(ys))
            if not centre or area < centre[0]: centre = (area, url, f['properties']['id'])
            if sum(any(inside(q, pl) for pl in polys) for q in inset) >= 3 and (not best or area < best[0]): best = (area, url, f['properties']['id'])  # ...and most of its area (a national network: the country, not the region in its middle)
    if best and best[0] > 30: best = centre  # never a huge extract (France 4.5 GB, the Alps): a region-wide network takes its centre's region
    if not best: return None
    fn = os.path.join(od, best[2].replace('/', '_') + '.osm.pbf')
    if not os.path.exists(fn):
        req = urllib.request.Request(best[1], headers={'user-agent':'LondonLive/1.0 (+https://github.com/finncoates/london-live)'})
        with urllib.request.urlopen(req, timeout=1800) as r, open(fn + '.part', 'wb') as f:
            want = int(r.headers.get('content-length') or 0); shutil.copyfileobj(r, f)
        if want and os.path.getsize(fn + '.part') != want: os.remove(fn + '.part'); sys.exit(f'{best[2]} extract download cut short')  # (a connection closed early: Hungary's)
        os.replace(fn + '.part', fn)
    return fn
jf = os.path.join(HERE, f'{a.country}-{a.id}.json')
env = dict(os.environ, USE_ROUTE_COLOR='1' if colours else '0', PYTHONIOENCODING='utf-8')
if a.nolines: d = {'lines':[], 'stations':[]}; tmap = ''
elif tmap and has_shapes:
    subprocess.run([sys.executable, '-I', os.path.join(HERE, 'gtfs_lines.py'), sub, jf, tmap, '', box], check=True, env=env)
    subprocess.run([sys.executable, '-I', os.path.join(HERE, 'gtfs_stations.py'), sub, jf, tmap, box], check=True, env=env)
    d = json.load(open(jf, encoding='utf-8'))
    kinds = dict(x.split('=') for x in a.kind.split(',')) if a.kind else {}; ren = dict(x.split('=') for x in a.rename.split(',')) if a.rename else {}
    drop = lambda n: bool(a.drop and re.search(a.drop, n))
    cols = dict(x.split('=') for x in a.colour.split(',')) if a.colour else {}
    d['lines'] = [dict(l, kind=kinds.get(l['name'], l['kind']), name=ren.get(l['name'], l['name']), col=cols.get(l['name'], l['col'])) for l in d['lines'] if not drop(l['name'])]
    sts = []
    for st in d.get('stations', []):
        ls = [[ren.get(x[0], x[0]), cols.get(x[0], x[1]), kinds.get(x[0], x[2])] for x in st[4] if not drop(x[0])]
        if ls: sts.append(st[:4] + [ls])
    d['stations'] = sts
    json.dump(d, open(jf, 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
    # white lines are event shuttles on other lines' track (Lyon's OL Stadium tram): unreadable, and they'd cover the real line
    white = {l['name'] for l in d['lines'] if l['col'].lower() in ('#ffffff', '#fff')}
    if white:
        d['lines'] = [l for l in d['lines'] if l['name'] not in white]
        d['stations'] = [st[:4] + [[x for x in st[4] if x[0] not in white]] for st in d.get('stations', []) if any(x[0] not in white for x in st[4])]
        json.dump(d, open(jf, 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False); report['dropped_white'] = sorted(white)
elif tmap and not has_shapes and (pbf0 := None) is None and any(int(r['route_type']) in (0, 1, 4) or 900 <= int(r['route_type']) < 1000 for r in routes):
    # no shapes (Montpellier, Lille, Le Mans): each stop-to-stop hop routed along OpenStreetMap's tram / metro track
    tl = {}
    for r in routes:
        t = int(r['route_type']); k = 'tram' if t == 0 or 900 <= t < 1000 else 'metro' if t == 1 else 'ferry' if t == 4 else None
        c = (r.get('route_color') or '').strip()
        if k and r.get('route_short_name') and c and c.lower() not in ('ffffff', '000000'): tl[r['route_short_name']] = [r['route_short_name'], '#' + c.upper(), k]
        elif k and r.get('route_short_name'): tl[r['route_short_name']] = [r['route_short_name'], {'tram':'#00985F', 'metro':'#FF6319', 'ferry':'#00B9E4'}[k], k]
    pbf0 = region_pbf(); op = (agencies and list(agencies.values())[0]) or a.name
    if pbf0 and tl:
        subprocess.run([sys.executable, '-I', os.path.join(HERE, 'gtfs_tram_osm.py'), sub, pbf0, jf, json.dumps(tl), op, box], check=True, env=env)
        d = json.load(open(jf, encoding='utf-8')); report['lines_routed'] = 'OpenStreetMap track (no shapes in the timetable)'
    else: d = {'lines':[], 'stations':[]}; json.dump(d, open(jf, 'w', encoding='utf-8'))
elif os.path.exists(jf) and json.load(open(jf, encoding='utf-8')).get('lines'):
    d = json.load(open(jf, encoding='utf-8')); report['lines_kept'] = 'existing file (routed along OpenStreetMap track)'
else:
    d = {'lines':[], 'stations':[]}; json.dump(d, open(jf, 'w', encoding='utf-8'))
    if tmap and not has_shapes: report['warning'] = 'no route shapes: lines not drawn'
report['lines'] = sorted({(l['name'], l['kind'], l['col']) for l in d['lines']}); report['stations'] = len(d.get('stations', []))

# 4. buses: built into a folder of their own, then merged into the shared tiles. Routes follow the timetable's shapes, or,
# when it has none or they only join the stops with straight lines (Nantes), are matched onto OpenStreetMap's roads.
BUS_TYPES = ('3', '11', '200', '201', '202', '204', '209', '700', '701', '702', '704', '705', '711', '712', '715', '800')
if not a.nobus and not any(r['route_type'] in BUS_TYPES for r in routes): report['bus'] = 'no bus routes'
elif not a.nobus:
    bdir = os.path.join(work, 'busnet'); shutil.rmtree(bdir, ignore_errors=True)
    gap = shape_quality(); share = shapeless_share(); report['bus_shape_gap_m'] = gap and round(gap); report['bus_trips_without_shape'] = round(share, 3)
    report['bus_long_jumps'] = round(shape_quality.long, 3)
    roads = a.roads == 'on' or (a.roads == 'auto' and (gap is None or gap > 120 or share > 0.03 or shape_quality.long > 0.15))
    if roads and (pbf := region_pbf()):
        edges = os.path.join(work, 'edges.pkl'); report['bus_roads'] = os.path.basename(pbf)
        subprocess.run([sys.executable, '-I', os.path.join(HERE, 'busnet2.py'), 'match', pbf, edges, sub], check=True, env=env)
        subprocess.run([sys.executable, '-I', os.path.join(HERE, 'busnet2.py'), 'tiles', bdir, edges], check=True, env=dict(env, NO_RAW='1' if gap is None or gap > 120 or shape_quality.long > 0.3 else '0'))  # straight published pieces never kept
    elif has_shapes:
        subprocess.run([sys.executable, '-I', os.path.join(HERE, 'citybus.py'), sub, bdir, str(S), str(W), str(N), str(E)], check=True, env=env)
    # the shared tiles are rebuilt from every French network's routes, each road once (fr_merge.py)
    nt = len(os.listdir(bdir)) if os.path.isdir(bdir) else 0
    if nt: subprocess.run([sys.executable, '-I', os.path.join(HERE, 'fr_merge.py'), os.path.basename(work)], check=True, env=env)  # (its build folder's name)
    report['bus_tiles'] = nt

# 4b. its bus stops (name and place), for the map's bus stop layer (fr_stops.py puts every network's into cities/stops tiles)
if not a.nobus:
    zz = zipfile.ZipFile(sub); rr = lambda n: csv.DictReader(io.TextIOWrapper(zz.open(n), 'utf-8-sig'))
    bus_r = {r['route_id'] for r in rr('routes.txt') if r['route_type'] in BUS_TYPES}
    bus_t = {t['trip_id'] for t in rr('trips.txt') if t['route_id'] in bus_r}
    used = set()
    if bus_t:
        for x in rr('stop_times.txt'):
            if x['trip_id'] in bus_t: used.add(x['stop_id'])
    pts = {}
    for x in rr('stops.txt'):
        if x['stop_id'] in used and x.get('stop_lat'):
            la, lo = round(float(x['stop_lat']), 5), round(float(x['stop_lon']), 5)
            if S <= la <= N and W <= lo <= E: pts[(x['stop_name'], round(la, 4), round(lo, 4))] = [x['stop_name'], la, lo]
    json.dump(list(pts.values()), open(os.path.join(work, 'stops.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':')); report['bus_stops'] = len(pts)
# 5. the city's entry for the map (bus-only networks have none: the France-wide entry covers their buses). An area much
# bigger than a city (a department's boats, a stray far-off stop) gets none either: it would cover other places.
if not a.nolines and (N - S > 1.0 or E - W > 1.4) and not a.box: report['no_entry'] = f'area too big ({N-S:.1f}° x {E-W:.1f}°)'
if a.nolines or report.get('no_entry'):
    print(json.dumps(report, ensure_ascii=False)); sys.exit(0)
ix = os.path.join(HERE, 'fr-index.json'); idx = json.load(open(ix, encoding='utf-8')) if os.path.exists(ix) else []
idx = [c for c in idx if c['id'] != a.id] + [{'id':a.id, 'name':a.name, 'box':[round(S, 3), round(W, 3), round(N, 3), round(E, 3)], 'url':f'cities/{a.country}-{a.id}.json', 'bus':a.bus.split(',')}]
json.dump(idx, open(ix, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print(json.dumps(report, ensure_ascii=False))
