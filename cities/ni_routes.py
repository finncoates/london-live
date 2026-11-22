# Northern Ireland bus routes (Translink Metro/Glider and Ulsterbus/Goldliner route links, OpenDataNI, MapInfo MIF, WGS84)
# -> edges_ni.pkl for busnet2.py tiles (each stop-to-stop link's geometry; identical stretches collapse into one)
#   python3 ni_routes.py PtLinks_mtt.ptl.MIF PtLinks_y18.ptl.MIF edges_ni.pkl
import sys, pickle
E = set(); n = 0
for f in sys.argv[1:-1]:
    lines = open(f, encoding='latin-1').read().split('\n'); i = 0
    while i < len(lines):
        t = lines[i].split()
        if t and t[0].upper() == 'PLINE':
            parts = 1
            if len(t) > 1 and t[1].upper() == 'MULTIPLE': parts = int(t[2]); i += 1; cnt = [int(lines[i].split()[0])]
            else: cnt = [int(t[1])] if len(t) > 1 else [int(lines[i+1].split()[0])]
            if len(t) == 1: i += 1
            for pi in range(parts):
                if pi: i += 1; cnt.append(int(lines[i].split()[0]))
                pts = []
                for j in range(cnt[-1]):
                    i += 1; x, y = map(float, lines[i].split()[:2]); pts.append((round(y, 5), round(x, 5)))
                for a, b in zip(pts, pts[1:]):
                    if a != b: E.add((a[0], a[1], b[0], b[1]) if a < b else (b[0], b[1], a[0], a[1]))
                n += 1
        elif t and t[0].upper() == 'LINE':
            x1, y1, x2, y2 = map(float, t[1:5]); a, b = (round(y1, 5), round(x1, 5)), (round(y2, 5), round(x2, 5))
            if a != b: E.add((a[0], a[1], b[0], b[1]) if a < b else (b[0], b[1], a[0], a[1])); n += 1
        i += 1
pickle.dump({'edges': E, 'raw': []}, open(sys.argv[-1], 'wb'))
print(n, 'route links ->', len(E), 'distinct road segments')
