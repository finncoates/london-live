# France's passenger railway network for the live map, from SNCF open data (ressources.data.sncf.com, licence ODbL):
#   formes-des-lignes-du-rfn  the shapes of every line section of the national network, with its status
#   liste-des-gares           every station, its line and whether it takes passengers
# Lines in use with at least one passenger station are drawn (freight-only and closed lines are not), into the same
# 0.5° tiles as Britain's National Rail map (cities/nr/<lat*2>_<lon*2>.json, merged where a tile has both countries)
# and its overview (cities/nr/all.json). Passenger stations go to cities/fr-gares.json: [uic, name, lat, lon].
#   python -I cities/fr_rail.py      (downloads into cities/.build/frnr)
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace'); _s.stderr.reconfigure(encoding='utf-8', errors='replace')  # Windows console: never crash on a name
import os, json, math, subprocess, urllib.request, collections
HERE = os.path.dirname(os.path.abspath(__file__)); B = os.path.join(HERE, '.build', 'frnr'); os.makedirs(B, exist_ok=True)
BASE = '6c9aa8ce'  # before France: the tiles as Britain's own
def get(name):
    fn = os.path.join(B, name + '.geojson')
    if not os.path.exists(fn):
        req = urllib.request.Request(f'https://ressources.data.sncf.com/api/explore/v2.1/catalog/datasets/{name}/exports/geojson', headers={'user-agent':'LondonLive/1.0'})
        with urllib.request.urlopen(req, timeout=600) as r, open(fn, 'wb') as f: f.write(r.read())
    return json.load(open(fn, encoding='utf-8'))['features']
G = get('liste-des-gares'); L = get('formes-des-lignes-du-rfn')
pax = {g['properties']['code_ligne'] for g in G if g['properties'].get('voyageurs') == 'O'}
lines = []
for f in L:
    p = f['properties']
    if p.get('mnemo') != 'EXPLOITE' or p['code_ligne'] not in pax or not f.get('geometry'): continue
    g = f['geometry']; parts = g['coordinates'] if g['type'] == 'MultiLineString' else [g['coordinates']]
    for c in parts:
        if len(c) > 1: lines.append([(round(y, 5), round(x, 5)) for x, y in c])
def dp(p, eps):  # closed loops (a ring line, a circular bus route) split at their farthest point first: measured against
    # a line from a point to itself, the whole loop would collapse to nothing (Copenhagen's M3 did)
    if len(p) > 3 and abs(p[0][0] - p[-1][0]) < 2e-5 and abs(p[0][1] - p[-1][1]) < 3e-5:
        k = max(range(len(p)), key=lambda i: (p[i][0] - p[0][0])**2 + ((p[i][1] - p[0][1])*0.65)**2)
        if 0 < k < len(p) - 1: return _dp_open(p[:k+1], eps)[:-1] + _dp_open(p[k:], eps)
    return _dp_open(p, eps)
_dp_loop = True
def _dp_open(p, eps):  # Douglas-Peucker, metres
    if len(p) < 3: return p
    k = math.cos(math.radians(p[0][0])); a, b = p[0], p[-1]
    ax, ay, bx, by = a[1]*k*111320, a[0]*111320, b[1]*k*111320, b[0]*111320; L2 = math.hypot(bx-ax, by-ay) or 1e-9; best, bi = 0, 0
    for i in range(1, len(p)-1):
        x, y = p[i][1]*k*111320, p[i][0]*111320; d = abs((bx-ax)*(ay-y) - (ax-x)*(by-ay))/L2
        if d > best: best, bi = d, i
    return [a, b] if best <= eps else dp(p[:bi+1], eps)[:-1] + dp(p[bi:], eps)
import sys; sys.setrecursionlimit(100000)
# its lines go to cities/.build/rail/fr.json; rail_tiles.py rebuilds the shared tiles from every country's
os.makedirs(os.path.join(HERE, '.build', 'rail'), exist_ok=True)
json.dump([[[a, b] for a, b in l] for l in lines], open(os.path.join(HERE, '.build', 'rail', 'fr.json'), 'w'), separators=(',', ':'))
# stations: one per UIC code, passenger ones only
st = {}
for g in G:
    p = g['properties']
    if p.get('voyageurs') != 'O' or p['code_uic'] in st: continue
    c = p.get('c_geo') or {}
    if 'lat' in c: st[p['code_uic']] = [p['code_uic'], p['libelle'], round(c['lat'], 5), round(c['lon'], 5)]
json.dump(sorted(st.values(), key=lambda s: s[1]), open(os.path.join(HERE, 'fr-gares.json'), 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
km = sum(math.hypot((b[0]-a[0])*111.32, (b[1]-a[1])*111.32*math.cos(math.radians(a[0]))) for l in lines for a, b in zip(l, l[1:]))
print(len(lines), 'line pieces', round(km), 'km;', len(st), 'passenger stations')
subprocess.run([sys.executable, '-I', os.path.join(HERE, 'rail_tiles.py')], check=True)
