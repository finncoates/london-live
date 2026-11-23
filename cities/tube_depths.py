"""Build tube-depths.json from TfL's station depth table (FOI-0493-2223).

Source: https://foi.tfl.gov.uk/FOI-0493-2223/Copy%20of%20Station%20depths.csv
Levels in that file are on the London Underground Datum, which is 100 m below sea level
(Ordnance Datum Newlyn), so platform height above sea level = level - 100.

Output: {"<normalised station name>": [ground_m_above_sea_level, {"<tfl line id>": platform_m_above_sea_level}]}
The live map matches station names with the same normalisation (depthKey in index.html).

Usage: python3 -I cities/tube_depths.py depths.csv tube-depths.json
"""
import csv, json, re, sys

COLS = [  # (first column index, TfL line ids), each line has two direction columns
    (2, ['bakerloo']), (4, ['central']), (6, ['district']), (8, ['hammersmith-city']), (10, ['jubilee']),
    (12, ['metropolitan']), (14, ['northern']), (16, ['piccadilly']), (18, ['victoria']), (20, ['waterloo-city'])]
SURFACE = ['district', 'hammersmith-city', 'metropolitan']  # the Circle line runs on their platforms
ALIAS = {'heathrow airport terminal 1 2 and 3': 'heathrow terminals 2 and 3',
         'shepherds bush central': 'shepherds bush', 'shepherds bush market hammersmith and city': 'shepherds bush market'}


def key(name):
    n = name.lower().replace('&', ' and ').replace('-', ' ')
    n = re.sub(r'\b(city|charing x) branch\b', '', n)
    n = re.sub(r"[.'’,]", '', n)
    n = re.sub(r'\s+', ' ', n).strip()
    if n in ALIAS:
        return ALIAS[n]
    n = re.sub(r'\s*\(.*?\)', '', n).strip()
    return ALIAS.get(n, n)


def num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def main(src, dst):
    out = {}
    with open(src, newline='', encoding='utf-8-sig') as f:
        rows = list(csv.reader(f))
    for r in rows[2:]:
        if not r or not r[0].strip() or r[0].strip() == 'Notes':
            if r and r[0].strip() == 'Notes':
                break
            continue
        ground = num(r[1])
        if ground is None:
            continue
        k = key(r[0])
        g, lines = out.setdefault(k, [ground, {}])
        acc = {}
        for i, ids in COLS:
            v = [x for x in (num(r[i]) if i < len(r) else None, num(r[i + 1]) if i + 1 < len(r) else None) if x is not None]
            if v:
                for lid in ids:
                    acc.setdefault(lid, []).extend(v)
        for lid, v in acc.items():
            lines.setdefault(lid, []).extend(v)
    res = {}
    for k, (g, lines) in out.items():
        m = {lid: round(sum(v) / len(v) - 100, 1) for lid, v in lines.items()}
        circ = [m[x] for x in SURFACE if x in m]
        if circ:
            m['circle'] = round(sum(circ) / len(circ), 1)
        res[k] = [g, m]
    with open(dst, 'w', encoding='utf-8') as f:
        json.dump(res, f, separators=(',', ':'), sort_keys=True)
    print(len(res), 'stations')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
