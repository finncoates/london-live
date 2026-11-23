# Is a point in Greater London? (OpenStreetMap boundary, simplified to ~30 m: greater_london.json, [[lat, lon], ...])
# London's buses come from TfL; everything outside the boundary (Watford, Dartford, Epsom...) from the national bus data.
import json, os, functools
_P = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'greater_london.json')))
_B = (min(p[0] for p in _P), min(p[1] for p in _P), max(p[0] for p in _P), max(p[1] for p in _P))
@functools.lru_cache(maxsize=1 << 20)
def in_london(a, b):
    if not (_B[0] < a < _B[2] and _B[1] < b < _B[3]): return False
    inside = False; n = len(_P); j = n - 1
    for i in range(n):
        yi, xi = _P[i]; yj, xj = _P[j]
        if (yi > a) != (yj > a) and b < (xj - xi) * (a - yi) / (yj - yi) + xi: inside = not inside
        j = i
    return inside
