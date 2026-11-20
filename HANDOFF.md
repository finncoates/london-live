# London Live Trains — handoff

## Goal
A single-file HTML page (`index.html`) showing a live, top-down map of London rail
(Tube, Elizabeth line, DLR, Overground). Each train is drawn as a short line segment
in its line colour, moving in real time. Target: full-screen on a JVC LT-40C700 TV (1080p)
through a Fire TV Stick's Silk browser, hosted on GitHub Pages. A Tokyo version comes later.

## URL options
`?theme=dark|light` `?kiosk=1` `?lines=victoria,central` `?modes=tube,dlr,elizabeth,overground`
`?app_key=TFLKEY` `?carto_key=CARTOKEY` `?refresh=30` `?fps=30` `?view=lat,lon,zoom` `?debug=1`

Live at https://finncoates.github.io/london-live/ — suggested TV URL: `https://finncoates.github.io/london-live/?kiosk=1&theme=dark&fps=20`

## v2 — tested against the live TfL API (20 Nov 2026)
Findings and fixes:
- **CARTO basemaps now need an API key** (unkeyed tiles are watermarked "API KEY REQUIRED").
  Default basemap is now Esri Light/Dark Gray Canvas (keyless); `?carto_key=` switches back to CARTO.
- **Station ids**: some predictions use ids that only appear in the *inbound* route sequence
  (Mildmay Clapham Junction) or a different NaPTAN id altogether (Elizabeth at Farringdon,
  Whitechapel, Abbey Wood; H&C at Paddington). Both directions are now loaded and unknown ids
  are matched by station name. Geometry cache key bumped to `seq2:`.
- **vehicleId quality**: all tube lines have ids except some Metropolitan trains (`000`).
  **DLR has no vehicle ids at all.** Elizabeth/Overground ids are per trip (`20261120…`), not per unit.
  - Trains without ids: predictions at consecutive stations are matched up (a train seen at the
    previous station and later at this one is the same train); leftovers are trains between
    the two stations. They're followed across refreshes by nearest position.
  - Rail feeds list **timetabled trips that haven't started** (a few seconds from their first
    station, then 20–100 min to the next). These are dropped, which removed ~60 Elizabeth/Overground ghosts.
  - Interchanges can list one train under two ids (Elizabeth Paddington PADTON/PADTLL): merged.
- **Position model**: the feed is ~60 s old (`s-maxage=60`), so a stop's predicted time has
  often passed already. Each train now keeps its next 4 predicted stops and continues to the
  following stop instead of waiting at a station until the next refresh. Trains never slide
  backwards within a segment. Corrections glide (2 s time constant) instead of jumping.
  Result: ~0–1.5 % of train-seconds show a visible correction (was ~10–20 % of trains per refresh).
- **Segment times** are learned from live data (difference between consecutive predictions
  minus a dwell time) and cached in localStorage (`segt:` keys). Fallback: distance / mode speed.
- **Shared track**: trains keep left, and Circle/H&C/District/Met (plus Piccadilly, Lioness)
  get lanes so they draw side by side.
- **Overground colours** set to the TfL digital colour standard: Liberty #61686B, Lioness #FFA600,
  Mildmay #006FE6, Suffragette #18A95D, Weaver #9B0058, Windrush #DC241F.
- **Rate limits**: requests run in parallel and with backoff on errors; a failed chunk keeps its
  lines' trains. A 429 shows a hint to add `?app_key=` (TfL also returns 429 for an invalid key).
  Unkeyed use is 3 requests every 30 s, well under the anonymous limit.
- **Performance**: train drawing is batched (one canvas path per colour), and the heading comes
  from lat/lng without projecting. `draw()` is ~1.7 ms/frame on a desktop (~10 ms at 6× CPU throttle).
  Each refresh downloads ~280 KB gzipped, but that's **~6.8 MB of JSON** to parse (~1 s at 6× throttle),
  which may cause a brief hitch every 30 s on the Fire TV Stick. Use `?refresh=45` if needed.

## Known limits / ideas
- TfL `lineStrings` are straight lines between stations, not real track. Real curves would need
  OSM railway geometry baked into the file.
- The Piccadilly line was closed by a strike during testing, so it is barely exercised.
- Elizabeth west of Paddington / east of Liverpool St runs on Network Rail track; its predictions are rougher.

## To do
1. Deploy to GitHub Pages and test on the TV (Silk): check fps 15/20/30 and the refresh hitch.
2. Tokyo version.
