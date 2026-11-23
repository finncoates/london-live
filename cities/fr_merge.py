# Rebuild the shared bus tiles (cities/busnet) that French cities touch: each = the tile as it was before any French city
# (git, BASE in fr_build.py) + every French city's own routes there (cities/.build/<city>/busnet). fr_build.py does this
# for the city it builds; this script redoes it for the given cities (or all) without rebuilding them.
#   python -I cities/fr_merge.py [city ...]
import os, sys, json, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); BASE = '6c9aa8ce'; root = os.path.join(HERE, '.build')
cities = sys.argv[1:] or [c for c in os.listdir(root) if os.path.isdir(os.path.join(root, c, 'busnet'))]
tiles = {fn for c in cities if os.path.isdir(os.path.join(root, c, 'busnet')) for fn in os.listdir(os.path.join(root, c, 'busnet'))}
for fn in sorted(tiles):
    base = subprocess.run(['git', '-C', HERE, 'show', f'{BASE}:cities/busnet/{fn}'], capture_output=True, text=True)
    merged = json.loads(base.stdout) if base.returncode == 0 else []; have = {json.dumps(p) for p in merged}
    for c in sorted(os.listdir(root)):
        f2 = os.path.join(root, c, 'busnet', fn)
        if os.path.exists(f2):
            for p in json.load(open(f2)):
                k = json.dumps(p)
                if k not in have: have.add(k); merged.append(p)
    json.dump(merged, open(os.path.join(HERE, 'busnet', fn), 'w'), separators=(',', ':'))
print(len(tiles), 'tiles rebuilt for', ', '.join(cities))
