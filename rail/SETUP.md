# Switching on live National Rail (and buses/trams around Great Britain)

Everything is built and tested with demo data. When your Rail Data Marketplace (RDM) access is approved,
it takes about 10 minutes. Nothing here costs money.

## Why a "relay"?
Your RDM key must stay secret, and the web pages are public. So a tiny free program (`worker.js`)
runs on Cloudflare, keeps the key, asks National Rail for the departure boards and passes only the
train information to the maps.

## Step 1 — check your RDM key (2 min)
1. Go to https://raildata.org.uk → **My subscriptions** → open **Live Departure Board** (or
   *Live Arrival and Departure Board*).
2. Open the **Specification** tab. Note:
   - the **Consumer key** (long string), and
   - the endpoint address for **GetDepBoardWithDetails** (it starts with `https://api1.raildata.org.uk/`).
3. Tell Claude "my rail data key is ready". Claude will open a secure form to enter the key **for
   testing only** (it's stored on your cloud environment, never in the code or chat) and check the
   address and data format before you continue.

## Step 2 — create the relay on Cloudflare (5 min)
1. Sign up (free) at https://dash.cloudflare.com/sign-up and confirm your email.
2. In the dashboard: **Workers & Pages** → **Create** → **Create Worker** → name it `london-rail` → **Deploy**.
3. Click **Edit code**, delete everything, paste the whole of
   https://github.com/finncoates/london-live/blob/main/rail/worker.js (use the **Copy raw file** button), then **Deploy**.
4. Back on the worker: **Settings** → **Variables and secrets** → **Add**:
   - Type **Secret**, name `RDM_KEY`, value = your Consumer key → **Deploy**.
   - Only if Claude says so in step 1: type **Text**, name `BOARD_URL`, value = the endpoint address with `{crs}`
     where the station code goes.
5. Copy the worker's address, e.g. `https://london-rail.yourname.workers.dev`, and open
   `…/health` in your browser: it should say `"configured":true`.

## Step 3 — connect the maps (1 min)
Send Claude the worker address. Claude sets it in both apps (`RAIL_DEFAULT_RELAY` in the pages) so it works
on every device. To try it before that: on either map open the **Map** menu → **National Rail** → **Relay…**,
paste the address, OK.

## Optional — buses and trams around the country (same relay, 5 min)
The same worker also serves live vehicles outside London. Add any of these as more **Secrets** on the worker
(Settings → Variables and secrets → Add), then **Deploy**:
- `BODS_KEY` — buses with GPS positions everywhere in England. Free and instant: register at
  https://data.bus-data.dft.gov.uk (Account → API key).
- `TFGM_KEY` — Manchester Metrolink departures. Free: https://developer.tfgm.com → subscribe to the Metrolink product.
- Edinburgh buses and trams (Lothian / Edinburgh Trams), and Tallinn, Gdańsk and Vilnius, need no key: they work as soon as the relay is connected.
  (Finland, Helsinki, Norway and Boston don't need the relay at all: they already work.)
Check `…/health`: it lists which ones are switched on (`"bods":true`, `"metrolink":true`).
On the live map, turn on **Buses** and zoom into a town (Map menu → **Go to** jumps to the big cities).

## What you get
- Live map: National Rail trains moving on every operator's network (colour per operator) — in London and, wherever you
  look on the map, around the 25 nearest stations anywhere in Britain — a National Rail switch, rail stations in the station search and on TV boards (platforms, delays).
- London Journey: train legs show the expected time, delay, reason and platform; missed trains and
  delays trigger re-planning; your train is highlighted on the map.

## Notes
- Preview without a key: add `?rail=demo` to either address (made-up trains on real routes, clearly labelled).
- The relay asks for ~40 big London stations' boards every minute (cached 45 s). The public board service lists up to
  10 trains per station; the **Staff** version lists more — if RDM approves it, put its address in `BOARD_URL`.
- Test the relay code locally: `node rail/test-worker.mjs` (uses fake boards, no key needed).
- Developer notes: the map code lives in `rail/client.part.js` and is copied into both pages by
  `python3 rail/inject.py index.html journey/index.html`.
