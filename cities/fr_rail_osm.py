# France's railway drawn from OpenStreetMap's track, region by region, instead of SNCF's line shapes (formes-des-lignes-
# du-rfn), which are schematic: around Bordeaux's Garonne crossing they run ~60 m off the track in 0.7–1.8 km straight
# pieces, across the river where there's no bridge and down Rue Marcel Sembat. Each Geofabrik region done replaces the
# SNCF pieces inside its border (its .poly); regions not done yet keep SNCF's. Then the shared tiles are rebuilt.
#   python -I cities/fr_rail_osm.py aquitaine [more Geofabrik france/ regions…]   (all: every region)
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace')
import os, sys, json, subprocess, urllib.request, time
HERE = os.path.dirname(os.path.abspath(__file__)); B = os.path.join(HERE, '.build'); R = os.path.join(B, 'rail'); O = os.path.join(B, 'osm'); P = os.path.join(B, 'frpoly')
os.makedirs(P, exist_ok=True)
REG = ['alsace', 'aquitaine', 'auvergne', 'basse-normandie', 'bourgogne', 'bretagne', 'centre', 'champagne-ardenne', 'corse', 'franche-comte', 'haute-normandie',
       'ile-de-france', 'languedoc-roussillon', 'limousin', 'lorraine', 'midi-pyrenees', 'nord-pas-de-calais', 'pays-de-la-loire', 'picardie', 'poitou-charentes',
       'provence-alpes-cote-d-azur', 'rhone-alpes']
want = REG if sys.argv[1:] == ['all'] else sys.argv[1:]
GF = 'https://download.geofabrik.de/europe/france/'
def fetch(url, fn):
    req = urllib.request.Request(url, headers={'user-agent': 'LondonLive/1.0'})
    with urllib.request.urlopen(req, timeout=3600) as r:
        n = int(r.headers.get('Content-Length') or 0)
        with open(fn + '.part', 'wb') as f:
            while True:
                b = r.read(1 << 20)
                if not b: break
                f.write(b)
    if n and os.path.getsize(fn + '.part') != n: os.remove(fn + '.part'); raise IOError('truncated ' + url)
    os.replace(fn + '.part', fn)
def poly(reg):  # Geofabrik's border: rings of (lat, lon) (holes, marked '!', ignored)
    fn = os.path.join(P, reg + '.poly')
    if not os.path.exists(fn): fetch(GF + reg + '.poly', fn)
    rings, cur, hole = [], None, False
    for l in open(fn).read().split('\n')[1:]:
        l = l.strip()
        if not l: continue
        if l == 'END':
            if cur is not None: (None if hole else rings.append(cur)); cur = None
            continue
        if cur is None: cur = []; hole = l.startswith('!'); continue
        x, y = map(float, l.split()[:2]); cur.append((y, x))
    return rings
def inside(rings, p):
    c = False
    for r in rings:
        j = len(r) - 1
        for i in range(len(r)):
            a, b = r[i], r[j]
            if (a[0] > p[0]) != (b[0] > p[0]) and p[1] < (b[1]-a[1])*(p[0]-a[0])/(b[0]-a[0]) + a[1]: c = not c
            j = i
    return c
for reg in want:
    t0 = time.time(); out = os.path.join(R, f'fr-{reg}.json')
    # its own copy (the bus builds share cities/.build/osm and clear it whenever they like)
    pbf = os.path.join(B, 'frrail-' + reg + '.osm.pbf'); got = True; have = os.path.join(O, reg + '.osm.pbf')
    try: __import__('shutil').copyfile(have, pbf)
    except OSError: fetch(GF + reg + '-latest.osm.pbf', pbf)
    rings = poly(reg); la = [q[0] for r in rings for q in r]; lo = [q[1] for r in rings for q in r]
    box = f'{min(la)},{min(lo)},{max(la)},{max(lo)}'
    try: subprocess.run([sys.executable, '-I', os.path.join(HERE, 'osm_rail.py'), f'fr-{reg}', pbf, box], check=True, env=dict(os.environ, NO_TILES='1'))
    except subprocess.CalledProcessError: print(reg, 'FAILED: its SNCF lines stay', flush=True); os.path.exists(out) and os.remove(out); os.path.exists(pbf) and os.remove(pbf); continue
    if got: os.remove(pbf)
    # the OSM lines kept only where they're in the region (a way spilling over the border is drawn by its neighbour)
    L = json.load(open(out)); L2 = []
    for l in L:
        run = []
        for q in l:
            if inside(rings, q): run.append(q)
            else:
                if run: run.append(q); L2.append(run) if len(run) > 1 else None; run = []
                else: run = []
        if len(run) > 1: L2.append(run)
    json.dump(L2, open(out, 'w'), separators=(',', ':'))
    print(reg, len(L2), 'OSM track pieces', f'{time.time()-t0:.0f}s', flush=True)
# SNCF's pieces kept only outside the regions now drawn from OSM (the original kept as fr-sncf.json)
src = os.path.join(B, 'fr-sncf.json')
if not os.path.exists(src): os.replace(os.path.join(R, 'fr.json'), src)
done = [poly(r) for r in REG if os.path.exists(os.path.join(R, f'fr-{r}.json'))]
keep = []
for l in json.load(open(src)):
    run = []
    for q in l:
        if any(inside(rs, q) for rs in done):
            if len(run) > 1: keep.append(run + [q])
            run = []
        else: run.append(q)
    if len(run) > 1: keep.append(run)
json.dump(keep, open(os.path.join(R, 'fr.json'), 'w'), separators=(',', ':'))
print(len(done), 'regions from OSM;', len(keep), 'SNCF pieces kept elsewhere', flush=True)
subprocess.run([sys.executable, '-I', os.path.join(HERE, 'rail_tiles.py')], check=True)
