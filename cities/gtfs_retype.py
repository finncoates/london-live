# Give some routes of a GTFS another route type (and colour), for timetables that file trams as buses — Lisbon's Carris
# lists its trams (12E, 28E…) and its funiculars and lift (51E–55E) as route_type 3, with no colours.
#   python -I cities/gtfs_retype.py in.zip out.zip 'short-name regex=type[:#colour]' ...
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace')
import sys, re, zipfile, csv, io, collections
src, dst, rules = sys.argv[1], sys.argv[2], [r.rsplit('=', 1) for r in sys.argv[3:]]
zi = zipfile.ZipFile(src); n = collections.Counter()
with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as zo:
    for info in zi.infolist():
        name = info.filename.split('/')[-1]
        if not name.endswith('.txt'): continue
        if name != 'routes.txt':
            with zi.open(info) as f, zo.open(name, 'w') as g:
                while True:
                    b = f.read(1 << 20)
                    if not b: break
                    g.write(b)
            continue
        rows = list(csv.DictReader(io.TextIOWrapper(zi.open(info), 'utf-8-sig'))); cols = list(rows[0].keys())
        if 'route_color' not in cols: cols.append('route_color')
        for r in rows:
            for rx, to in rules:
                if re.search(rx, r.get('route_short_name') or ''):
                    t, _, c = to.partition(':'); r['route_type'] = t; n[t] += 1
                    if c: r['route_color'] = c.lstrip('#')
                    break
        out = io.StringIO(); w = csv.DictWriter(out, cols, extrasaction='ignore'); w.writeheader(); w.writerows(rows)
        zo.writestr('routes.txt', out.getvalue())
print('retyped', dict(n), '->', dst)
