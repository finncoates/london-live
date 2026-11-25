# Weekly refresh: every city whose timetable has changed at its source is rebuilt the way it was built
# (cities/.build/manifest.json, written by fr_build.py), its lines put back on the track and thinned, checked, and
# published (git push runs the smoke test first). A city with no build record, or built from a file made by hand
# (split, merged or fixed), is listed for a person to rebuild with its country's job.
#   python -I cities/refresh.py            check the sources, rebuild what changed, publish
#   python -I cities/refresh.py --check    only report what changed
#   python -I cities/refresh.py --backfill  add the build records that can be read back from the job scripts (Poland)
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace')
import os, sys, json, re, subprocess, urllib.request, time, glob
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); B = os.path.join(HERE, '.build')
MF = os.path.join(B, 'manifest.json')
UA = {'user-agent':'LondonLive/1.0 (+https://github.com/finncoates/london-live)'}
def load(): return json.load(open(MF, encoding='utf-8')) if os.path.exists(MF) else {}
def save(m):
    with open(MF + '.tmp', 'w', encoding='utf-8') as f: json.dump(m, f, ensure_ascii=False, indent=1)
    os.replace(MF + '.tmp', MF)
def remote(url):  # what the source says about its file now: its tag, date and size (no download)
    for method in ('HEAD', 'GET'):
        try:
            req = urllib.request.Request(url, method=method, headers={**UA, **({'range':'bytes=0-0'} if method == 'GET' else {})})
            with urllib.request.urlopen(req, timeout=60) as r:
                h = r.headers; tag = h.get('etag') or h.get('last-modified')
                size = (h.get('content-range') or '').split('/')[-1] if method == 'GET' else h.get('content-length')
                if tag or size: return f'{tag}|{size}'
        except Exception: pass
    return None
def backfill():  # Poland: its job script lists every city: id | name | source | extra options
    m = load(); sh = open(os.path.join(B, 'pl.sh'), encoding='utf-8').read()
    var = dict(re.findall(r'(\w+)=(https?://\S+?)(?:;|\s)', sh)); n = 0
    for row in re.findall(r'^([a-z0-9-]+)\|([^|]+)\|([^|]+)\|(.*)$', sh, re.M):
        cid, name, src, extra = row; src = re.sub(r'\$(\w+)', lambda x: var.get(x.group(1), x.group(0)), src)
        if not src.startswith('http'): continue
        args = [cid, name, src, '--work', os.path.join(B, 'pl-' + cid).replace('\\', '/'), '--country', 'pl', '--roads', 'on'] + (extra.split() if extra.strip() else [])
        m.setdefault('pl-' + cid, {'args':args, 'url':src, 'built':'2026-11-24T22:00:00Z'}); n += 1
    save(m); print('backfilled', n, 'Polish cities')
def run(cmd, **kw): print('  $', ' '.join(cmd)[:160], flush=True); return subprocess.run(cmd, cwd=ROOT, **kw)
def main():
    if '--backfill' in sys.argv: return backfill()
    m = load(); check = '--check' in sys.argv; changed, unknown, failed, done = [], [], [], []
    have = {os.path.basename(f)[:-5] for f in glob.glob(os.path.join(HERE, '*.json'))}
    for key, e in sorted(m.items()):
        if not e.get('url'): unknown.append(key); continue
        now = remote(e['url'])
        if now is None: failed.append(key + ' (source not answering)'); continue
        if e.get('remote') is None: e['remote'] = now; continue  # first look: remembered, not rebuilt
        if now != e['remote']: changed.append(key)
    print(f'{len(m)} build records · {len(changed)} changed · {len(failed)} not answering · {len(unknown)} built from local files')
    if check or not changed: save(m); report(changed, failed, unknown, m, have); return
    for key in changed:
        e = m[key]; args = list(e['args']); work = args[args.index('--work') + 1] if '--work' in args else os.path.join(B, args[0])
        try: os.remove(os.path.join(work, 'feed.zip'))  # (the builder reuses a downloaded feed: a refresh fetches it again)
        except OSError: pass
        r = run([sys.executable, '-I', os.path.join(HERE, 'fr_build.py')] + args, timeout=5400)
        if r.returncode: failed.append(key + ' (build failed)'); continue
        city = os.path.join(HERE, key + '.json')
        if os.path.exists(city) and '--nolines' not in args:  # its trams and metros back on the track, then thinned
            plan = subprocess.run([sys.executable, '-I', os.path.join(HERE, 'snap_plan.py'), city], cwd=ROOT, capture_output=True, text=True).stdout.split()
            if plan:
                pbf = os.path.join(B, 'refresh-' + os.path.basename(plan[0]))
                try:
                    urllib.request.urlretrieve(plan[0], pbf); run([sys.executable, '-I', os.path.join(HERE, 'line_snap.py'), pbf, city])
                finally:
                    try: os.remove(pbf)
                    except OSError: pass
            run([sys.executable, '-I', os.path.join(HERE, 'simplify_lines.py'), city])
        e['remote'] = remote(e['url']); e['refreshed'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()); done.append(key)
    save(m)
    if done:
        run([sys.executable, '-I', os.path.join(HERE, 'fr_stops.py')])
        bad = [f for f in glob.glob(os.path.join(HERE, '*.json')) if not ok_json(f)]
        if bad: print('NOT publishing: files that do not parse:', bad); return
        run(['git', 'add', '-A', 'cities'])
        r = run(['git', 'commit', '-q', '-m', 'Weekly refresh: ' + ', '.join(done) + ' rebuilt from their new timetables\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>'])
        if r.returncode == 0: run(['git', 'push', '-q', 'origin', 'main'])  # (the smoke test runs first, and stops a broken page)
    report(done, failed, unknown, m, have)
def ok_json(f):
    try: json.load(open(f, encoding='utf-8')); return True
    except Exception: return False
def report(changed, failed, unknown, m, have):
    norec = sorted(h for h in have if h not in m and not h.endswith(('-index', '-stations', 'feed-names')) and '-' in h)
    txt = [time.strftime('%Y-%m-%d %H:%M'), f'rebuilt or changed: {", ".join(changed) or "none"}', f'problems: {", ".join(failed) or "none"}',
           f'built from local files (rebuild with their country job): {len(unknown)}', f'no build record yet ({len(norec)}): ' + ', '.join(norec[:40]) + (' …' if len(norec) > 40 else '')]
    open(os.path.join(B, 'refresh-report.txt'), 'w', encoding='utf-8').write('\n'.join(txt) + '\n'); print('\n'.join(txt))
main()
