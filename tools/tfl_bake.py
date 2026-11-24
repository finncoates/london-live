# London's line shapes and stops baked into the site (cities/tfl/<line>.json), in the shape loadLine() keeps them, so
# the map never needs TfL's API just to draw its lines (a first visit made 50 calls, and a rate limit left London blank).
# Re-run when TfL changes a route:   python -I tools/tfl_bake.py
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace')
import os, re, json, time, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, 'cities', 'tfl'); os.makedirs(OUT, exist_ok=True)
src = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
ids = re.findall(r"\['([a-z0-9-]+)','[^']+','#[0-9A-Fa-f]{6}','(?:tube|elizabeth|dlr|overground|tram|river|cable)'\]", src[src.index('const LINES = ['):src.index('];', src.index('const LINES = ['))])
def get(path):
    for k in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request('https://api.tfl.gov.uk' + path, headers={'user-agent': 'LondonLive/1.0'}), timeout=60) as r: return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            time.sleep(20 * (k + 1))
    raise IOError('TfL kept failing: ' + path)
def clean(n): return re.sub(r'\s+(Underground|DLR|Rail|Tram|Overground)?\s*Station$|\s+\(.*?\)$', '', n).strip()
r5 = lambda x: round(x*1e5)/1e5
for lid in ids:
    o = get(f'/Line/{lid}/Route/Sequence/outbound'); time.sleep(2); i = get(f'/Line/{lid}/Route/Sequence/inbound'); time.sleep(2)
    d = {'polys': [[[r5(la), r5(lo)] for lo, la in p] for s in o['lineStrings'] for p in json.loads(s)], 'routes': [], 'stops': {}}
    for j, dr in ((o, 'outbound'), (i, 'inbound')):
        if not j: continue
        for r in j.get('orderedLineRoutes') or []: d['routes'].append({'dir': dr, 'ids': r['naptanIds']})
        for seq in j.get('stopPointSequences') or []:
            for s in seq['stopPoint']:
                if s['id'] not in d['stops']: d['stops'][s['id']] = {'raw': s['name'], 'p': [r5(s['lat']), r5(s['lon'])]}
    json.dump(d, open(os.path.join(OUT, lid + '.json'), 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
    print(lid, len(d['polys']), 'pieces', len(d['stops']), 'stops', flush=True)
