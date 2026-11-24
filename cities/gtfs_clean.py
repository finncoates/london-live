# Rewrite a GTFS whose CSV puts a space after every comma (Latvia's ATD: 'route_id, agency_id, …') as plain CSV, so
# the other tools find their columns. Every .txt in the zip is read with skipinitialspace and written back cleanly.
#   python -I cities/gtfs_clean.py in.zip out.zip
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace')
import sys, zipfile, csv, io
src, dst = sys.argv[1:3]
zi = zipfile.ZipFile(src)
with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as zo:
    for info in zi.infolist():
        name = info.filename.split('/')[-1]
        if not name.endswith('.txt'): continue
        with zi.open(info) as f, zo.open(name, 'w') as g:
            r = csv.reader(io.TextIOWrapper(f, 'utf-8-sig', newline=''), skipinitialspace=True)
            out = io.TextIOWrapper(g, 'utf-8', newline=''); w = csv.writer(out)
            for row in r: w.writerow([c.strip() for c in row])
            out.flush(); out.detach()
print('cleaned', dst)
