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
| oslo.json | Ruter GTFS from Entur — https://storage.googleapis.com/marduk-production/outbound/gtfs/rb_rut-aggregated-gtfs.zip (T-bane, trams, ferries; Ruter colours): `USE_ROUTE_COLOR=1 python3 cities/gtfs_lines.py rut.zip cities/oslo.json "401:metro,902:tram,1008:ferry" '{"metro":"#EC700C","tram":"#0B91EF","ferry":"#682C88"}' "59.75,10.45,60.10,11.05"` then `gtfs_stations.py` with the same types and box; buses with `citybus.py rut.zip cities/busnet 59.75 10.45 60.10 11.05`. Departures: Entur journey planner (keyless) |
| boston.json | MBTA GTFS — https://cdn.mbta.com/MBTA_GTFS.zip (official colours) |
| finland.json | Fintraffic passenger-train GTFS — https://rata.digitraffic.fi/api/v1/trains/gtfs-passenger.zip (whole network, de-duplicated: `GLOBAL_DEDUP=1 EPS=8`) |
| london-tracks.json | OpenStreetMap railway tracks (© OpenStreetMap contributors, ODbL), via the BBBike London extract: each TfL station-to-station hop routed along the real track (`osm_rails.py` then `osm_tracks.py`) |
| manchester.json | TfGM GTFS — https://odata.tfgm.com/opendata/downloads/TfGMgtfsnew.zip: Metrolink lines (line colours set by name), stops, and a compact timetable (`gtfs_sched.py`) used to place trams where no live feed exists |
| busnet/ | Every bus route outside London, from the Bus Open Data Service regional GTFS timetables (https://data.bus-data.dft.gov.uk/timetable/download/gtfs-file/<region>/), de-duplicated (each road once) and tiled 0.1°×0.1° (`busnet.py`) |
| wmids.json | West Midlands Metro from the Bus Open Data GTFS (west_midlands): no shapes in the feed, so each stop-to-stop hop is routed along the OpenStreetMap tram tracks (`gtfs_tram_osm.py`, router in `route.py`), plus a timetable (`ONLY='^Metro$' gtfs_sched.py`) for timetable-placed trams |
| busnet/ (shapeless operators) | Operators that publish no route shapes (e.g. Brighton & Hove, Reading, Oxford, Arriva) are drawn stop to stop along the real roads: `MERGE=1 NOSHAPE=1 PBF=<region>.osm.pbf busnet.py <region>.zip cities/busnet` (OSM extracts from download.openstreetmap.fr) |
| sheffield.json, blackpool.json, liverpool.json | Sheffield Supertram (+ tram-train on the main-line railway), Blackpool Tramway, Mersey Ferries, from the Bus Open Data GTFS (yorkshire / north_west), built like wmids.json with a `{"route": ["name", "#colour", "tram/tramtrain/ferry"]}` map and `NAMES='<map>' gtfs_sched.py` |
| busnet/ (v2, current) | Every bus route outside London matched onto the OpenStreetMap road network (`busnet2.py`): routes with shapes are snapped point by point and joined along the roads, routes without shapes are routed stop to stop; the map is the union of the road segments buses use, so each road is drawn once, with no gaps. `busnet2.py match <region>.osm.pbf edges_<region>.pkl <region>.zip [tfgm.zip]` per region, then `busnet2.py tiles cities/busnet edges_*.pkl` |
| busnet/ (v3) | `busnet2.py match uk.osm.pbf edges_<region>.pkl <region>.zip`: each route point is matched to the nearest road point **reachable along the roads from the previous one** (so a route never flips to a parallel road), routes are matched against the whole UK road map (regional timetables cross region borders), and any stretch of a bus route not covered by a drawn road running the same way is drawn as published and joined onto the roads at both ends — no gaps. City buses of National Express West Midlands / Coventry are buses, not coaches. |
| coachnet.json | Every National Express, FlixBus and Scottish Citylink route in the Bus Open Data timetables, routed stop to stop along Britain's main roads (OpenStreetMap, motorway→tertiary) with `coachnet.py`; routes abroad are drawn to the port they leave Britain from. Megabus publishes no open timetable. Shown with the "Coach routes" switch (off by default). |
| tyneandwear.json, glasgow.json, edinburgh.json | Tyne and Wear Metro + Shields Ferry, SPT Subway, Edinburgh Trams from the Bus Open Data GTFS (north_east / scotland), on OpenStreetMap track (`gtfs_tram_osm.py`, metro mode) + timetable (`gtfs_sched.py`) |
| nottingham.json | Nottingham NET from OpenStreetMap only (`osm_tramnet.py`): lines and stops, no open timetable |
| nr/ | National Rail network (OpenStreetMap railway=rail main/branch, one line per pair of tracks): 0.5° tiles + `all.json` overview (`osm_nr.py`), then `nr_join.py cities/nr` joins each loose end to the line it stops short of (station throats such as Leeds were drawn as broken pieces) |
| busnet/ (Northern Ireland) | Translink Metro/Glider and Ulsterbus/Goldliner route links from OpenDataNI (MapInfo MIF, `ni_routes.py` → edges for `busnet2.py tiles`) |
| busnet/ (Berlin, Boston, Helsinki) | Bus routes from each city's own GTFS shapes (VBB https://www.vbb.de/gtfs, MBTA https://cdn.mbta.com/MBTA_GTFS.zip, HSL https://infopalvelut.storage.hsldev.com/gtfs/hsl.zip), each road segment once, same 0.1° tiles: `citybus.py feed.zip cities/busnet s w n e` (Berlin 52.2 12.9 52.8 13.9, Boston 41.9 -71.8 42.9 -70.5, Helsinki 59.95 24.3 60.45 25.4). Drawn in the colour of the city's buses |
| greater_london.json / .py | Greater London's boundary (OpenStreetMap relation 175342, simplified to ~30 m). `busnet2.py` and `busstops.py` leave out only what is inside it (TfL's own routes and stops), so towns at London's edge (Watford, Dartford, Epsom…) are in `busnet/` and `stops/`; the page uses a ~200 m version to decide when a zoomed-in view is 'London' |
| stops/ | Every bus stop outside London (Bus Open Data GTFS stops + the routes calling there, `busstops.py`; Northern Ireland from the OpenDataNI Translink stop list), 0.05° tiles. Departures come live from the relay (`/vehicles?src=stop&id=<ATCO>`, bustimes.org departures, cached 45 s). |
