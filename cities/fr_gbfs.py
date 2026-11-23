# French bikes and scooters for hire (GBFS, from the national catalogue) for the map's "Bikes & scooters" layer:
# each feed is read once here to find where it is (its stations' or vehicles' middle) and checked that a browser may
# read it (CORS); feeds are grouped into cities (within 25 km). -> cities/gbfs-fr.json  [[city, lat, lon, [[name, url, colour]]]]
#   python -I cities/fr_gbfs.py
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace'); _s.stderr.reconfigure(encoding='utf-8', errors='replace')  # Windows console: never crash on a name
import json, os, urllib.request, urllib.parse, concurrent.futures, math, re, statistics
HERE = os.path.dirname(os.path.abspath(__file__)); cat = json.load(open(os.path.join(HERE, '.build', 'fr_catalogue.json'), encoding='utf-8'))
UA = {'user-agent':'LondonLive/1.0 (+https://github.com/finncoates/london-live)', 'origin':'https://finncoates.github.io'}
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=20) as r: return r.headers.get('access-control-allow-origin'), json.load(r)
COL = {'velib':'#6B9E2E', "vélo'v":'#E2001A', 'velov':'#E2001A', 'v3':'#E3007E', 'vcub':'#E3007E', 'dott':'#1E9BE9', 'lime':'#00DE00', 'tier':'#0E1A50', 'bird':'#262626', 'pony':'#F7B500', 'voi':'#F26961', 'bolt':'#2FB863', 'cityscoot':'#00A0DF', 'cooltra':'#00C1D5', 'yego':'#F7B500', 'zoov':'#00BFA5'}
jobs = []
for x in cat:
    if x['type'] != 'vehicles-sharing' or re.search(r'autopartage|voitures?|scooters? [ée]lectriques? Cityscoot|Cityscoot', x['title'], re.I): continue  # bikes and kick scooters only (no car sharing)
    for r in x['resources']:
        if (r.get('format') or '').lower() == 'gbfs' and r.get('is_available') and r.get('url'):
            jobs.append((x['title'], ', '.join(a['nom'] for a in x['covered_area']), r.get('original_url') or r['url']))
def where(job):
    title, area, url = job
    try:
        cors, d = get(url); dd = d.get('data') or {}
        feeds = dd.get('feeds') or next((v.get('feeds') for v in dd.values() if isinstance(v, dict) and v.get('feeds')), None) or []
        F = {f['name']: f['url'] for f in feeds}
        pts = []
        if 'station_information' in F: pts = [(float(s['lat']), float(s['lon'])) for s in get(F['station_information'])[1]['data'].get('stations', [])]
        if not pts:
            for k in ('vehicle_status', 'free_bike_status'):
                if k in F: pts = [(float(b['lat']), float(b['lon'])) for b in (get(F[k])[1]['data'].get('vehicles') or get(F[k])[1]['data'].get('bikes') or []) if b.get('lat')]; break
        pts = [p for p in pts if 41 < p[0] < 51.5 and -5.5 < p[1] < 9.8]
        if not pts: return None
        hosts = {urllib.parse.urlparse(u).hostname for u in [url, *F.values()]}
        name = re.sub(r'^(V[ée]los?( et trottinettes)?|Trottinettes|VLS)\s+', '', re.sub(r'\s*[-–(].*$', '', title)).strip()
        col = next((c for k, c in COL.items() if k in (title + ' ' + url).lower()), '#00A77F')
        return dict(hosts=sorted(hosts), proxy=cors not in ('*', 'https://finncoates.github.io'), name=name, area=area.split(',')[0], url=url, col=col, lat=statistics.median(p[0] for p in pts), lon=statistics.median(p[1] for p in pts), n=len(pts))
    except Exception as e: return None
with concurrent.futures.ThreadPoolExecutor(12) as ex: found = [r for r in ex.map(where, jobs) if r]
# a place name: the nearest built city (fr-index) within 25 km, else the area without 'CA du…', else the nearest station's town
idx = json.load(open(os.path.join(HERE, 'fr-index.json'), encoding='utf-8')); gares = json.load(open(os.path.join(HERE, 'fr-gares.json'), encoding='utf-8'))
km = lambda a, b: math.hypot((a[0] - b[0])*111, (a[1] - b[1])*111*math.cos(math.radians(a[0])))
def label(f):
    near = [(km((f['lat'], f['lon']), ((c['box'][0] + c['box'][2])/2, (c['box'][1] + c['box'][3])/2)), c['name']) for c in idx]
    near = [n for n in near if n[0] < 25]
    if near: return min(near)[1]
    a = re.sub(r"^(CA|CU|CC|M[ée]tropole|Communaut[ée].*? de)\s+(du |de la |de l'|des |de |d')?", '', f['area']).strip()
    if a and not re.search(r'^(France|Grand Est|Auvergne|Centre-Val|Occitanie|Nouvelle|Hauts|Bretagne|Normandie|Pays de la Loire|Bourgogne|Provence)', a): return a
    g = min(gares, key=lambda g: km((f['lat'], f['lon']), (g[2], g[3]))); return re.sub(r'\s.*$', '', g[1])
cities = []
for f in sorted(found, key=lambda f: -f['n']):
    sysd = [f['name'], ('relay:' if f['proxy'] else '') + f['url'], f['col']]
    c = next((c for c in cities if km((c[1], c[2]), (f['lat'], f['lon'])) < 25), None)
    if c:
        if sysd[1] not in [x[1] for x in c[3]]: c[3].append(sysd)
    else: cities.append([label(f), round(f['lat'], 3), round(f['lon'], 3), [sysd]])
hosts = sorted({h for f in found if f['proxy'] for h in f['hosts'] if h})
json.dump(hosts, open(os.path.join(HERE, 'gbfs-fr-hosts.json'), 'w'), indent=0)
json.dump(cities, open(os.path.join(HERE, 'gbfs-fr.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print(len(jobs), 'feeds;', len(found), 'usable (', sum(f['proxy'] for f in found), 'through the relay);', len(cities), 'cities:', ', '.join(c[0] for c in cities[:25]))
