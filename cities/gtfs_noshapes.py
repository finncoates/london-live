# A timetable without its shapes, for operators whose shapes are wrong (allGo's zig-zag between parallel streets in
# Amsterdam): the builder then routes each bus stop to stop along the roads instead of following them.
#   python -I cities/gtfs_noshapes.py in.zip out.zip
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace')
import sys, zipfile, csv, io
src, dst = sys.argv[1:3]
zi = zipfile.ZipFile(src)
with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as zo:
    for info in zi.infolist():
        name = info.filename.split('/')[-1]
        if not name.endswith('.txt') or name == 'shapes.txt': continue
        with zi.open(info) as f, zo.open(name, 'w') as g:
            if name != 'trips.txt':
                while True:
                    b = f.read(1 << 20)
                    if not b: break
                    g.write(b)
                continue
            r = csv.DictReader(io.TextIOWrapper(f, 'utf-8-sig')); out = io.TextIOWrapper(g, 'utf-8', newline='')
            w = csv.DictWriter(out, fieldnames=r.fieldnames); w.writeheader()
            for t in r: t['shape_id'] = '' if 'shape_id' in t else None; w.writerow({k: v for k, v in t.items() if k in r.fieldnames})
            out.flush(); out.detach()
print('shapes dropped ->', dst)
