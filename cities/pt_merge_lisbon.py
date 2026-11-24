# Lisbon is drawn from several operators' timetables (Metro, Carris's trams and lifts, Metro Sul do Tejo, the Tagus
# ferries): their separate entries in fr-index.json become one city with all their files (the map loads every file of
# the city in view).
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace')
import os, json
HERE = os.path.dirname(os.path.abspath(__file__)); f = os.path.join(HERE, 'fr-index.json')
idx = json.load(open(f, encoding='utf-8'))
for city, prefix in (('Lisbon', 'lisbon-'),):
    parts = [c for c in idx if c['id'].startswith(prefix) or c['id'] == prefix.rstrip('-')]  # (the city merged before: an operator built again joins it)
    if not parts: continue
    b = [min(c['box'][0] for c in parts), min(c['box'][1] for c in parts), max(c['box'][2] for c in parts), max(c['box'][3] for c in parts)]
    urls = list(dict.fromkeys(u for c in parts for u in (c.get('urls') or [c['url']])))
    idx = [c for c in idx if not c['id'].startswith(prefix) and c['id'] != prefix.rstrip('-')]
    idx.append({'id': prefix.rstrip('-'), 'name': city, 'box': b, 'url': urls[0], 'urls': urls, 'bus': parts[0]['bus']})
    print(city, len(urls), 'files', b)
json.dump(idx, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
