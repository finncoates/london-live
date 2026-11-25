# Ways from an OpenStreetMap file with their points' locations, in two passes and without a node index: first the ways
# (and nodes) wanted, then only those ways' points (filtered in C++). A whole country fits in a few hundred MB, where
# an on-disk index of every point in it (4 GB for Britain, on a USB disk) took hours of random reads.
#   from osm2pass import read
#   ways, nodes = read(pbf, keep_way, keep_node)
#     keep_way(tags) -> anything (kept with the way) or None;  keep_node(tags) -> anything or None
#     ways: [(info, [(lat, lon, node id), ...]), ...]   nodes: [(info, lat, lon, node id), ...]
import osmium
from osmium.filter import KeyFilter, IdFilter
def read(pbf, keep_way, keep_node=None, keys=('railway', 'public_transport')):
    raw, nodes = [], []
    for o in osmium.FileProcessor(pbf, osmium.osm.NODE | osmium.osm.WAY).with_filter(KeyFilter(*keys)):
        if o.is_way():
            info = keep_way(o.tags)
            if info is not None: raw.append((info, [n.ref for n in o.nodes]))
        elif keep_node is not None and o.location.valid():
            info = keep_node(o.tags)
            if info is not None: nodes.append((info, o.location.lat, o.location.lon, o.id))
    need = {r for _, refs in raw for r in refs}; loc = {}
    if need:
        for n in osmium.FileProcessor(pbf, osmium.osm.NODE).with_filter(IdFilter(need)):
            if n.location.valid(): loc[n.id] = (n.location.lat, n.location.lon)
    ways = []
    for info, refs in raw:
        if all(r in loc for r in refs): ways.append((info, [(loc[r][0], loc[r][1], r) for r in refs]))
    return ways, nodes
