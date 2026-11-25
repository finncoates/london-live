# Every station's platforms from OpenStreetMap: the stretch of track a train stands on at each numbered platform, so
# a train the live data says is at "platform 7" is drawn on platform 7's track. Works anywhere OSM maps platforms.
#   python -I cities/osm_platforms.py area.osm.pbf stations.json out.json
#   stations.json: [[id, name, lat, lon], ...]   ->   out.json: {id: {"7": [[lat, lon], ...], ...}, ...}
# Where a platform's track comes from, best first:
#   1. the track itself is numbered (railway:track_ref=7), cut to where the station's platforms are
#   2. a platform edge (railway=platform_edge, ref=7): the track beside it
#   3. a platform (railway=platform / public_transport=platform) numbered "7", or "7;8" (an island: one track each
#      side, the numbers running across the station the way its other platforms' do): the track(s) beside it
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace')
import sys, os, json, math, re, osmium
pbf, stf, outf = sys.argv[1], sys.argv[2], sys.argv[3]
R = 6371000.0
ST = json.load(open(stf, encoding='utf-8'))
# only stations in the extract's area (the pbf's header box)
fh = osmium.io.Reader(pbf, osmium.osm.osm_entity_bits.NOTHING); hb = fh.header().box(); fh.close()
if hb.valid(): ST = [s for s in ST if hb.bottom_left.lat < s[2] < hb.top_right.lat and hb.bottom_left.lon < s[3] < hb.top_right.lon]
print(len(ST), 'stations in the area')
G = 0.01 # ~1 km grid of stations, to keep only what is near one
grid = {}
for s in ST: grid.setdefault((int(s[2]/G), int(s[3]/G)), []).append(s)
def near_station(lat, lon):
    i, j = int(lat/G), int(lon/G)
    return any(grid.get((i + a, j + b)) for a in (-1, 0, 1) for b in (-1, 0, 1))
def refs(v):
    if not v: return []
    return [x.strip().upper() for x in re.split(r'[;,/&]| and ', v) if x.strip() and len(x.strip()) <= 4]
TRAIN = {'rail'} # national rail; metro and tram platforms are a later step
class H(osmium.SimpleHandler):
    def __init__(h): super().__init__(); h.tracks, h.plats, h.edges = [], [], []
    def way(h, w):
        t = w.tags; rw = t.get('railway')
        if rw not in ('rail', 'platform', 'platform_edge') and t.get('public_transport') != 'platform': return
        try: pts = [(n.lat, n.lon) for n in w.nodes]
        except osmium.InvalidLocationError: return
        if len(pts) < 2 or not any(near_station(*p) for p in pts[::max(1, len(pts)//4)]): return
        if rw == 'rail':
            if t.get('service') in ('yard', 'spur') or t.get('usage') in ('industrial', 'military'): return
            h.tracks.append({'pts':pts, 'ref':(t.get('railway:track_ref') or '').strip().upper()})
        elif rw == 'platform_edge': h.edges.append({'pts':pts, 'refs':refs(t.get('ref'))})
        else:
            if t.get('train') == 'no' or t.get('subway') == 'yes' or t.get('tram') == 'yes' or t.get('light_rail') == 'yes' or t.get('bus') == 'yes' or t.get('highway') == 'bus_stop': return
            if rw != 'platform' and t.get('train') != 'yes': return
            h.plats.append({'pts':pts, 'refs':refs(t.get('ref') or t.get('local_ref'))})
    def relation(h, r): pass
h = H(); h.apply_file(pbf, locations=True, idx=os.environ.get('OSM_IDX', 'flex_mem'))
for x in h.tracks + h.plats + h.edges: x['bb'] = (min(p[0] for p in x['pts']), max(p[0] for p in x['pts']), min(p[1] for p in x['pts']), max(p[1] for p in x['pts']))
IDX = {} # what lies in each ~1 km cell (by its box), so a station looks only at what is near it
for kind, L in (('t', h.tracks), ('p', h.plats), ('e', h.edges)):
    for x in L:
        for i in range(int(x['bb'][0]/G), int(x['bb'][1]/G) + 1):
            for j in range(int(x['bb'][2]/G), int(x['bb'][3]/G) + 1): IDX.setdefault((kind, i, j), []).append(x)
def cand(kind, s):
    seen, out = set(), []
    for a in (-1, 0, 1):
        for b in (-2, -1, 0, 1, 2):
            for x in IDX.get((kind, int(s[2]/G) + a, int(s[3]/G) + b), []):
                if id(x) not in seen: seen.add(id(x)); out.append(x)
    return out
close = lambda x, s, dla: x['bb'][0] - dla < s[2] < x['bb'][1] + dla and x['bb'][2] - dla*1.7 < s[3] < x['bb'][3] + dla*1.7
print(len(h.tracks), 'tracks', len(h.plats), 'platforms', len(h.edges), 'platform edges')

def local(s):
    la0, lo0 = math.radians(s[2]), math.radians(s[3]); c = math.cos(la0)
    to = lambda p: ((math.radians(p[1]) - lo0)*c*R, (math.radians(p[0]) - la0)*R)
    back = lambda q: (round(math.degrees(la0 + q[1]/R), 6), round(math.degrees(lo0 + q[0]/(c*R)), 6))
    return to, back
def axis(P): # centre, unit direction (principal), half-length
    n = len(P); cx = sum(p[0] for p in P)/n; cy = sum(p[1] for p in P)/n
    sxx = sum((p[0]-cx)**2 for p in P); syy = sum((p[1]-cy)**2 for p in P); sxy = sum((p[0]-cx)*(p[1]-cy) for p in P)
    a = 0.5*math.atan2(2*sxy, sxx - syy); u = (math.cos(a), math.sin(a))
    pr = [(p[0]-cx)*u[0] + (p[1]-cy)*u[1] for p in P]
    return (cx, cy), u, (min(pr), max(pr))
def dens(P, step=5.0): # points every few metres along a line
    out = [P[0]]
    for a, b in zip(P, P[1:]):
        d = math.hypot(b[0]-a[0], b[1]-a[1]); k = max(1, int(d/step))
        out += [(a[0] + (b[0]-a[0])*i/k, a[1] + (b[1]-a[1])*i/k) for i in range(1, k + 1)]
    return out
def rdp(P, eps=1.5):
    if len(P) < 3: return P
    a, b = P[0], P[-1]; dx, dy = b[0]-a[0], b[1]-a[1]; L = math.hypot(dx, dy) or 1e-9
    i, dm = 0, 0
    for k in range(1, len(P) - 1):
        d = abs(dy*(P[k][0]-a[0]) - dx*(P[k][1]-a[1]))/L
        if d > dm: i, dm = k, d
    return rdp(P[:i+1], eps)[:-1] + rdp(P[i:], eps) if dm > eps else [a, b]
def beside(pl, tracks, side=None, maxd=12.0):
    """the track running alongside a platform (pl: its points in metres): the points of the nearest parallel track
    over the platform's length; side -1/+1 picks one side of it (an island), None the nearest either side"""
    (cx, cy), u, (lo, hi) = axis(pl); nx, ny = -u[1], u[0]; best = None
    for T in tracks:
        got = []
        for p in T:
            s = (p[0]-cx)*u[0] + (p[1]-cy)*u[1]; d = (p[0]-cx)*nx + (p[1]-cy)*ny
            if lo - 5 <= s <= hi + 5 and abs(d) <= maxd and (side is None or d*side > 0.5): got.append((s, d, p))
        if len(got) < 3: continue
        # the platform runs along it: the track points cover most of its length and keep a steady distance
        if (max(g[0] for g in got) - min(g[0] for g in got)) < 0.6*(hi - lo): continue
        md = sorted(abs(g[1]) for g in got)[len(got)//2]
        if best is None or md < best[0]: best = (md, [g[2] for g in sorted(got)])
    return best and best[1]

out = {}
for s in ST:
    to, back = local(s)
    def nearby(P, r): return any(abs(p[0]) < r and abs(p[1]) < r for p in P[::max(1, len(P)//6)] + [P[-1]])
    tr = [dict(t, m=dens([to(p) for p in t['pts']])) for t in cand('t', s) if close(t, s, 0.0065)]
    tr = [t for t in tr if nearby(t['m'], 700)]
    if not tr: continue
    pls = [dict(p, m=dens([to(q) for q in p['pts']], 3)) for p in cand('p', s) if close(p, s, 0.0045)]; pls = [p for p in pls if nearby(p['m'], 500)]
    eds = [dict(e, m=dens([to(q) for q in e['pts']], 3)) for e in cand('e', s) if close(e, s, 0.0045)]; eds = [e for e in eds if nearby(e['m'], 500)]
    # a platform belongs to the station it is nearest to (stations a few hundred metres apart keep their own)
    def mine(P):
        (cx, cy), _, _ = axis(P); la, lo = back((cx, cy)); d0 = math.hypot(cx, cy)
        for o in grid.get((int(la/G), int(lo/G)), []) + [x for a in (-1, 0, 1) for b in (-1, 0, 1) for x in grid.get((int(la/G)+a, int(lo/G)+b), [])]:
            if o is s: continue
            t2, _ = local(o); q = t2(back((0, 0)));
            if math.hypot(cx + q[0], cy + q[1]) < d0 - 1: return False
        return d0 < 450
    pls = [p for p in pls if mine(p['m'])]; eds = [e for e in eds if mine(e['m'])]
    res = {}
    # 3. platforms: single numbers, then islands, the numbers running across the station like its others
    zone = [q for p in pls + eds for q in p['m']]
    if pls:
        allp = [q for p in pls for q in p['m']]; (_, _), U, _ = axis(allp); NX, NY = -U[1], U[0]
        across = lambda P: sum(q[0]*NX + q[1]*NY for q in P)/len(P)
        num = lambda r: int(re.match(r'\d+', r).group()) if re.match(r'\d+', r) else None
        xs = [(across(p['m']), num(p['refs'][0])) for p in pls if p['refs'] and num(p['refs'][0]) is not None]
        mx = sum(x for x, _ in xs)/len(xs) if xs else 0; mn = sum(n for _, n in xs)/len(xs) if xs else 0
        up = sum((x - mx)*(n - mn) for x, n in xs) >= 0 # numbers rise as "across" rises
        for p in pls:
            if len(p['refs']) == 1: tk = beside(p['m'], [t['m'] for t in tr]); tk and res.setdefault(p['refs'][0], tk)
            elif len(p['refs']) == 2:
                rs = sorted(p['refs'], key=lambda r: (num(r) is None, num(r) or 0, r)); (_, _), u, _ = axis(p['m'])
                # which way round: "across" for this platform's own sides, compared with the station's
                sgn = 1 if (-u[1])*NX + u[0]*NY >= 0 else -1
                lo_side, hi_side = (-sgn, sgn) if up else (sgn, -sgn)
                for r, sd in ((rs[0], lo_side), (rs[1], hi_side)):
                    tk = beside(p['m'], [t['m'] for t in tr], sd); tk and res.setdefault(r, tk)
    # 2. platform edges (better than a whole platform)
    for e in eds:
        for r in e['refs'][:1]:
            tk = beside(e['m'], [t['m'] for t in tr], None, 6); tk and res.__setitem__(r, tk)
    # 1. numbered tracks (best): cut to the station's platforms, or 300 m round the station
    for t in tr:
        if not t['ref'] or len(t['ref']) > 4: continue
        if zone: keep = [p for p in t['m'] if any(abs(p[0]-q[0]) < 25 and abs(p[1]-q[1]) < 25 for q in zone[::2])]
        else: keep = [p for p in t['m'] if math.hypot(*p) < 300]
        if len(keep) >= 3 and math.hypot(keep[-1][0]-keep[0][0], keep[-1][1]-keep[0][1]) > 40:
            old = res.get(t['ref'])
            if not old or old is not None and len(keep) > len(old): res[t['ref']] = keep
    if res:
        out[s[0]] = {r: [list(back(q)) for q in rdp(P)] for r, P in res.items() if math.hypot(P[-1][0]-P[0][0], P[-1][1]-P[0][1]) > 30}
        if not out[s[0]]: del out[s[0]]
json.dump(out, open(outf, 'w', encoding='utf-8'), separators=(',', ':'))
print(len(out), 'stations with platforms;', sum(len(v) for v in out.values()), 'platforms')
for k in ('WAT', 'LBG', 'KGX', 'EUS', 'VIC', 'LST', 'PAD', 'CHX', 'CST', 'MYB', 'STP', 'FST', 'CLJ'):
    print(' ', k, sorted(out.get(k, {}), key=lambda r: (len(r), r)))
