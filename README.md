# London Live

**A live map of public transport across London, the UK and Europe:** trains, Tube, metros, trams, buses, coaches
and ferries, moving on the map where they are right now.

**Open the map:** https://finncoates.github.io/london-live/ · **Service status:** https://finncoates.github.io/london-live/status.html

It runs in any modern browser, on a phone, a computer or a TV, and can be installed as an app. Nothing to sign up for,
no tracking.

## What it shows

- **London:** every Tube, Elizabeth line, Overground, DLR, tram, cable car and river bus, live from TfL; London's buses
  close up; hire bikes.
- **Great Britain:** National Rail trains (live from Darwin, the industry's real-time feed), live buses and coaches
  (National Express, Megabus, FlixBus, Scottish Citylink), trams and metros in Manchester, Birmingham, Sheffield,
  Newcastle, Edinburgh and Glasgow, and the ferries.
- **Europe and beyond:** 175 cities and whole national rail networks in 30 countries (France, the Netherlands,
  Belgium, Switzerland, Germany, Poland, Czechia, Portugal, Spain, Italy, Austria, the Nordic and Baltic countries,
  Ireland and more, plus Toronto and Japan). Lines are drawn along the real track, and vehicles are live where the
  operator publishes positions, otherwise placed from the timetable with live delays where those are shared.

In London every train runs on its own track: Tube and Elizabeth line trains in their tunnels, main-line trains on the
fast or slow lines they really use, each standing at its real platform; tracks shared by a TfL line and main-line trains
are drawn as such (Brockley), as are the Tyne and Wear Metro's at Sunderland and Sheffield's tram-train.

Solid vehicles are live positions; pale ones with a coloured edge are placed from the timetable; a see-through one is
catching up with where a new report says it really is. The full city-by-city
picture is in [COVERAGE.md](COVERAGE.md).

## What you can do

- **Tap a stop** for its next departures (live where available), with operators' notices about works and diversions.
- **Tap a vehicle** for its next stops, its platform and how late it is (National Rail trains: minutes behind the
  timetable, from Darwin), and **Follow** it; in London, **Ride along** keeps the map on your train.
- **Directions:** plan a journey from where you are to any stop or place in Europe, drawn on the map, with the
  vehicles you'd ride highlighted.
- **Search** any stop, street or place in Europe; **save stops** (☆) for one-tap departures; **share** a link to a stop
  or a vehicle; get an **alert** 2 minutes before a departure.
- **Near me** (⌖) opens the nearest stop's departures.
- Switch each kind of transport on and off, its vehicles and its lines separately.
- In English, French, German, Dutch, Spanish, Italian, Polish or Portuguese (from your browser, or `?lang=fr`).
- Works offline with the last data it had, and as a full-screen TV display (`?kiosk=1`).

## Where the data comes from

Thank you to everyone who publishes open transport data. This map would not exist without:

| Source | Used for |
|---|---|
| [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors (via [OpenFreeMap](https://openfreemap.org) and [Geofabrik](https://download.geofabrik.de)) | The base map, railway track and roads. © OpenStreetMap contributors, ODbL |
| [Transport for London](https://tfl.gov.uk/info-for/open-data-users/) | London's trains, buses and stations. Powered by TfL Open Data; contains OS data © Crown copyright and database rights |
| [Rail Data Marketplace](https://raildata.org.uk) (Network Rail / National Rail, Darwin) | Live train running in Great Britain |
| [Bus Open Data Service](https://www.bus-data.dft.gov.uk) and [bustimes.org](https://bustimes.org) | Live buses and coaches in Great Britain |
| [Transitous](https://transitous.org) | Timetables, live delays, departures, search and journey planning across Europe |
| [adsb.lol](https://adsb.lol) (ODbL), with [adsb.fi](https://adsb.fi) and [airplanes.live](https://airplanes.live) as fallbacks | Planes: live aircraft positions from volunteer ADS-B receivers |
| [OpenStreetMap](https://www.openstreetmap.org) (ODbL) | Station platforms and their tracks |
| [Mobility Database](https://mobilitydatabase.org), [transport.data.gouv.fr](https://transport.data.gouv.fr) and national open-data portals | The timetables each city's lines are drawn from |
| Live feeds from operators and agencies, including OVapi (Netherlands), VBB (Berlin), HSL (Helsinki), Entur (Norway), Trafiklab (Sweden), Transport for Edinburgh and many French networks | Live vehicle positions |
| [AISStream](https://aisstream.io) | Live ferry positions |
| GBFS feeds | Hire bikes and scooters |
| [MapLibre GL JS](https://maplibre.org) | Drawing the map |

Each source's own licence and terms apply to its data.

## How it works

- **`index.html`** is the whole app: one page (MapLibre underneath, the vehicles drawn on a canvas on top), hosted on
  GitHub Pages. `i18n.js` holds the translations, `sw.js` the offline cache, `status.html` the status page.
- **`rail/worker.js`** is a Cloudflare Worker (the "relay"). It holds the API keys, adds caching shared by every
  visitor, and passes on requests the browser can't make directly.
- **`rail/darwin/`** is a small always-on Node.js server (on an Oracle Cloud machine). It reads the Darwin rail feed,
  AIS ferry positions and about 150 live GPS feeds, and serves them to the relay. `connect.ps1` sets it up and
  enters its keys.
- **`cities/`** holds each city's lines and stations (`*.json`), the shared bus-route, stop and railway tiles, and the
  Python scripts that build them from open timetables and OpenStreetMap (`fr_build.py`, `osm_rail.py`,
  `line_snap.py`, `simplify_lines.py`, `refresh.py` and others). See [cities/README.md](cities/README.md).

## Running it locally

```sh
python -m http.server 8765        # then open http://127.0.0.1:8765/
```

The page works as it is; live data comes through the public relay, which also accepts `localhost` pages.

## Tests

```sh
cd tools && npm ci                # once: installs puppeteer-core
node tools/smoke.mjs              # opens the map in five places: no script errors, lines load, frame rate (runs before every push)
node tools/features.mjs           # stop cards, saving, sharing, vehicle cards, Follow, switches, search, French, Near me
```

Both use a local Edge or Chrome (or `BROWSER=/path/to/chrome`). GitHub Actions run them nightly, along with a check
every 30 minutes that the site, the relay and the server are answering.

## Keeping the data fresh

`cities/refresh.py` checks each city's timetable at its source every week (Windows Task Scheduler on the build
machine), rebuilds the ones that changed, checks them and publishes. Its report lists any city that needs rebuilding by
hand.

## Found a problem?

Check the [status page](https://finncoates.github.io/london-live/status.html) first: it shows which live sources are
answering. Script errors in visitors' maps are reported anonymously (the message, the line, which country was on
screen and the browser family; nothing about the person) so problems are seen even when nobody reports them.

## Licence

© 2026 finncoates (github.com/finncoates). All rights reserved. The code is public to read, but it isn't licensed for reuse: please ask
before copying, changing or running your own version of it.

The data shown belongs to its sources, under their own licences (above).
