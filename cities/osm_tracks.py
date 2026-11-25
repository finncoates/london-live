# Every running track, one line each (the rail map, nr_skel.py, merges tracks side by side into one line per corridor;
# a four-track main line is four tracks here), with the direction trains use it in where OpenStreetMap says so.
#   python -I cities/osm_tracks.py area.osm.pbf cities/tracks/ [minlat,minlon,maxlat,maxlon]
#   -> cities/tracks/<lat*10>_<lon*10>.json (0.1° squares): [[dir, [[lat, lon], ...], kind], ...]
#      dir: 1 trains run first point → last, -1 the other way, 0 both ways / not mapped
#      kind: r railway (trains, Overground, Elizabeth line), l light rail (DLR), s subway (Underground); + t in a tunnel
# Running lines, their junctions and the crossovers between them (so tracks link up); no sidings, yards or spurs.
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace')
import sys, os, json, math, osmium
pbf, out = sys.argv[1], sys.argv[2]; box = [float(x) for x in sys.argv[3].split(',')] if len(sys.argv) > 3 else None
os.makedirs(out, exist_ok=True)
KIND = {'rail':'r', 'light_rail':'l', 'subway':'s'} # trains (with the Overground and Elizabeth line), the DLR, the Underground
def keep_way(t):
    if t.get('railway') not in KIND or t.get('service') in ('siding', 'yard', 'spur') or t.get('usage') in ('industrial', 'military', 'tourism', 'test') or t.get('railway:preserved') == 'yes': return None
    pd = t.get('railway:preferred_direction'); d = 1 if pd == 'forward' else -1 if pd == 'backward' else 0
    return (d, KIND[t.get('railway')] + ('t' if t.get('tunnel') in ('yes', 'building_passage') or t.get('layer', '0').startswith('-') else ''))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from osm2pass import read
class H: ways = []
h = H()
for (d, kd), p in read(pbf, keep_way, keys=('railway',))[0]:
    p = [(round(a, 6), round(b, 6), n) for a, b, n in p]
    if len(p) < 2 or box and not any(box[0] <= a <= box[2] and box[1] <= b <= box[3] for a, b, _ in p): continue
    h.ways.append((d, p, kd))
def rdp(P, eps):
    if len(P) < 3: return P
    k = math.cos(math.radians(P[0][0])); a, b = P[0], P[-1]; dx, dy = (b[1]-a[1])*k, b[0]-a[0]; L = math.hypot(dx, dy) or 1e-12
    i, dm = 0, 0
    for j in range(1, len(P) - 1):
        d = abs(dy*(P[j][1]-a[1])*k - dx*(P[j][0]-a[0]))/L
        if d > dm: i, dm = j, d
    return rdp(P[:i+1], eps)[:-1] + rdp(P[i:], eps) if dm > eps else [a, b]
# split at every junction (a node two tracks share: points, crossovers, where one track's way ends and the next begins),
# so the page can join them into a network of tracks: each piece runs junction to junction, its ends exact (6 decimals)
use = {}
for d, p, kd in h.ways:
    for k, (_, _, n) in enumerate(p): use[n] = use.get(n, 0) + (1 if 0 < k < len(p) - 1 else 2)
tiles = {}; pieces = 0
for d, p, kd in h.ways:
    cut = [0] + [k for k in range(1, len(p) - 1) if use[p[k][2]] >= 2] + [len(p) - 1]
    for a0, a1 in zip(cut, cut[1:]):
        seg = [(a, b) for a, b, _ in p[a0:a1 + 1]]; q = [[a, b] for a, b in rdp(seg, 1.0/111320)]; pieces += 1 # ~1 m
        for key in {(math.floor(a*10), math.floor(b*10)) for a, b in seg}: tiles.setdefault(key, []).append([d, q, kd])
# merged with what a square already has (a square on a border gets both countries' tracks; a rebuild adds nothing twice)
for (i, j), v in tiles.items():
    f = os.path.join(out, f'{i}_{j}.json'); old = json.load(open(f)) if os.path.exists(f) else []
    seen = {json.dumps(x, separators=(',', ':')) for x in v}; v = v + [x for x in old if json.dumps(x, separators=(',', ':')) not in seen]
    json.dump(v, open(f, 'w'), separators=(',', ':'))
print(len(h.ways), 'tracks,', pieces, 'pieces junction to junction;', sum(1 for d, _, _ in h.ways if d), 'with a direction;', len(tiles), 'squares')
