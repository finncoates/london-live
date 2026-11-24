# Checks every city's line file for the faults London never has: a line that doesn't reach a station it serves (part
# of it missing), a straight jump far longer than the line's usual spacing (a stretch drawn as a straight line), and
# a line end nowhere near any of its stations (a stub). Prints the worst first.
#   python -I cities/check_lines.py [city id ...]
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace')
import os, sys, json, math
HERE = os.path.dirname(os.path.abspath(__file__))
def m(a, b): return math.hypot((a[0]-b[0])*111320, (a[1]-b[1])*111320*math.cos(math.radians(a[0])))
def seg_d(p, a, b):
    c = math.cos(math.radians(a[0])); ax, ay, bx, by, px, py = a[1]*c, a[0], b[1]*c, b[0], p[1]*c, p[0]
    dx, dy = bx - ax, by - ay; L2 = dx*dx + dy*dy; t = max(0, min(1, ((px-ax)*dx + (py-ay)*dy)/L2)) if L2 else 0
    return math.hypot((ax + dx*t - px)/c*111320*c, (ay + dy*t - py)*111320)
def near_line(p, pts): return min((seg_d(p, a, b) for a, b in zip(pts, pts[1:])), default=1e9)
idx = json.load(open(os.path.join(HERE, 'fr-index.json'), encoding='utf-8'))
want = set(sys.argv[1:]); issues = []
for c in idx:
    if want and c['id'] not in want: continue
    for u in c.get('urls') or [c['url']]:
        try: d = json.load(open(os.path.join(HERE, u[7:]), encoding='utf-8'))
        except Exception as e: issues.append((9e9, c['name'], u, 'unreadable', str(e)[:60])); continue
        lines = {}
        for l in d.get('lines', []):
            pts = l['pts'] if l['pts'] and not isinstance(l['pts'][0][0], list) else [q for part in l['pts'] for q in part]
            lines.setdefault((l['name'], l['kind']), []).append(pts)
        st = {}
        for s in d.get('stations', []):
            for x in s[4]: st.setdefault((x[0], x[2]), []).append((s[1], (s[2], s[3])))
        for (name, kind), parts in lines.items():
            if kind in ('ferry', 'cable'): continue
            for s_name, p in st.get((name, kind), []):
                dd = min(near_line(p, pts) for pts in parts)
                if dd > 120: issues.append((dd, c['name'], u, f'{kind} {name} misses its station', f'{s_name} by {dd:.0f} m'))
            for pts in parts:
                hops = [m(a, b) for a, b in zip(pts, pts[1:])]
                if len(hops) > 3:
                    med = sorted(hops)[len(hops)//2]
                    for i, h in enumerate(hops):
                        if h > max(2500, 12*med): issues.append((h, c['name'], u, f'{kind} {name} straight jump', f'{h:.0f} m at {pts[i]} → {pts[i+1]} (median {med:.0f} m)'))
                ss = [p for _, p in st.get((name, kind), [])]
                if ss:
                    for end in (pts[0], pts[-1]):
                        e = min(m(end, p) for p in ss)
                        if e > 800: issues.append((e, c['name'], u, f'{kind} {name} end far from its stations', f'{end} is {e:.0f} m from the nearest'))
issues.sort(key=lambda x: -x[0])
print(len(issues), 'issues')
for x in issues[:int(os.environ.get('N', 80))]: print(f'{x[1]:<18} {x[2][7:]:<34} {x[3]:<40} {x[4]}')
