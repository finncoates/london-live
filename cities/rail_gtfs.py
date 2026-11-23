# A country's railway for the National Rail map from its national GTFS timetable (route shapes of its trains), for
# countries without an open track dataset like SNCF's: the Netherlands (OVapi), …
#   python -I cities/rail_gtfs.py <cc> feed.zip "<south,west,north,east>" ["route types", default 2 and 100-117]
# -> cities/.build/rail/<cc>.json (lines, each stretch of track once) and cities/<cc>-stations.json ([id, name, lat, lon])
# then rail_tiles.py rebuilds the shared tiles.
import os, sys, json, subprocess, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
cc, feed, box = sys.argv[1:4]; types = sys.argv[4] if len(sys.argv) > 4 else ','.join(['2'] + [str(t) for t in range(100, 118)])
tmap = ','.join(f'{t}:train' for t in types.split(','))
tmp = os.path.join(tempfile.gettempdir(), f'rail-{cc}.json'); env = dict(os.environ, GLOBAL_DEDUP='1', EPS='8', PYTHONIOENCODING='utf-8')
subprocess.run([sys.executable, '-I', os.path.join(HERE, 'gtfs_lines.py'), feed, tmp, tmap, '', box], check=True, env=env)
subprocess.run([sys.executable, '-I', os.path.join(HERE, 'gtfs_stations.py'), feed, tmp, tmap, box], check=True, env=env)
d = json.load(open(tmp, encoding='utf-8'))
os.makedirs(os.path.join(HERE, '.build', 'rail'), exist_ok=True)
json.dump([l['pts'] for l in d['lines']], open(os.path.join(HERE, '.build', 'rail', cc + '.json'), 'w'), separators=(',', ':'))
json.dump(sorted([[s[0], s[1], s[2], s[3]] for s in d['stations']], key=lambda s: s[1]), open(os.path.join(HERE, f'{cc}-stations.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print(cc, len(d['lines']), 'railway lines,', len(d['stations']), 'stations')
subprocess.run([sys.executable, '-I', os.path.join(HERE, 'rail_tiles.py')], check=True, env=env)
