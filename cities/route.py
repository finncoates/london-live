# Road router for bus routes that come without a shape: A* over the OSM drivable road network between consecutive stops.
import math, heapq, array, osmium
import numpy as np
from scipy.spatial import cKDTree

BUS_HW = {'motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary', 'primary_link', 'secondary', 'secondary_link',
          'tertiary', 'tertiary_link', 'unclassified', 'residential', 'living_street', 'busway', 'bus_guideway', 'road', 'service'}

RAIL = {'tram', 'light_rail'}
class H(osmium.SimpleHandler):
    def __init__(self, box, kind='road'):
        super().__init__(); self.box = box; self.ways = []; self.kind = kind
    def way(self, w):
        if self.kind == 'tram':
            if w.tags.get('railway') not in RAIL or w.tags.get('service') in ('yard', 'siding'): return
            return self.keep(w)
        hw = w.tags.get('highway')
        if hw not in BUS_HW: return
        if hw == 'service' and w.tags.get('bus') not in ('yes', 'designated') and w.tags.get('psv') not in ('yes', 'designated') and w.tags.get('service') not in (None, 'bus'): return
        if w.tags.get('access') in ('private', 'no') and w.tags.get('bus') not in ('yes', 'designated') and w.tags.get('psv') not in ('yes', 'designated'): return
        self.keep(w)
    def keep(self, w):
        s, wq, n, e = self.box; pts = []
        try:
            for nd in w.nodes: pts.append((nd.ref, nd.location.lat, nd.location.lon))
        except osmium.InvalidLocationError: return
        if not any(s <= a <= n and wq <= b <= e for _, a, b in pts): return
        self.ways.append(pts)

class Router:
    def __init__(self, pbf, box, kind='road', snap_m=60):
        self.snap_m = snap_m; h = H(box, kind); h.apply_file(pbf, locations=True, idx='flex_mem')
        idx = {}; lat = array.array('d'); lon = array.array('d'); adj = []
        def nid(ref, a, b):
            i = idx.get(ref)
            if i is None: i = idx[ref] = len(lat); lat.append(a); lon.append(b); adj.append([])
            return i
        self.k = math.cos(math.radians((box[0] + box[2]) / 2))
        for pts in h.ways:
            prev = None
            for ref, a, b in pts:
                i = nid(ref, a, b)
                if prev is not None and prev != i:
                    d = math.hypot((a - lat[prev]) * 111320, (b - lon[prev]) * 111320 * self.k); n = max(1, int(d // 40))
                    last = prev; la0, lo0 = lat[prev], lon[prev]
                    for k in range(1, n + 1):  # long straight edges get extra points every ~40 m, so stops snap onto them
                        if k < n: lat.append(la0 + (a - la0) * k / n); lon.append(lo0 + (b - lo0) * k / n); adj.append([]); cur = len(lat) - 1
                        else: cur = i
                        adj[last].append((cur, d / n)); adj[cur].append((last, d / n)); last = cur
                prev = i
        self.lat, self.lon, self.adj = lat, lon, adj
        self.tree = cKDTree(np.c_[np.frombuffer(lat) * 111320, np.frombuffer(lon) * 111320 * self.k]) if len(lat) else None
        print('road graph', len(lat), 'nodes', len(h.ways), 'ways', flush=True)
    def snap(self, q):
        d, i = self.tree.query((q[0] * 111320, q[1] * 111320 * self.k))
        return (int(i) if d < self.snap_m else None)
    def near(self, q, r):
        return self.tree.query_ball_point((q[0] * 111320, q[1] * 111320 * self.k), r)
    def path(self, a, b):
        """Road (or track) path between two stops, or None (caller draws a straight line or leaves a gap).
        Starts from every node near stop a and ends at any node near stop b: the other carriageway / the other track counts."""
        if self.tree is None: return None
        S = self.near(a, self.snap_m); T = set(self.near(b, self.snap_m))
        if not S or not T: return None
        lat, lon, adj, k = self.lat, self.lon, self.adj, self.k
        bx, by = b[0] * 111320, b[1] * 111320 * k
        hx = lambda n: max(0.0, math.hypot(lat[n] * 111320 - bx, lon[n] * 111320 * k - by) - self.snap_m)
        sd = lambda n, q: math.hypot((lat[n] - q[0]) * 111320, (lon[n] - q[1]) * 111320 * k)
        straight = math.hypot((a[0] - b[0]) * 111320, (a[1] - b[1]) * 111320 * k); cap = straight * 2.5 + 400
        g = {}; came = {}; pq = []
        for n in S:
            c = sd(n, a); g[n] = c; heapq.heappush(pq, (c + hx(n), c, n))
        steps = 0; end = None
        while pq:
            f, gc, n = heapq.heappop(pq)
            if gc > g.get(n, 1e18): continue
            if f > cap: return None
            if n in T:
                end = n; break
            steps += 1
            if steps > 30000: return None
            for m, d in adj[n]:
                ng = gc + d
                if ng < g.get(m, 1e18): g[m] = ng; came[m] = n; heapq.heappush(pq, (ng + hx(m), ng, m))
        if end is None: return None
        out = [end]
        while out[-1] in came: out.append(came[out[-1]])
        out.reverse()
        return [a] + [(lat[n], lon[n]) for n in out] + [b]
