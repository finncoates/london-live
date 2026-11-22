import osmium, json, sys
KEEP = {'rail', 'subway', 'light_rail', 'tram'}
class H(osmium.SimpleHandler):
    def __init__(s): super().__init__(); s.ways = []
    def way(s, w):
        r = w.tags.get('railway')
        if r not in KEEP: return
        if w.tags.get('service') in ('yard', 'siding', 'spur', 'crossover'): return
        try: pts = [[round(n.lat, 6), round(n.lon, 6)] for n in w.nodes]
        except osmium.InvalidLocationError: return
        s.ways.append({'r': r, 'id': [n.ref for n in w.nodes], 'p': pts})
h = H(); h.apply_file('london.osm.pbf', locations=True)
json.dump(h.ways, open('rails.json', 'w'))
print(len(h.ways), sum(len(w['p']) for w in h.ways))
