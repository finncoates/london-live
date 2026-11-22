import osmium, json
class H(osmium.SimpleHandler):
    def __init__(s): super().__init__(); s.ways = []
    def way(s, w):
        if w.tags.get('waterway') == 'river' and 'Thames' in (w.tags.get('name') or ''):
            try: s.ways.append({'r': 'river', 'id': [n.ref for n in w.nodes], 'p': [[round(n.lat, 6), round(n.lon, 6)] for n in w.nodes]})
            except osmium.InvalidLocationError: pass
h = H(); h.apply_file('london.osm.pbf', locations=True)
rails = json.load(open('rails.json')); rails = [w for w in rails if w['r'] != 'river'] + h.ways
json.dump(rails, open('rails.json', 'w')); print(len(h.ways), sum(len(w['p']) for w in h.ways))
