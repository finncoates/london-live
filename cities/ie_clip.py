# Ireland's railway (from its national timetable, rail_gtfs.py) without Northern Ireland's part: Northern Ireland is in
# the UK's own National Rail map already. Uses the map's NI outline (NI_POLY in index.html).
#   python -I cities/ie_clip.py      (then rail_tiles.py)
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace')
import os, json, re
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, '..', 'index.html'), encoding='utf-8').read()
m = re.search(r'const NI_POLY = (\[\[.*?\]\]);', src, re.S); NI = json.loads(m.group(1))
def inp(P, p):
    c = False; j = len(P) - 1
    for i in range(len(P)):
        (y1, x1), (y2, x2) = P[i], P[j]
        if (y1 > p[0]) != (y2 > p[0]) and p[1] < (x2 - x1)*(p[0] - y1)/(y2 - y1) + x1: c = not c
        j = i
    return c
ni = lambda p: inp(NI, p) or (p[1] > -6.0 and p[0] > 54.7)
f = os.path.join(HERE, '.build', 'rail', 'ie.json'); out = []
for l in json.load(open(f)):
    run = []
    for q in l:
        if ni(q):
            if len(run) > 1: out.append(run)
            run = []
        else: run.append(q)
    if len(run) > 1: out.append(run)
json.dump(out, open(f, 'w'), separators=(',', ':'))
sf = os.path.join(HERE, 'ie-stations.json'); st = [s for s in json.load(open(sf, encoding='utf-8')) if not ni((s[2], s[3]))]
json.dump(st, open(sf, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print(len(out), 'railway pieces,', len(st), 'stations outside Northern Ireland')
