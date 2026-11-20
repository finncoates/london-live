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

## Build order (tonight)
| # | Feature | Why | Effort |
|---|---|---|---|
| 1 | Smooth zoom (done) | Was the #1 complaint | — |
| 2 | **Line status**: badges in the live-map legend, a status list, warnings on route options and during a journey | Problem 1 | M |
| 3 | **Saved places + recents**: Home/Work/favourites, one-tap routes | Problem 2 | M |
| 4 | **Nearby departures**: nearest stations with next trains; tap a station on the Journey map | Problem 3 | M |
| 5 | **Get-off alert**: "Next stop: X — get off here", vibration, notification if allowed | Problem 4 | S |
| 6 | **Share my ETA** (Web Share / copy) | Problem 5 | S |
| 7 | **Installable app** (manifest, icons, offline shell) | Problem 6 | S |
| 8 | TV **departure board** mode for the live map (`?board=Oxford Circus`) | TV use | S |
| 9 | Fares where Google gives them | Nice to have | S |

## Later
- Live National Rail (waiting on the key; plan in HANDOFF.md).
- Step-free journeys (TfL planner supports accessibility preferences; Google doesn't).
- Leave-by reminders for planned trips (needs the page open, or a push service).
- Optional OSM track geometry so lines follow real curves instead of station-to-station lines.
