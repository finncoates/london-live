# London Journey

Plan a trip across London and get re-routed live when things go wrong: a delayed train, a missed
connection, leaving late, or getting on the wrong bus. One file (`index.html`), no build step,
hosted on GitHub Pages. Explain things to the owner in plain, non-technical language; they mostly use a phone.

## How it works
- **Planning**: TfL Journey Planner (`/Journey/JourneyResults/{from}/to/{to}`), free, no key needed.
  Place names, stations and postcodes work; ambiguous names come back as HTTP 300 with
  "did you mean" options. Times in responses are London local time without an offset (`londonMs()`).
- **Live tracking** (every 20 s, and when the GPS moves):
  1. `updateProgress()` works out which leg you're on from GPS (or from the clock when GPS is
     stale, e.g. underground), and whether you're on board.
  2. `projectPlan()` replays the rest of the trip with live data: walking at 1.25 m/s, then for
     each of the next two vehicle legs the first live train/bus you can actually catch
     (`liveDepartures()`: vehicles predicted at both the boarding and alighting stop, in that order),
     using its own predicted arrival. If there's no live data it uses the timetable, and marks a
     connection *missed* if its planned time has passed.
  3. `replan()` asks the journey planner for the fastest route from where you are now (or from
     the next stop if you're on board). It shows a banner (**Switch** / **Keep current**) if:
     you've left the route (two GPS fixes > 250 m off), a different route is > 2 min faster, or a
     connection is missed and a different route is best. If the same route is still best, it just
     updates the arrival time ("10 min late").
- **Live map**: all London trains (engine copied from `finncoates/london-live`: TfL arrivals →
  positions along the line) shown dimmed during a journey; the line(s) you're using are pinned,
  bus routes are added on demand, and your own train/bus is drawn bigger with a ring.
- The journey is saved in localStorage, so reloading the page resumes it. Uses a screen wake lock
  while a journey is active.

## Outside London: Google
- Trips TfL can't plan (start/end outside London, or TfL's best place match scores < 900) go to
  Google's DirectionsService (Maps JS API, loaded only when needed, key = the doot key, `?gkey=` overrides).
- Google gives timetable times only (no live boards/vehicles), so projection uses the timetable and
  re-planning (every 2 min / off-route / missed) uses Google again.
- Google's terms only allow drawing its routes on a Google map, so Google journeys are shown as a step
  list with an "Open route in Google Maps" link, not drawn on this (Esri) map.
- The key is public in the page: restrict it to the site's address in Google Cloud Console.

## URL options
`?sim=1` test mode (drag the blue pin to pretend to move) · `?theme=dark|light` · `?app_key=` TfL key
(optional, for higher rate limits) · `?debug=1` (exposes `window.APP`) · `?view=lat,lon,zoom`

## Known limits / next ideas
- National Rail legs use the timetable only (TfL has no live National Rail data; see london-live's
  HANDOFF for the Rail Data Marketplace plan).
- While on board, alternatives are planned from your next alighting stop (not "get off early").
- Bus positions come from arrival predictions (no GPS feed from TfL), so they're approximate.
- Possible next steps: notifications when the screen is off, step-free/accessibility options,
  "leave by" reminders before the trip.
