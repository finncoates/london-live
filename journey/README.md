# London Journey

Plan a trip across London and get re-routed live when things go wrong: a delayed train, a missed
connection, leaving late, or getting on the wrong bus. One file (`index.html`), no build step,
hosted on GitHub Pages. Explain things to the owner in plain, non-technical language; they mostly use a phone.

## How it works
- **Map**: Google Maps (JS API, the doot key; `?gkey=` overrides). The live-trains canvas sits on top and
  uses an OverlayView projection for pixel positions.
- **Planning**: Google DirectionsService (transit) for every journey, anywhere: all modes incl. National
  Rail. TfL's journey planner is only a fallback if Google errors in London.
- **London live data**: each Google transit leg in London is matched to TfL (`tflLook` by line name /
  bus number; `enrichLeg` finds the TfL stop ids near each end, in the right direction, from the line's
  route sequence). Matched legs get roundels, live countdowns, live projection and the moving-train view.
  Everything else (National Rail, outside London) uses Google's timetable times.
- **Live tracking** (every 20 s, and when the GPS moves):
  1. `updateProgress()` works out which leg you're on from GPS (or the clock when GPS is stale).
  2. `projectPlan()` replays the rest of the trip: walking at 1.25 m/s, catching the first live TfL
     vehicle you can make (`liveDepartures()`), else the timetable; marks connections *missed*.
  3. `replan()` asks Google for the fastest route from where you are now (or your next stop if on board)
     and shows a Switch / Keep banner if you've left the route, a different route is > 2 min faster,
     or a connection is missed. Same route still best → just updates the arrival time.
- Your own train/bus is drawn bigger with a ring; tap any train for line, destination, next stop, number.
- The journey is saved in localStorage (reload resumes it); screen wake lock while active.

## Google key
The key is public in the page: restrict it to the site's address in Google Cloud Console.

## URL options
`?sim=1` test mode (drag the blue pin to pretend to move) · `?theme=dark|light` · `?app_key=` TfL key
(optional, for higher rate limits) · `?debug=1` (exposes `window.APP`) · `?view=lat,lon,zoom`

## Known limits / next ideas
- National Rail and non-London legs use Google's timetable times (live National Rail: see london-live's
  HANDOFF for the Rail Data Marketplace plan).
- While on board, alternatives are planned from your next alighting stop (not "get off early").
- Bus positions come from arrival predictions (no GPS feed from TfL), so they're approximate.
- Possible next steps: notifications when the screen is off, step-free/accessibility options,
  "leave by" reminders before the trip.
