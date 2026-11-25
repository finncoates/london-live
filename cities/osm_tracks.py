# Every running track, one line each (the rail map, nr_skel.py, merges tracks side by side into one line per corridor;
# a four-track main line is four tracks here), with the direction trains use it in where OpenStreetMap says so.
#   python -I cities/osm_tracks.py area.osm.pbf cities/tracks/ [minlat,minlon,maxlat,maxlon]
#   -> cities/tracks/<lat*10>_<lon*10>.json (0.1° squares): [[dir, [[lat, lon], ...]], ...]
#      dir: 1 trains run first point → last, -1 the other way, 0 both ways / not mapped
# Running lines, their junctions and the crossovers between them (so tracks link up); no sidings, yards or spurs.
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace')
import sys, os, json, math, osmium
pbf, out = sys.argv[1], sys.argv[2]; box = [float(x) for x in sys.argv[3].split(',')] if len(sys.argv) > 3 else None
os.makedirs(out, exist_ok=True)
class H(osmium.SimpleHandler):
    def __init__(h): super().__init__(); h.ways = []
    def way(h, w):
        t = w.tags
        if t.get('railway') != 'rail' or t.get('service') in ('siding', 'yard', 'spur') or t.get('usage') in ('industrial', 'military', 'tourism', 'test') or t.get('railway:preserved') == 'yes': return
        try: p = [(round(n.lat, 6), round(n.lon, 6)) for n in w.nodes]
        except osmium.InvalidLocationError: return
        if len(p) < 2: return
        if box and not any(box[0] <= a <= box[2] and box[1] <= b <= box[3] for a, b in p): return
        pd = t.get('railway:preferred_direction'); d = 1 if pd == 'forward' else -1 if pd == 'backward' else 0
        h.ways.append((d, p))
h = H(); h.apply_file(pbf, locations=True, idx=os.environ.get('OSM_IDX', 'flex_mem'))
def rdp(P, eps):
    if len(P) < 3: return P
    k = math.cos(math.radians(P[0][0])); a, b = P[0], P[-1]; dx, dy = (b[1]-a[1])*k, b[0]-a[0]; L = math.hypot(dx, dy) or 1e-12
    i, dm = 0, 0
    for j in range(1, len(P) - 1):
        d = abs(dy*(P[j][1]-a[1])*k - dx*(P[j][0]-a[0]))/L
        if d > dm: i, dm = j, d
    return rdp(P[:i+1], eps)[:-1] + rdp(P[i:], eps) if dm > eps else [a, b]
tiles = {}
for d, p in h.ways:
    q = [[round(a, 5), round(b, 5)] for a, b in rdp(p, 1.0/111320)] # ~1 m
    for key in {(math.floor(a*10), math.floor(b*10)) for a, b in p}: tiles.setdefault(key, []).append([d, q])
for (i, j), v in tiles.items(): json.dump(v, open(os.path.join(out, f'{i}_{j}.json'), 'w'), separators=(',', ':'))
print(len(h.ways), 'tracks;', sum(1 for d, _ in h.ways if d), 'with a direction;', len(tiles), 'squares')
