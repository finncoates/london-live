# Build some French networks again (from the catalogue, as fr_all.py does), with extra options — e.g. bus routes matched
# onto the roads where their published shapes turned out to be partly straight stop-to-stop lines (Rouen, Rémi…).
#   python -I cities/fr_redo.py "--roads on" n-network-id [n-network-id ...]
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace'); _s.stderr.reconfigure(encoding='utf-8', errors='replace')
import os, sys, json, subprocess, re
HERE = os.path.dirname(os.path.abspath(__file__)); B = os.path.join(HERE, '.build')
extra, ids = sys.argv[1].split(), sys.argv[2:]
log = {}
for line in open(os.path.join(B, 'fr_all.log'), encoding='utf-8'):
    try: j = json.loads(line); log[j['id']] = j
    except Exception: pass
cat = {x['slug']: x for x in json.load(open(os.path.join(B, 'fr_catalogue.json'), encoding='utf-8'))}
idx = {c['id']: c for c in json.load(open(os.path.join(HERE, 'fr-index.json'), encoding='utf-8'))}
for i in ids:
    j = log.get(i)
    if not j: print(i, 'not in the log'); continue
    x = cat[j['slug']]; g = [r for r in x['resources'] if r.get('format') == 'GTFS' and r.get('is_available')]
    url = max(g, key=lambda r: r.get('updated') or '')['url']
    city = i in idx; name = idx[i]['name'] if city else i
    args = [sys.executable, '-I', os.path.join(HERE, 'fr_build.py'), i, name, url] + ([] if city else ['--nolines']) + extra
    p = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace')
    rep = next((l for l in reversed(p.stdout.splitlines()) if l.startswith('{')), None)
    print(i, 'ok' if p.returncode == 0 else 'FAILED', (rep or p.stderr[-300:])[:300], flush=True)
    for fn in ('feed.zip', 'city.zip', 'edges.pkl'):
        try: os.remove(os.path.join(B, i, fn))
        except OSError: pass
