# Long-distance coach network (National Express, FlixBus, Scottish Citylink…): every coach route from the Bus Open Data
# timetables, routed stop to stop along the main roads of Great Britain (OpenStreetMap), each road drawn once per operator.
#   python3 coachnet.py pats.json great-britain.osm.pbf out.json
# pats.json = {"pats": [[operator, line, [stop ids…]]…], "stops": {id: [lat, lon, name]}}
import sys, json, math, collections
import numpy as np, osmium
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

pf, pbf, out = sys.argv[1:4]
D = json.load(open(pf)); S = D['stops']
MAIN = {'motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary', 'primary_link', 'secondary', 'secondary_link', 'tertiary', 'tertiary_link'}
class H(osmium.SimpleHandler):
    def __init__(s): super().__init__(); s.refs = []; s.lat = []; s.lon = []; s.cut = [0]
    def way(s, w):
        if w.tags.get('highway') not in MAIN: return
        try:
            for n in w.nodes: s.refs.append(n.ref); s.lat.append(n.location.lat); s.lon.append(n.location.lon)
        except osmium.InvalidLocationError: del s.refs[s.cut[-1]:]; del s.lat[s.cut[-1]:]; del s.lon[s.cut[-1]:]; return
        s.cut.append(len(s.refs))
h = H(); h.apply_file(pbf, locations=True, idx='flex_mem')
refs = np.array(h.refs, dtype=np.int64); lat = np.array(h.lat); lon = np.array(h.lon); cut = np.array(h.cut)
uniq, inv = np.unique(refs, return_inverse=True); N = len(uniq)
NLAT = np.zeros(N); NLON = np.zeros(N); NLAT[inv] = lat; NLON[inv] = lon
a = []; b = []
for i in range(len(cut) - 1):
    s0, s1 = cut[i], cut[i+1]
    if s1 - s0 > 1: a.append(inv[s0:s1-1]); b.append(inv[s0+1:s1])
a = np.concatenate(a); b = np.concatenate(b)
k = np.cos(np.radians(54)); w = np.hypot((NLAT[a]-NLAT[b])*111320, (NLON[a]-NLON[b])*111320*k) + 0.01
G = csr_matrix((np.concatenate([w, w]), (np.concatenate([a, b]), np.concatenate([b, a]))), shape=(N, N))
print('main roads:', N, 'nodes', len(a), 'edges', flush=True)
tree = cKDTree(np.c_[NLAT*111320, NLON*111320*k])
PORTS = {'Dover': (51.1256, 1.3271), 'Folkestone (Eurotunnel)': (51.0937, 1.1300), 'Holyhead': (53.3086, -4.6316), 'Cairnryan': (54.9710, -5.0190)}
def snap(sid, other=None):
    q = S[sid]; d, i = tree.query((q[0]*111320, q[1]*111320*k))
    if d < 2000: return int(i)
    if other is None: return None
    # abroad: the British part of the route runs to the port it leaves Britain from
    nm = S[sid][2] + ' ' + S[other][2]
    port = PORTS['Folkestone (Eurotunnel)'] if 'Eurotunnel' in nm else PORTS['Dover'] if q[1] > -2 else PORTS['Cairnryan'] if q[0] > 54 else PORTS['Holyhead']
    d, i = tree.query((port[0]*111320, port[1]*111320*k)); return int(i)
hops = collections.defaultdict(set)
for op, line, sq in D['pats']:
    for x, y in zip(sq, sq[1:]):
        if x != y: hops[x].add(y)
paths = {}; done = 0
for src, tgts in hops.items():
    si = snap(src, next(iter(tgts)))
    if si is None: continue
    tj = {t: snap(t, src) for t in tgts}
    far = max(math.hypot((NLAT[si]-NLAT[tj[t]])*111320, (NLON[si]-NLON[tj[t]])*111320*k) for t in tgts if tj[t] is not None) if any(v is not None for v in tj.values()) else 0
    dist, pred = dijkstra(G, indices=si, return_predecessors=True, limit=far*1.6 + 8000)
    for t, ti in tj.items():
        if ti is None or not np.isfinite(dist[ti]): continue
        p = [ti]
        while p[-1] != si and len(p) < 200000: p.append(pred[p[-1]])
        paths[(src, t)] = p[::-1]
    done += 1
    if done % 200 == 0: print(done, 'stops routed', flush=True)
print(len(paths), 'of', sum(len(v) for v in hops.values()), 'hops routed', flush=True)
COL = {'National Express': '#D2232A', 'FlixBus': '#73D700', 'Scottish Citylink': '#F7B500', 'Megabus': '#0057B8'}
res = {}
for op in sorted({p[0] for p in D['pats']}):
    E = set(); stubs = []
    for o, line, sq in D['pats']:
        if o != op: continue
        for x, y in zip(sq, sq[1:]):
            p = paths.get((x, y))
            if not p: continue
            for u, v in zip(p, p[1:]): E.add((u, v) if u < v else (v, u))
            for sid, n in ((x, p[0]), (y, p[-1])):  # coach station to the main road: a short straight link (not for stops abroad)
                if math.hypot((S[sid][0]-NLAT[n])*111320, (S[sid][1]-NLON[n])*111320*k) > 2000: continue
                stubs.append([[S[sid][0], S[sid][1]], [round(NLAT[n], 5), round(NLON[n], 5)]])
    adj = collections.defaultdict(set)
    for u, v in E: adj[u].add(v); adj[v].add(u)
    used = set(); lines = []
    def walk(u, v):
        ln = [u, v]; used.add((u, v) if u < v else (v, u))
        while len(adj[v]) == 2:
            nx = [x for x in adj[v] if x != ln[-2]]
            if not nx: break
            e = (v, nx[0]) if v < nx[0] else (nx[0], v)
            if e in used: break
            used.add(e); ln.append(nx[0]); v = nx[0]
        return ln
    for u in list(adj):
        if len(adj[u]) != 2:
            for v in adj[u]:
                if ((u, v) if u < v else (v, u)) not in used: lines.append(walk(u, v))
    for u in list(adj):
        for v in adj[u]:
            if ((u, v) if u < v else (v, u)) not in used: lines.append(walk(u, v))
    def dp(P, eps):
        if len(P) < 3: return P
        ax, ay, bx, by = P[0][1]*k*111320, P[0][0]*111320, P[-1][1]*k*111320, P[-1][0]*111320; L = math.hypot(bx-ax, by-ay) or 1e-9; best, bi = 0, 0
        for i in range(1, len(P)-1):
            x, y = P[i][1]*k*111320, P[i][0]*111320; d = abs((bx-ax)*(ay-y) - (ax-x)*(by-ay))/L
            if d > best: best, bi = d, i
        return [P[0], P[-1]] if best <= eps else dp(P[:bi+1], eps)[:-1] + dp(P[bi:], eps)
    pl = [dp([[round(NLAT[n], 5), round(NLON[n], 5)] for n in ln], 6) for ln in lines]
    pl += [s for s in stubs if math.hypot((s[0][0]-s[1][0])*111320, (s[0][1]-s[1][1])*111320*k) > 15]
    res[op] = {'col': COL.get(op, '#555555'), 'lines': pl}
    print(op, len(pl), 'lines', sum(len(p) for p in pl), 'points', flush=True)
json.dump({'ops': res, 'stops': [[v[0], v[1], v[2]] for v in S.values()]}, open(out, 'w'), separators=(',', ':'))
json.dump([[a, b] for a, v in hops.items() for b in v if (a, b) not in paths], open(out + '.failed.json', 'w'))
