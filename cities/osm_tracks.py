# Every running track, one line each (the rail map, nr_skel.py, merges tracks side by side into one line per corridor;
# a four-track main line is four tracks here), with the direction trains use it in where OpenStreetMap says so.
#   python -I cities/osm_tracks.py area.osm.pbf cities/tracks/ [minlat,minlon,maxlat,maxlon] [lines]
#   -> cities/tracks/<lat*10>_<lon*10>.json (0.1° squares): [[dir, [[lat, lon], ...], kind(, [line, ...])], ...]
#      lines (London): the TfL lines using the track, from OSM's route relations (jubilee, dlr, elizabeth, mildmay…)
#      dir: 1 trains run first point → last, -1 the other way, 0 both ways / not mapped
#      kind: r railway (trains, Overground, Elizabeth line), l light rail (DLR), s subway (Underground); + t in a tunnel
# Running lines, their junctions and the crossovers between them (so tracks link up); no sidings, yards or spurs.
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace')
import sys, os, json, math, osmium
pbf, out = sys.argv[1], sys.argv[2]; box = [float(x) for x in sys.argv[3].split(',')] if len(sys.argv) > 3 and sys.argv[3] != '-' else None; LINES = len(sys.argv) > 4 and sys.argv[4] == 'lines'
os.makedirs(out, exist_ok=True)
KIND = {'rail':'r', 'light_rail':'l', 'subway':'s'} # trains (with the Overground and Elizabeth line), the DLR, the Underground
def keep_way(t):
    if t.get('railway') not in KIND or t.get('service') in ('siding', 'yard', 'spur') or t.get('usage') in ('industrial', 'military', 'tourism', 'test') or t.get('railway:preserved') == 'yes': return None
    pd = t.get('railway:preferred_direction'); d = 1 if pd == 'forward' else -1 if pd == 'backward' else 0
    return (d, KIND[t.get('railway')] + ('t' if t.get('tunnel') in ('yes', 'building_passage') or t.get('layer', '0').startswith('-') else ''))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from osm2pass import read
# London's lines: which TfL line(s) each way carries (route relations: London Underground, DLR, Elizabeth line, Overground, trams)
OVER = ('liberty', 'lioness', 'mildmay', 'suffragette', 'weaver', 'windrush')
def line_of(t):
    nw, ref, name = t.get('network', ''), t.get('ref', ''), t.get('name', '').lower()
    if 'Underground' in nw and ref: return ref.lower().replace(' & ', '-').replace(' ', '-')
    if 'Docklands' in nw or name.startswith('dlr'): return 'dlr'
    if 'elizabeth line' in name or ref == 'Elizabeth': return 'elizabeth'
    if 'London Trams' in nw or 'Tramlink' in nw: return 'tram'
    for o in OVER:
        if o in name or o == ref.lower(): return o
    return None
WL = {}
if LINES:
    for r in osmium.FileProcessor(pbf, osmium.osm.RELATION).with_filter(osmium.filter.KeyFilter('route')):
        if r.tags.get('route') not in ('subway', 'light_rail', 'train', 'tram', 'railway'): continue
        ln = line_of(r.tags)
        if ln: [WL.setdefault(m.ref, set()).add(ln) for m in r.members if m.type == 'w']
    print(len(WL), 'ways on', len({x for v in WL.values() for x in v}), 'lines')
class H: ways = []
h = H()
for (d, kd), p, wid in read(pbf, keep_way, keys=('railway',), with_id=True)[0]:
    p = [(round(a, 6), round(b, 6), n) for a, b, n in p]
    if len(p) < 2 or box and not any(box[0] <= a <= box[2] and box[1] <= b <= box[3] for a, b, _ in p): continue
    h.ways.append((d, p, kd, sorted(WL.get(wid, ()))))
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
for d, p, kd, _ in h.ways:
    for k, (_, _, n) in enumerate(p): use[n] = use.get(n, 0) + (1 if 0 < k < len(p) - 1 else 2)
tiles = {}; pieces = 0
for d, p, kd, ln in h.ways:
    cut = [0] + [k for k in range(1, len(p) - 1) if use[p[k][2]] >= 2] + [len(p) - 1]
    for a0, a1 in zip(cut, cut[1:]):
        seg = [(a, b) for a, b, _ in p[a0:a1 + 1]]; q = [[a, b] for a, b in rdp(seg, 1.0/111320)]; pieces += 1 # ~1 m
        for key in {(math.floor(a*10), math.floor(b*10)) for a, b in seg}: tiles.setdefault(key, []).append([d, q, kd] + ([ln] if ln else []))
# merged with what a square already has (a square on a border gets both countries' tracks; a rebuild adds nothing twice)
for (i, j), v in tiles.items():
    f = os.path.join(out, f'{i}_{j}.json'); old = json.load(open(f)) if os.path.exists(f) else []
    K = lambda x: json.dumps(x[:3], separators=(',', ':')) # (the same track again, now with its lines: the new one stays)
    seen = {K(x) for x in v}; v = v + [x for x in old if K(x) not in seen]
    json.dump(v, open(f, 'w'), separators=(',', ':'))
print(sum(1 for w in h.ways if w[3]), 'with lines;', len(h.ways), 'tracks,', pieces, 'pieces junction to junction;', sum(1 for w in h.ways if w[0]), 'with a direction;', len(tiles), 'squares')
