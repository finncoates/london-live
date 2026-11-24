# Switzerland's lake boats and mountain lifts are drawn everywhere in the country: one 'Switzerland' entry carries their
# files (for the view outside a city), and each Swiss city's entry carries them too (the map loads only the files of the
# city in view: Zürich's lake boats would be missing otherwise). Run after building ch-lifts / ch-boats or any Swiss city.
import sys as _s; _s.stdout.reconfigure(encoding='utf-8', errors='replace')
import os, json
HERE = os.path.dirname(os.path.abspath(__file__)); f = os.path.join(HERE, 'fr-index.json')
idx = json.load(open(f, encoding='utf-8'))
extra = [c['url'] for c in idx if c['id'] in ('lifts', 'boats') and c['url'].startswith('cities/ch-')]
extra = list(dict.fromkeys(extra + [u for c in idx if c['id'] == 'switzerland' for u in c.get('urls', [])]))
idx = [c for c in idx if not (c['id'] in ('lifts', 'boats') and c['url'].startswith('cities/ch-')) and c['id'] != 'switzerland']
for c in idx:
    if c['url'].startswith('cities/ch-'):
        c['urls'] = list(dict.fromkeys((c.get('urls') or [c['url']]) + extra))
if extra:
    idx.append({'id': 'switzerland', 'name': 'Switzerland', 'box': [45.8, 5.9, 47.85, 10.55], 'cc': 'ch', 'url': extra[0], 'urls': extra, 'bus': ['#7E8BA3', '#97A6BF']})
json.dump(idx, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print(len(extra), 'country-wide files;', sum(c['url'].startswith('cities/ch-') for c in idx), 'Swiss entries')
