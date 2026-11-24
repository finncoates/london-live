# Line colours from OpenStreetMap for city lines whose timetable gives none (they were drawn in the default tram green /
# metro orange): each route=tram / light_rail / subway / funicular relation with a ref and a colour, placed by one of its
# ways, inside the city's box. Zürich's VBZ, Basel's BVB, Bern's, Geneva's trams…
#   python -I cities/osm_line_colours.py country.osm.pbf cities/ch-zurich.json [more city files…]
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace')
import sys, os, json, re, collections, osmium
pbf, files = sys.argv[1], sys.argv[2:]
DEFAULT = {'#00985f', '#ff6319'}
KINDS = {'tram': 'tram', 'light_rail': 'tram', 'subway': 'metro', 'funicular': 'metro'}
class Rels(osmium.SimpleHandler):
    def __init__(h): super().__init__(); h.rels = []; h.want = set()
    def relation(h, r):
        t = r.tags
        if t.get('type') == 'route' and t.get('route') in KINDS and t.get('ref') and t.get('colour'):
            w = next((m.ref for m in r.members if m.type == 'w'), None)
            if w is not None: h.rels.append((t['ref'].strip(), t['colour'].strip(), KINDS[t['route']], w)); h.want.add(w)
class Ways(osmium.SimpleHandler):
    def __init__(h, want): super().__init__(); h.want = want; h.at = {}
    def way(h, w):
        if w.id in h.want:
            try: n = w.nodes[len(w.nodes)//2]; h.at[w.id] = (n.location.lat, n.location.lon)
            except Exception: pass
r = Rels(); r.apply_file(pbf); w = Ways(r.want); w.apply_file(pbf, locations=True)
print(len(r.rels), 'coloured route relations', flush=True)
def hexcol(c):
    c = c.lower()
    if re.fullmatch(r'#[0-9a-f]{6}', c): return c.upper()
    if re.fullmatch(r'#[0-9a-f]{3}', c): return ('#' + ''.join(x*2 for x in c[1:])).upper()
    return {'red':'#E3000B', 'blue':'#0060AA', 'green':'#009F4D', 'yellow':'#FFD200', 'orange':'#F39200', 'purple':'#7B2482', 'brown':'#8B5A2B', 'black':'#222222', 'pink':'#E5007E', 'grey':'#8A8A8A', 'gray':'#8A8A8A'}.get(c)
idx = {c['url'][7:]: c['box'] for c in json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fr-index.json'), encoding='utf-8')) for _ in [0]}
for f in files:
    d = json.load(open(f, encoding='utf-8')); box = idx.get(os.path.basename(f))
    if not box: print(f, 'no box in the index'); continue
    votes = collections.defaultdict(collections.Counter)
    for ref, col, kind, wid in r.rels:
        p = w.at.get(wid); c = hexcol(col)
        if p and c and box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3]: votes[(ref, kind)][c] += 1
    n = 0
    for l in d['lines']:
        v = votes.get((l['name'], l['kind']))
        if v and l['col'].lower() in DEFAULT: l['col'] = v.most_common(1)[0][0]; n += 1
    cols = {l['name']: l['col'] for l in d['lines']}
    for st in d.get('stations', []):
        for x in st[4]:
            if x[0] in cols and x[1].lower() in DEFAULT: x[1] = cols[x[0]]
    for _k in range(20):  # written whole then swapped in, retried: Windows refuses a file another process has open
        try:
            with open(f + '.tmp', 'w', encoding='utf-8') as o_: json.dump(d, o_, separators=(',', ':'), ensure_ascii=False)
            os.replace(f + '.tmp', f); break
        except OSError: __import__('time').sleep(0.5)
    print(os.path.basename(f), n, 'of', len(d['lines']), 'lines coloured from OpenStreetMap', sorted({(l['name'], l['col']) for l in d['lines']})[:30], flush=True)
