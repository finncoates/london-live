# City line maps

Each `<city>.json` is the rail / metro / tram / ferry network of a city, baked from that city's official
GTFS timetable (route shapes, simplified to ~3 m), so the live map can draw the lines and snap the live
vehicles onto them.

| File | Source (open data) |
|---|---|
| helsinki.json | HSL GTFS — https://infopalvelut.storage.hsldev.com/gtfs/hsl.zip |
| berlin.json | VBB GTFS — https://www.vbb.de/vbbgtfs (official line colours) |

Rebuild (e.g. after timetable changes):
`python3 cities/gtfs_lines.py hsl.zip cities/helsinki.json "0:tram,1:metro,109:train,4:ferry"`
`USE_ROUTE_COLOR=1 python3 cities/gtfs_lines.py vbb.zip cities/berlin.json "109:train,100:train,400:metro,900:tram,1000:ferry" '{"train":"#008D4F","metro":"#115D91","tram":"#CC0A22","ferry":"#0080BA"}' "52.33,13.08,52.68,13.77"`
