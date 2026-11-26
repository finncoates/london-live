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
PCS = [] # [d, points, kind, lines, (end node, end node), all points]
for d, p, kd, ln in h.ways:
    cut = [0] + [k for k in range(1, len(p) - 1) if use[p[k][2]] >= 2] + [len(p) - 1]
    for a0, a1 in zip(cut, cut[1:]):
        seg = [(a, b) for a, b, _ in p[a0:a1 + 1]]; q = [[a, b] for a, b in rdp(seg, 1.0/111320)]
        PCS.append([d, q, kd, list(ln), (p[a0][2], p[a1][2]), seg])
pieces = len(PCS)
# OSM's route relations often list one direction's tunnel only: the other one gets its line here, so the line is drawn
# (and its trains run) on both. 1. a Tube or DLR track running alongside one of a line, within 35 m for most of its
# length, is that line's; 2. any piece whose two ends both join that line's pieces (a gap, a crossover) is too
if LINES:
    G = {} # ~50 m cells: tagged Tube/DLR points
    def cell(a, b): return (int(a*2000), int(b*1300))
    for P in PCS:
        if P[3] and P[2][0] in 'sl':
            for a, b in P[5][::1] + [P[5][-1]]: G.setdefault(cell(a, b), []).append((a, b, P[2][0], P[3]))
    def dens_ll(S, step=20):
        out = [S[0]]
        for (a, b), (c, e) in zip(S, S[1:]):
            n = max(1, int(math.hypot((c-a)*111320, (e-b)*69000)/step)); out += [(a + (c-a)*i/n, b + (e-b)*i/n) for i in range(1, n + 1)]
        return out
    n1 = 0
    for P in PCS:
        if P[3] or P[2][0] not in 'sl': continue
        S = dens_ll(P[5]); hits = {}
        for a, b in S:
            c0 = cell(a, b); best, near = 35, () # (the nearest tagged track's lines: the District's twin, not the Piccadilly beside it)
            for x in (-1, 0, 1):
                for y in (-1, 0, 1):
                    for (la, lo, k, ln) in G.get((c0[0]+x, c0[1]+y), []):
                        dd = math.hypot((la-a)*111320, (lo-b)*69000)
                        if k == P[2][0] and dd < best: best, near = dd, ln
            for l in near: hits[l] = hits.get(l, 0) + 1
        got = sorted(l for l, c in hits.items() if c >= 0.8*len(S))
        if got: P[3] = got; n1 += 1
    n2 = 0
    for _ in range(4):
        at = {}
        for P in PCS:
            for nd in P[4]: at.setdefault(nd, []).append(P)
        ch = 0
        for P in PCS:
            if P[3]: continue
            A = set(l for Q in at[P[4][0]] if Q is not P and Q[2][0] == P[2][0] for l in Q[3]); B = set(l for Q in at[P[4][1]] if Q is not P and Q[2][0] == P[2][0] for l in Q[3])
            both = sorted(A & B)
            if both and len(P[5]) and math.hypot((P[5][0][0]-P[5][-1][0])*111320, (P[5][0][1]-P[5][-1][1])*69000) < 3000: P[3] = both; ch += 1
        n2 += ch
        if not ch: break
    print(n1, 'tracks given their line by the one beside them,', n2, 'by both ends')
tiles = {}
for d, q, kd, ln, _, seg in PCS:
    for key in {(math.floor(a*10), math.floor(b*10)) for a, b in seg}: tiles.setdefault(key, []).append([d, q, kd] + ([ln] if ln else []))
# merged with what a square already has (a square on a border gets both countries' tracks; a rebuild adds nothing twice)
for (i, j), v in tiles.items():
    f = os.path.join(out, f'{i}_{j}.json'); old = json.load(open(f)) if os.path.exists(f) else []
    K = lambda x: json.dumps(x[:3], separators=(',', ':')) # (the same track again, now with its lines: the new one stays)
    seen = {K(x) for x in v}; v = v + [x for x in old if K(x) not in seen]
    json.dump(v, open(f, 'w'), separators=(',', ':'))
print(sum(1 for w in h.ways if w[3]), 'with lines;', len(h.ways), 'tracks,', pieces, 'pieces junction to junction;', sum(1 for w in h.ways if w[0]), 'with a direction;', len(tiles), 'squares')
