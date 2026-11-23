# Build every French public-transport network in mainland France from the national catalogue (transport.data.gouv.fr):
# urban and intercity buses into the bus tiles; networks with trams / metro / cable / funicular / boats also get a city
# file. Regional bundles, national operators (SNCF, FlixBus, BlaBlaCar…), school-only networks and the networks already
# built by hand are left out. One network at a time (the road matching needs memory); a log lets it pick up where it left.
#   python -I cities/fr_all.py [--limit N]
import os, sys, json, re, subprocess, shutil, urllib.request, time, unicodedata
HERE = os.path.dirname(os.path.abspath(__file__)); B = os.path.join(HERE, '.build'); LOG = os.path.join(B, 'fr_all.log')
os.makedirs(B, exist_ok=True)
cat = os.path.join(B, 'fr_catalogue.json')
if not os.path.exists(cat) or time.time() - os.path.getmtime(cat) > 86400:
    req = urllib.request.Request('https://transport.data.gouv.fr/api/datasets', headers={'user-agent':'LondonLive/1.0 (+https://github.com/finncoates/london-live)'})
    with urllib.request.urlopen(req, timeout=300) as r, open(cat, 'wb') as f: shutil.copyfileobj(r, f)
done = {}
if os.path.exists(LOG):
    for line in open(LOG, encoding='utf-8'):
        try: j = json.loads(line); done.update({j['slug']: j} if j.get('ok') else {})
        except Exception: pass
OVERSEAS = re.compile(r'Martinique|Guadeloupe|R[ée]union|Guyane|Mayotte|Cal[ée]donie|Polyn[ée]sie|Saint-Martin|Saint-Barth|Wallis|Miquelon|Grand Sud Cara|Cara[ïi]be|Cap Excellence|CINOR|CIVIS|CIREST|TCO|Estival|Nord Basse-Terre|Riviera du Levant', re.I)
SKIP = re.compile(r'^Agr[ée]gat|SNCF|FlixBus|BlaBlaCar|Eurostar|Trenitalia|Renfe|europ[ée]en|^R[ée]seau scolaire|scolaire de |Navettes? A[ée]roport|covoiturage|TER\b|a[ée]rien', re.I)
BUILT = re.compile(r'le-de-france-mobilit|offres-de-services-bus-tram-et-scolaire|ilevia|versions-des-horaires-theoriques-des-lignes-de-bus|tisseo|reseaux-de-transports-en-commun-de-la-metropo|donnees-statiques-et-dynamiques-du-reseau-de-trans|naolib|donnees-theoriques-gtfs-et-temps-reel-siri-li|offre-de-transport-tam-en-temps-reel')
RAILISH = {'tramway', 'subway', 'funicular', 'gondola', 'cable_car', 'ferry'}
jobs = []
for x in json.load(open(cat, encoding='utf-8')):
    if x['type'] != 'public-transit': continue
    area = ', '.join(a['nom'] for a in x['covered_area'])
    if SKIP.search(x['title']) or OVERSEAS.search(x['title'] + ' ' + area) or BUILT.search(x['slug']): continue
    g = [r for r in x['resources'] if r.get('format') == 'GTFS' and r.get('is_available')]
    if not g: continue
    best = max(g, key=lambda r: r.get('updated') or ''); md = best.get('metadata') or {}
    if (md.get('end_date') or '9999') < time.strftime('%Y-%m-%d'): continue  # an expired timetable: nothing runs on it
    modes = set(md.get('modes') or [])
    # a city file for trams / metro / cable / funicular, and for local boats; not for sea crossings (Brittany Ferries to
    # Portsmouth, Corsica): their 'city' would stretch across the sea, and the timetable already shows them
    sea = re.search(r'Brittany|Corsica|Transmanche|DFDS|P&O|M[ée]ridionale|Irish|Stena|Condor|maritime -', x['title'], re.I)
    city = bool(modes & (RAILISH - {'ferry'})) or ('ferry' in modes and not sea)
    jobs.append(dict(slug=x['slug'], title=x['title'], area=area, url=best['url'], modes=sorted(modes), city=city, sea=bool(sea)))
lim = int(sys.argv[sys.argv.index('--limit') + 1]) if '--limit' in sys.argv else len(jobs)
import hashlib
def ident(j):  # a short file-safe id from the network's slug (+ a hash: many slugs start the same way)
    s = unicodedata.normalize('NFKD', j['slug']).encode('ascii', 'ignore').decode().lower()
    return 'n-' + re.sub(r'[^a-z0-9]+', '-', s)[:32].strip('-') + '-' + hashlib.sha1(j['slug'].encode()).hexdigest()[:6]
def place(j):  # the map's name for a network with its own city file: its main town
    t = re.sub(r'^(R[ée]seaux? (urbains?|interurbains?)( et (scolaire|interurbain|p[ée]riurbain))?|R[ée]seau)\s*', '', j['title']).strip()
    a = re.sub(r'^(CA|CU|CC|M[ée]tropole|Communaut[ée].*? de)\s+(du |de la |de l\'|des |de |d\')?', '', j['area'].split(',')[0]).strip()
    return a or t
print(len(jobs), 'networks;', sum(j['city'] for j in jobs), 'with trams/boats/cable;', sum(1 for j in jobs if j['slug'] in done), 'done before')
n = 0
for j in jobs:
    if j['slug'] in done or n >= lim: continue
    n += 1; i = ident(j); t0 = time.time()
    args = [sys.executable, '-I', os.path.join(HERE, 'fr_build.py'), i, place(j), j['url']] + ([] if j['city'] else ['--nolines']) + (['--nobus'] if j['sea'] else [])
    p = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace', env=dict(os.environ, PYTHONIOENCODING='utf-8'), timeout=5400)
    rep = None
    for line in reversed(p.stdout.splitlines()):
        if line.startswith('{'):
            try: rep = json.loads(line); break
            except Exception: pass
    out = dict(slug=j['slug'], id=i, title=j['title'], ok=p.returncode == 0 and rep is not None, secs=round(time.time() - t0), report=rep,
               error=None if p.returncode == 0 else (p.stderr or p.stdout)[-600:])
    with open(LOG, 'a', encoding='utf-8') as f: f.write(json.dumps(out, ensure_ascii=False) + '\n')
    print(n, i, 'ok' if out['ok'] else 'FAILED', out['secs'], 's', (rep or {}).get('lines', '')[:3] if rep else (out['error'] or '')[-150:], flush=True)
    for fn in ('feed.zip', 'city.zip', 'edges.pkl'):  # keep only its bus routes (and the log): the disk is small
        try: os.remove(os.path.join(B, i, fn))
        except OSError: pass
    osm = os.path.join(B, 'osm')
    while shutil.disk_usage(B).free < 4e9 and os.path.isdir(osm):  # running low: drop the oldest OSM extract
        pb = sorted((os.path.getmtime(os.path.join(osm, f)), f) for f in os.listdir(osm) if f.endswith('.pbf'))
        if not pb: break
        os.remove(os.path.join(osm, pb[0][1]))
