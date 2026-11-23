# Rebuild the shared bus tiles (cities/busnet) that French networks touch. Each tile = the tile as it was before any French
# network (git, BASE) + every French network's own routes there (cities/.build/<network>/busnet), with each road drawn
# once: a stretch of route that runs along a road already drawn (within ~11 m, either direction) is left out, so a road
# served by the city's buses and by intercity coaches isn't drawn two or three times over.
# Networks with their own city file (trams, metros) go first, then the rest by name, so the result doesn't depend on order.
#   python -I cities/fr_merge.py [network ...]      (no names: every network)
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace'); _s.stderr.reconfigure(encoding='utf-8', errors='replace')  # Windows console: never crash on a name
import os, sys, json, math, subprocess
# one writer at a time: two builds merging into the same shared tiles at once corrupt them (Windows: 'Invalid argument')
import time as _t, atexit as _ax
_LOCK = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.build', 'merge.lock'); _t0 = _t.time()
while True:
    try: _fd = os.open(_LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY); break
    except FileExistsError:
        if _t.time() - os.path.getmtime(_LOCK) > 1800: os.remove(_LOCK)  # left by a crashed run
        _t.sleep(2)
_ax.register(lambda: (os.close(_fd), os.remove(_LOCK)))
HERE = os.path.dirname(os.path.abspath(__file__)); BASE = '6c9aa8ce'; root = os.path.join(HERE, '.build')
nets = [c for c in os.listdir(root) if os.path.isdir(os.path.join(root, c, 'busnet'))]
want = sys.argv[1:] or nets
cityfile = {c for c in nets if any(os.path.exists(os.path.join(HERE, f'{cc}-{c}.json')) for cc in ('fr', 'nl', 'be', 'de', 'ch', 'lu', 'es', 'it', 'at', 'pt'))}
order = sorted(nets, key=lambda c: (c not in cityfile, c))
tiles = {fn for c in want if os.path.isdir(os.path.join(root, c, 'busnet')) for fn in os.listdir(os.path.join(root, c, 'busnet'))}
CY, CX = 0.0001, 0.00015                      # ~11 m cells
def cells_along(p, step=5):
    for (a, b), (c, d) in zip(p, p[1:]):
        L = math.hypot((c - a)*111320, (d - b)*111320*math.cos(math.radians(a))); n = max(1, int(L/step))
        for k in range(n + 1):
            yield math.floor((a + (c - a)*k/n)/CY), math.floor((b + (d - b)*k/n)/CX)
def covered(seg, mark):
    return all(c in mark for c in cells_along(seg, 8))
# which tiles existed before any other country (listed once: asking git for each missing tile is slow)
INBASE = set(subprocess.run(['git', '-C', HERE, 'ls-tree', '--name-only', f'{BASE}:cities/busnet/'], capture_output=True, text=True).stdout.split())
for fn in sorted(tiles):
    base = subprocess.run(['git', '-C', HERE, 'show', f'{BASE}:cities/busnet/{fn}'], capture_output=True, text=True) if fn in INBASE else None
    out = json.loads(base.stdout) if base and base.returncode == 0 else []; mark = set()
    def draw(p):
        out.append(p)
        for y, x in cells_along(p):
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1): mark.add((y + dy, x + dx))
    for p in out[:]: out.pop(0); draw(p)
    for c in order:
        f2 = os.path.join(root, c, 'busnet', fn)
        if not os.path.exists(f2): continue
        for p in json.load(open(f2)):
            run = [p[0]]
            for q in p[1:]:
                if covered([run[-1], q], mark):
                    if len(run) > 1: draw(run)
                    run = [q]
                else: run.append(q)
            if len(run) > 1: draw(run)
    json.dump(out, open(os.path.join(HERE, 'busnet', fn), 'w'), separators=(',', ':'))
print(len(tiles), 'tiles rebuilt for', len(want), 'networks')
