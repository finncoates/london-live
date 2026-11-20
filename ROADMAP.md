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

## Next ideas (not built yet)
- Live National Rail (waiting on the Rail Data Marketplace key; plan in HANDOFF.md).
- "Leave by" reminders for planned trips (needs the page open, or a push server).
- Build-my-route: apply route preferences (step-free) per step.
- Optional OSM track geometry so lines follow real curves.
- Crowding indicator per line (TfL crowding API) — check data quality first.
