# Bus stops abroad (France, the Netherlands…) for the map's bus stop layer: every network's stops
# (cities/.build/<network>/stops.json: [name, lat, lon], written by fr_build.py) into the same 0.05° tiles as Britain's
# (cities/stops/<lat*20>_<lon*20>.json), merged with whatever a tile held before (git, BASE). A stop that two networks
# both list (same name, within ~15 m) is kept once. Departures come from Transitous when a stop is tapped (by place).
#   python -I cities/fr_stops.py
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace'); _s.stderr.reconfigure(encoding='utf-8', errors='replace')  # Windows console: never crash on a name
import os, json, math, subprocess, collections

def save(path, obj, **kw):  # written whole then swapped in, retried: Windows refuses a file another process (the web server, a scan) has open
    import time
    for k in range(20):
        try:
            with open(path + '.tmp', 'w', encoding='utf-8') as f: json.dump(obj, f, separators=(',', ':'), **kw)
            os.replace(path + '.tmp', path); return
        except OSError:
            if k == 19: raise
            time.sleep(0.5)
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
T = collections.defaultdict(dict); n = 0
for c in sorted(os.listdir(root)):
    f = os.path.join(root, c, 'stops.json')
    if not os.path.exists(f): continue
    for name, la, lo in json.load(open(f, encoding='utf-8')):
        t = f'{math.floor(la*20)}_{math.floor(lo*20)}'; k = (name.lower(), round(la*7000), round(lo*5000))  # ~15 m
        if k not in T[t]: T[t][k] = [f'x:{la:.5f},{lo:.5f}', name, la, lo, []]; n += 1
INBASE = set(subprocess.run(['git', '-C', HERE, 'ls-tree', '--name-only', f'{BASE}:cities/stops/'], capture_output=True, text=True).stdout.split())
for t, d in T.items():
    fn = t + '.json'; out = {'stops':[]}
    if fn in INBASE:
        b = subprocess.run(['git', '-C', HERE, 'show', f'{BASE}:cities/stops/{fn}'], capture_output=True, text=True)
        if b.returncode == 0: out = json.loads(b.stdout)
    out['stops'] = out.get('stops', []) + list(d.values())
    save(os.path.join(HERE, 'stops', fn), out, ensure_ascii=False)
print(n, 'stops in', len(T), 'tiles')
