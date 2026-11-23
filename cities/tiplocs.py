"""Build rail/tiplocs.json: every National Rail station's TIPLOC (the code Darwin uses) -> where it is and its CRS code.

Source: NaPTAN rail access nodes (Open Government Licence): their ATCO code is "9100" + TIPLOC.
  https://naptan.api.dft.gov.uk/v1/access-nodes?atcoAreaCodes=910&dataFormat=csv
The CRS (three-letter) code comes from the app's own station list (rail/stations.json), matched by position.

Output: {"TIPLOC": [lat, lon, "CRS" or null]}

Usage: python3 -I cities/tiplocs.py naptan-rail.csv rail/stations.json rail/tiplocs.json
"""
import csv, json, math, sys


def dist(a, b):
    k = math.cos(math.radians(a[0]))
    return math.hypot((a[0] - b[0]) * 111320, (a[1] - b[1]) * 111320 * k)


def main(src, stations, dst):
    st = json.load(open(stations, encoding='utf-8'))  # [[crs, name, lat, lon], ...]
    grid = {}
    for crs, name, la, lo in st:
        grid.setdefault((round(la * 50), round(lo * 30)), []).append((crs, la, lo))
    out, matched = {}, 0
    with open(src, newline='', encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            atco = r.get('ATCOCode', '')
            if not atco.startswith('9100') or r.get('Status', 'active') not in ('active', ''):
                continue
            try:
                la, lo = float(r['Latitude']), float(r['Longitude'])
            except (KeyError, ValueError):
                continue
            tpl = atco[4:]
            best, bd = None, 400
            gk = (round(la * 50), round(lo * 30))
            for i in (-1, 0, 1):
                for j in (-1, 0, 1):
                    for crs, a, b in grid.get((gk[0] + i, gk[1] + j), []):
                        d = dist((la, lo), (a, b))
                        if d < bd:
                            bd, best = d, crs
            matched += best is not None
            out[tpl] = [round(la, 5), round(lo, 5), best]
    with open(dst, 'w', encoding='utf-8') as f:
        json.dump(out, f, separators=(',', ':'), sort_keys=True)
    print(len(out), 'tiplocs,', matched, 'with a CRS code')


if __name__ == '__main__':
    main(*sys.argv[1:4])
