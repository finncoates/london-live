# London Journey + Live Trains — critical review and roadmap

Written overnight, 20–21 Nov 2026. Honest first, then what to build.

## What the apps are for (and who they compete with)
Google Maps and Citymapper already plan journeys well. To be worth opening, these apps must do
something they don't. Our genuine edges are:
1. **Build my route**: you choose the mode for every step (walk → train → cycle → bus). Nobody else does this well.
2. **Live picture**: you can *see* your train moving, and every other one; the TV map is unique.
3. **Re-routing that keeps your choices**: late, missed a train, wrong bus → a better plan *using your modes*.

Everything else should support those three, or remove friction for everyday use.

## Critical problems today (ranked by how often they would annoy a real user)
1. **No service status.** The first question every London commuter asks is "is my line OK?". We show
   live trains but not that the Central line is suspended. → Biggest gap. Easy: TfL `/Line/Mode/.../Status`.
2. **Typing every trip on a phone.** No saved places (Home/Work), no recent destinations.
3. **"When's my next train?"** needs a whole journey plan. There is no "departures near me".
4. **The tracking moment that matters most has no alert:** "your stop is next — get off". Tracking
   without that is a pretty map, not a tool.
5. **No way to tell someone when you'll arrive.** (Share ETA.)
6. **Not installable.** Add-to-home-screen gives no proper icon or full-screen app feel.
7. **Only works while the page is open and on screen** (browsers stop pages in the background).
   Wake lock helps; true background alerts need a push server — out of scope for a static site.
8. **Underground has no GPS** → progress is assumed from the clock. Acceptable, but say so.
9. **National Rail is timetable-only** until the Rail Data Marketplace key arrives.
10. **Fire TV performance** is unknown with Google Maps (heavier than the old map).

Things I considered and rejected for now: live buses on the map (thousands of predictions, heavy,
little value on a map), crowding (TfL crowding API is patchy), weather, social features.

## Built overnight (20–21 Nov) — all live, each tested in a browser on desktop + phone, light + dark
| Feature | Where |
|---|---|
| Smooth zoom (layers follow Google's in-between zoom; lines cached off-screen; lighter layer resolution) — ~2× fps on Retina | both |
| Line status: badges, "N lines with problems" + reasons, warnings on routes and steps | both |
| Saved places (Home/Work/favourites) + recents, one-tap routes, suggestions when tapping an empty box | Journey |
| Near you: live departures from nearest stations + bus stops; tap any station on the map; "Route here" | Journey |
| Alerts: time to leave, get off at the next stop, arrived (vibration + notification if allowed) | Journey |
| Share ETA (share sheet or copy) | Journey |
| Installable app (manifest, original icon, offline shell, service worker) | Journey |
| TV departure board (`?board=Oxford Circus` or "Show as TV board") | Live map |
| Fares on route options (where Google gives them) | Journey |
| Route preferences: fastest / fewer changes / less walking / step-free (TfL; bus fallback when no step-free rail) | Journey |
| Arrive by (plan backwards from a time) | Journey |
| Customise: turn any planned route into an editable Build-my-route chain | Journey |
| 10 bugs from an independent code review fixed (see git log) | both |

## Built 21 Nov (day)
| Feature | Where |
|---|---|
| National Rail framework, ready for the key: relay (`rail/worker.js`), 660 stations, live NR trains per operator, rail in station search/TV board, live rail legs in Journey (expected time, delay, platform, re-planning), `?rail=demo`, `rail/SETUP.md` | both |
| Automatic low-power mode for slow devices (Fire TV): 15 fps, no outlines; `?quality=low|high` | both |
| Leave-by reminders: Remind me, live re-check 25/10 min before, alerts at −5/0, one-tap Start | Journey |
| Step-free per step in Build my route (TfL step-free per mode, bus fallback) | Journey |
| Commute card (Home ⇄ Work, leaving now, problems on the way) | Journey |
| Follow a train (tap it) and TV tour mode (`?tour=1`, T key) | Live map |
| 12 findings from a second independent review fixed | both |
| Line problems on the map (severe = dashed, closed = faded + dashed); "live data delayed / no internet" notice | both |
| TV auto mode (`?auto=1`): overview → train tour → departure boards | Live map |
| Lift-out-of-service warnings for stations on your route | Journey |
| Fixes from user-style review: no false "late" at start, destination name kept after reroute, nearest bus stop | Journey |
| Station dots on the lines when zoomed in (bigger for interchanges); station names too when "Hide places & labels" is on | both |
| Return trip: one tap plans the way back to where you started | Journey |
| Tap a station dot on the live map → its next trains (a tap right on the dot wins over a train waiting there) | Live map |
| Planned works for later trips: routes and reminders an hour or more ahead show TfL's planned closures/reduced service for that time, not today's live problems | Journey |
| Earlier / Later buttons under route options (moves the time by 15 min) | Journey |
| Station taps on both maps no longer also pop up a train's info card | both |
| Legend: Show all / Hide all (hide all, then tap a line = just that line); hidden lines lose their station dots | Live map |
| Bookmarkable stations: `?station=Bank` opens its next trains; the address updates when you open a station | Live map |
| Station card shows problems on that station's lines (short reason; full text on hover) | Live map |
| 8 findings from a third independent review fixed (planned-works refresh/fallback, Return trip start after swap/reminder, Earlier/Later limits, "London" kept in station labels, station grouping) | both |
| "Leave in 4 min" / "Leave now" on route options (live, every 30 s); routes that have already left are faded and marked "Missed" | Journey |
| "Plan a trip here" on station cards opens London Journey with that station as the destination (`journey/?to=Name&ll=lat,lng`) | both |
| Stations whose platforms are far apart (Paddington) get a dot on each line, one name | both |

## Built 21–22 Nov (overnight)
| Feature | Where |
|---|---|
| Live buses: "Buses" switch; zoom in (14+) and the ~12 busiest routes around the view load, thin route lines, buses moving from TfL predictions, route numbers from zoom 15.5; `?buses=1` | Live map |
| Beyond London (framework, switch on with free keys): relay now also serves **buses with GPS across England** (Bus Open Data), **Edinburgh buses + trams** (no key) and **Manchester Metrolink**; map draws GPS vehicles gliding between updates, tap for route/destination/operator; tested with fake feeds (`node rail/test-worker.mjs`) and `?rail=demo` | Live map + relay |
| National Rail anywhere in Britain: 2,610 stations; outside London the 25 stations nearest the view are polled; demo trains in Manchester, Leeds, Edinburgh/Glasgow, Birmingham | both |
| Lines back to a simple style: one smooth solid line per route (pieces joined so every bend is rounded), TfL colours and double lines kept, no dashed "problem" lines; side-by-side layout is an option in the Map menu | both |
| **Finland: every train in the country live** (GPS from Digitraffic, open data, no key, straight from the browser): type, route, speed; Helsinki commuter trains purple, long-distance green, freight grey | Live map |
| **Helsinki: every tram, metro, bus and ferry live each second** (HSL open MQTT feed, no key): HSL colours, route + destination, speed, on time/late; zoom 12+ (only the map tiles on screen are followed) | Live map |
| **Norway: buses, coaches, trains and ferries with GPS** (Entur, open data, no key) — best in Bergen (Skyss), Trondheim, Tromsø; Oslo's Ruter doesn't publish to this feed; parked vehicles (no report for 10 min) hidden | Live map |
| **Boston: MBTA subway, light rail, commuter rail and buses with GPS** (MBTA v3 API, no key), official line colours, with the subway lines drawn (MBTA shapes, cached a week) | Live map |
| Fixes from a fourth independent review: joined lines never pass a stop twice (loops, out-and-back routes); switching country drops the old vehicles; bus updates debounced and arrivals throttled (TfL rate limit); 10 s timeouts on every feed; Helsinki feed stops cleanly when you leave; National Rail re-polls only after a ~25 km move and not abroad; faster relay parsing; tighter Finland/Norway borders | both + relay |
| Relay also serves **Tallinn (250 buses/trams), Gdańsk (140), Vilnius** — open feeds that don't allow browsers directly, so they switch on with the relay (no key); tested end-to-end with the real feeds through the relay code | Live map + relay |
| **Berlin & Brandenburg: S-Bahn, U-Bahn, trams, buses, regional trains** (VBB real-time positions, no key) in BVG/VBB colours | Live map |
| **Bikes: Santander Cycles docks live** (TfL): bikes, e-bikes (blue dot) and free docks; tap for details; `?bikes=1`. Lime/Forest/Voi/Dott publish no open data for London | Live map |
| **City line maps** for Helsinki (metro, trams, local trains, ferries) and Berlin (S-Bahn, U-Bahn, trams, regional, in official colours), baked from GTFS (`cities/`); vehicles snap onto their own line and face along it; Explore switches hide lines and vehicles together (Boston too) | Live map |
| Fixes from a fifth independent review: line-search card no longer overwritten by an old station card; taps work outside London (UK region); right departures source per city file; failed bus routes not retried every refresh; Explore switches abroad apply at once; faster bent trains and city station dots | Live map |
| **Road works layer** ("Road works" switch): TfL road disruptions as warning triangles (red = closure), tap for what, where and until when | Live map |
| **Bus stops**: with Buses on and zoomed in (16+), stops show as red markers with their letter; tap for the next buses | Live map |
| **How busy + lifts on station cards**: TfL crowding (live when available, else the typical pattern for today with a 5am–midnight chart) and lifts out of service at that station | Live map |
| **River boats and cable car**: Uber Boat RB1/RB4/RB6 and the Woolwich Ferry moving live (TfL predictions), routes following the Thames (OpenStreetMap river centreline); IFS Cloud Cable Car line; own switches | Live map |
| **Shared track split side by side**: where 2, 3, 4… lines share track (Circle + District, H&C + Met…) each gets an equal slice of the line width, so all colours show | both |
| **Trains bend with the track**: each train is drawn along the stretch of line it covers, so it follows curves (straight shape only where no track is known) | both |
| Station cards: next departures grouped by kind (Tube, Overground, Buses from stops within 250 m, S-Bahn, U-Bahn, trams, commuter rail…) in London, Berlin, Boston and Finland; bus routes no longer drawn as straight cuts | Live map |
| Crosscheck fixes: abroad, search finds that city's stations and lines (not London's); buses abroad on by default with their own switch (Bergen/Trondheim are mostly buses) | Live map |
| **Lines follow the real track** (OpenStreetMap): 589 of 620 London station-to-station hops traced along the actual railway, checked for realism (no hooks into sidings/other lines, no detours or hairpins; Tube lines prefer Underground track; anything doubtful drawn straight) (e.g. Peckham Rye–Denmark Hill), trains follow them; long "express" pairs no longer drawn as straight lines | both |
| **Search a line**: type a bus number (172), a Tube line (Victoria) or a line abroad (U8, M1): the route is shown with its live vehicles and everything else fades; ✕ to show all | Live map |
| **Stations in every city**: dots + names like London; tap for live departures (Finland: Fintraffic; Boston: MBTA; Berlin: VBB). Helsinki metro/tram departures need a free HSL key | Live map |
| **Explore menu** (globe button): continent → country → city → that city's transport switches, with what's live now and what's coming | Live map |
| **Bikes & scooters to hire** from open GBFS feeds: Berlin (nextbike, Dott), Helsinki (city bikes, Bird), Bergen, Trondheim (+Dott), Boston (Bluebikes), Gdańsk (MEVO), Vilnius, Manchester/Leeds/Birmingham (Beryl, Veo), Liverpool (Bolt), Bristol (Dott), London (Beryl cargo bikes); docks with counts, free bikes (dots) and scooters (squares), tap for range/battery. Lime publishes open data only in other cities (none on the map yet) | Live map |
| Slimmer lines (like a transit map layer) and slightly smaller trains | both |
| Map menu → Go to grouped: live now (London, Helsinki, Finland, Bergen, Trondheim, Berlin, Boston) / rest of Britain (live once keys are set up) | Live map |
| Region-aware panel: outside London the title, counts and notes describe what's live there; London legend/status/TfL chips hidden | Live map |
| Map menu → Go to: London, Manchester, Birmingham, Leeds, Liverpool, Newcastle, Edinburgh, Glasgow, Bristol, Cardiff | Live map |

## Next ideas (not built yet)
- Switch on live National Rail (waiting on the key; `rail/SETUP.md`) and buses beyond London (free BODS key, instant).
- Other countries checked 21–22 Nov: Tallinn (transport.tallinn.ee/gps.txt, keyless, but no CORS → relay); Boston MBTA to try; Germany db.transport.rest down; Edinburgh TfE server down (522).
- Other countries checked 21 Nov: Switzerland (transport.opendata.ch, departure boards only, CORS ok); Germany (v6.db.transport.rest radar = live positions, keyless) didn't connect from the sandbox; Helsinki HSL live vehicles via MQTT (mqtt.hsl.fi) to try.
- Research notes (21 Nov): no GB rail source gives GPS train positions; RealTimeTrains API (free, personal use) is the best alternative to Darwin; Tyne & Wear Metro only via an unofficial API; Glasgow Subway / Sheffield / Nottingham / Blackpool trams have no public live feed.
- Optional OSM track geometry so lines follow real curves.
