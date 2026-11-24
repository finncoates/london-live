# Bus stops for networks built before fr_build.py saved them: for each cities/.build/<network> without stops.json, its
# bus stops from its own timetable (city.zip if kept, else feed.zip, else downloaded again from the URL in fr_all.log and
# deleted after). Then run fr_stops.py.
#   python -I cities/stops_backfill.py
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace'); _s.stderr.reconfigure(encoding='utf-8', errors='replace')
import os, json, zipfile, csv, io, urllib.request, shutil, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); B = os.path.join(HERE, '.build')
BUS = ('3', '11', '700', '701', '702', '704', '705', '711', '712', '715', '800')
urls = {}
if os.path.exists(os.path.join(B, 'fr_all.log')):
    for line in open(os.path.join(B, 'fr_all.log'), encoding='utf-8'):
        try: j = json.loads(line)
        except Exception: continue
        urls[j['id']] = j
cat = {x['slug']: x for x in json.load(open(os.path.join(B, 'fr_catalogue.json'), encoding='utf-8'))} if os.path.exists(os.path.join(B, 'fr_catalogue.json')) else {}
def url_of(i):
    j = urls.get(i)
    if not j: return None
    x = cat.get(j['slug']) or {}
    g = [r for r in x.get('resources', []) if r.get('format') == 'GTFS' and r.get('is_available')]
    return max(g, key=lambda r: ('flex' not in ((r.get('title') or '') + (r.get('url') or '')).lower(), ((r.get('metadata') or {}).get('stats') or {}).get('routes_count') or 0, r.get('updated') or ''))['url'] if g else None
def stops_of(zp, box):
    z = zipfile.ZipFile(zp); N = {n.split('/')[-1]: n for n in z.namelist()}; rd = lambda n: csv.DictReader(io.TextIOWrapper(z.open(N[n]), 'utf-8-sig'))
    r = {x['route_id'] for x in rd('routes.txt') if x['route_type'] in BUS}
    t = {x['trip_id'] for x in rd('trips.txt') if x['route_id'] in r}
    used = set()
    for x in rd('stop_times.txt'):
        if x['trip_id'] in t: used.add(x['stop_id'])
    out = {}
    for x in rd('stops.txt'):
        if x['stop_id'] in used and x.get('stop_lat'):
            la, lo = round(float(x['stop_lat']), 5), round(float(x['stop_lon']), 5)
            if not box or (box[0] <= la <= box[2] and box[1] <= lo <= box[3]): out[(x['stop_name'], round(la, 4), round(lo, 4))] = [x['stop_name'], la, lo]
    return list(out.values())
idx = {c['id']: c['box'] for c in json.load(open(os.path.join(HERE, 'fr-index.json'), encoding='utf-8'))}
done = 0
for i in sorted(os.listdir(B)):
    d = os.path.join(B, i)
    if not os.path.isdir(os.path.join(d, 'busnet')) or os.path.exists(os.path.join(d, 'stops.json')): continue
    zp = next((os.path.join(d, f) for f in ('city.zip', 'feed.zip') if os.path.exists(os.path.join(d, f))), None); tmp = None
    if not zp:
        u = url_of(i)
        if not u: print(i, 'no timetable to read'); continue
        tmp = os.path.join(tempfile.gettempdir(), 'backfill.zip')
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={'user-agent':'LondonLive/1.0'}), timeout=900) as r, open(tmp, 'wb') as f: shutil.copyfileobj(r, f)
        except Exception as e: print(i, 'download failed', e); continue
        zp = tmp
    try:
        s = stops_of(zp, idx.get(i)); json.dump(s, open(os.path.join(d, 'stops.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':')); done += 1; print(i, len(s), 'stops', flush=True)
    except Exception as e: print(i, 'failed', e)
    if tmp and os.path.exists(tmp): os.remove(tmp)
print(done, 'networks backfilled')
