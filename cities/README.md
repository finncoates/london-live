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
| boston.json | MBTA GTFS — https://cdn.mbta.com/MBTA_GTFS.zip (official colours) |
| finland.json | Fintraffic passenger-train GTFS — https://rata.digitraffic.fi/api/v1/trains/gtfs-passenger.zip (whole network, de-duplicated: `GLOBAL_DEDUP=1 EPS=8`) |
| london-tracks.json | OpenStreetMap railway tracks (© OpenStreetMap contributors, ODbL), via the BBBike London extract: each TfL station-to-station hop routed along the real track (`osm_rails.py` then `osm_tracks.py`) |
| manchester.json | TfGM GTFS — https://odata.tfgm.com/opendata/downloads/TfGMgtfsnew.zip: Metrolink lines (line colours set by name), stops, and a compact timetable (`gtfs_sched.py`) used to place trams where no live feed exists |
| busnet/ | Every bus route outside London, from the Bus Open Data Service regional GTFS timetables (https://data.bus-data.dft.gov.uk/timetable/download/gtfs-file/<region>/), de-duplicated (each road once) and tiled 0.1°×0.1° (`busnet.py`) |
| wmids.json | West Midlands Metro from the Bus Open Data GTFS (west_midlands): no shapes in the feed, so each stop-to-stop hop is routed along the OpenStreetMap tram tracks (`gtfs_tram_osm.py`, router in `route.py`), plus a timetable (`ONLY='^Metro$' gtfs_sched.py`) for timetable-placed trams |
| busnet/ (shapeless operators) | Operators that publish no route shapes (e.g. Brighton & Hove, Reading, Oxford, Arriva) are drawn stop to stop along the real roads: `MERGE=1 NOSHAPE=1 PBF=<region>.osm.pbf busnet.py <region>.zip cities/busnet` (OSM extracts from download.openstreetmap.fr) |
| sheffield.json, blackpool.json, liverpool.json | Sheffield Supertram (+ tram-train on the main-line railway), Blackpool Tramway, Mersey Ferries, from the Bus Open Data GTFS (yorkshire / north_west), built like wmids.json with a `{"route": ["name", "#colour", "tram/tramtrain/ferry"]}` map and `NAMES='<map>' gtfs_sched.py` |
| busnet/ (v2, current) | Every bus route outside London matched onto the OpenStreetMap road network (`busnet2.py`): routes with shapes are snapped point by point and joined along the roads, routes without shapes are routed stop to stop; the map is the union of the road segments buses use, so each road is drawn once, with no gaps. `busnet2.py match <region>.osm.pbf edges_<region>.pkl <region>.zip [tfgm.zip]` per region, then `busnet2.py tiles cities/busnet edges_*.pkl` |
