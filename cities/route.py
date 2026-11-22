# Road router for bus routes that come without a shape: A* over the OSM drivable road network between consecutive stops.
import math, heapq, array, osmium
import numpy as np
from scipy.spatial import cKDTree

BUS_HW = {'motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary', 'primary_link', 'secondary', 'secondary_link',
          'tertiary', 'tertiary_link', 'unclassified', 'residential', 'living_street', 'busway', 'bus_guideway', 'road', 'service'}

class H(osmium.SimpleHandler):
    def __init__(self, box):
        super().__init__(); self.box = box; self.ways = []
    def way(self, w):
        hw = w.tags.get('highway')
        if hw not in BUS_HW: return
        if hw == 'service' and w.tags.get('bus') not in ('yes', 'designated') and w.tags.get('psv') not in ('yes', 'designated') and w.tags.get('service') not in (None, 'bus'): return
        if w.tags.get('access') in ('private', 'no') and w.tags.get('bus') not in ('yes', 'designated') and w.tags.get('psv') not in ('yes', 'designated'): return
        s, wq, n, e = self.box; pts = []
        try:
            for nd in w.nodes: pts.append((nd.ref, nd.location.lat, nd.location.lon))
        except osmium.InvalidLocationError: return
        if not any(s <= a <= n and wq <= b <= e for _, a, b in pts): return
        self.ways.append(pts)

class Router:
    def __init__(self, pbf, box):
        h = H(box); h.apply_file(pbf, locations=True, idx='flex_mem')
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
                    d = math.hypot((a - lat[prev]) * 111320, (b - lon[prev]) * 111320 * self.k); adj[prev].append((i, d)); adj[i].append((prev, d))
                prev = i
        self.lat, self.lon, self.adj = lat, lon, adj
        self.tree = cKDTree(np.c_[np.frombuffer(lat) * 111320, np.frombuffer(lon) * 111320 * self.k]) if len(lat) else None
        print('road graph', len(lat), 'nodes', len(h.ways), 'ways', flush=True)
    def snap(self, q):
        d, i = self.tree.query((q[0] * 111320, q[1] * 111320 * self.k))
        return (int(i) if d < 60 else None)
    def path(self, a, b):
        """Road path between two stops, or None (caller draws a straight line)."""
        if self.tree is None: return None
        i, j = self.snap(a), self.snap(b)
        if i is None or j is None: return None
        if i == j: return [a, b]
        lat, lon, adj, k = self.lat, self.lon, self.adj, self.k
        straight = math.hypot((lat[i] - lat[j]) * 111320, (lon[i] - lon[j]) * 111320 * k); cap = straight * 2.5 + 400
        hx = lambda n: math.hypot((lat[n] - lat[j]) * 111320, (lon[n] - lon[j]) * 111320 * k)
        g = {i: 0.0}; came = {}; pq = [(hx(i), 0.0, i)]; steps = 0
        while pq:
            f, gc, n = heapq.heappop(pq)
            if n == j: break
            if gc > g.get(n, 1e18) or f > cap: continue
            steps += 1
            if steps > 20000: return None
            for m, d in adj[n]:
                ng = gc + d
                if ng < g.get(m, 1e18): g[m] = ng; came[m] = n; heapq.heappush(pq, (ng + hx(m), ng, m))
        else: return None
        if j not in g: return None
        out = [j]
        while out[-1] != i: out.append(came[out[-1]])
        out.reverse()
        return [a] + [(lat[n], lon[n]) for n in out] + [b]
