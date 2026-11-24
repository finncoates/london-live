# What's on the map: UK (and beyond)

Checked 23 Nov 2026 on the live site and locally, city by city. **Live** = real positions or live predictions.
**Timetable** = placed where the timetable says it should be now (no live report). Every vehicle sits on its line.

## UK at a glance

| Transport | Where | How it's shown | Source |
|---|---|---|---|
| Tube, DLR, Overground, Elizabeth line, trams, cable car, river buses | London | **Live** (from TfL arrival predictions) | TfL, shared through the relay |
| London buses | London | **Live** (from predictions), up to 30 routes around you at street zoom | TfL |
| Buses | England | **Live GPS** | Bus Open Data Service (BODS) |
| Buses | Scotland, Wales, Northern Ireland | **Live GPS** (where operators share) | bustimes.org |
| Coaches | GB | **Live GPS** (National Express, FlixBus, Citylink…) | BODS / bustimes.org |
| National Rail | GB | **Live** where a nearby station board lists the train; **every other train from the timetable** | National Rail boards (RDM) + Transitous |
| NI Railways | Northern Ireland | **Timetable** | Transitous |
| Eurostar | Both ways: St Pancras ⇄ Paris, Brussels, Lille, Amsterdam | **Live** when on the St Pancras board, otherwise **timetable**, along HS1 and the Channel Tunnel | National Rail boards + Transitous |
| Trams/metros | Edinburgh | **Live GPS** | Transport for Edinburgh |
| Trams/metros | Manchester, Sheffield, Birmingham, Blackpool, Tyne & Wear Metro, Glasgow Subway | **Timetable** | Operators' published timetables (baked into the app) |
| Ferries | Every timetabled UK ferry (CalMac, Red Funnel, Wightlink, Hovertravel, Orkney, Gosport, Brittany Ferries…) | **Timetable**, on the sea route | Transitous |
| Mersey Ferries | Liverpool | **Timetable** | baked timetable |
| Bikes and scooters | London (+ where shared) | **Live** docks/vehicles | TfL / GBFS |

Checked city by city: London, Manchester, Birmingham, Leeds, Liverpool, Newcastle, Sheffield, Nottingham, Bristol,
Cardiff, Swansea, Edinburgh, Glasgow, Aberdeen, Inverness, Belfast, Blackpool, Southampton, Brighton, Norwich,
Plymouth, Oxford, Cambridge, York, Isle of Wight.

## What isn't visible (or isn't live), why, and how it could be

| Missing | Why | How to get it | Effort / cost |
|---|---|---|---|
| **Exact live position of every National Rail train** | The public departure boards only list trains from the station on; the rest are shown from the timetable | **Darwin**: the server is **built and tested** (
ail/darwin, see its SETUP.md); the relay and map already switch to it when it's connected. It needs the always-on machine (Oracle free tier). The Darwin key goes on that server, not the relay | Free. You: create the Oracle account (needs a card for verification), then ~15 min to install |
| **Nottingham trams (NET)** | NET publishes no open timetable or live feed (not in Bus Open Data, not in Transitous). Lines are drawn, no trams | Ask NET (Transdev) for their GTFS timetable, or register for Traveline's TNDS dataset and check whether it includes NET | Free; an email/registration by you |
| **Manchester Metrolink live** | Shown from the timetable (every tram, on its line) | TfGM's developer portal has stopped issuing new live keys, so there's no free route today. If it reopens, add the key as `TFGM_KEY` on the relay (already supported) | Waiting on TfGM |
| **First Bus in Glasgow and Aberdeen** | First doesn't share live positions in Scotland (England's are in BODS by law; Scotland has no such rule) | Nothing open; only First's own app. The routes are drawn | — |
| **Live trams/metros elsewhere** (Sheffield, Birmingham, Blackpool, Tyne & Wear, Glasgow Subway) | No public live feed (Tyne & Wear has an unofficial one) | Timetable for now; Nexus (Tyne & Wear) could be added from its unofficial API | Small |
| **Live ferries** | Ferries are shown from the timetable | Ship positions (AIS) through aisstream.io (free key) on the same Oracle server | Free; needs the server |
| **Heritage railways, cliff railways, airport shuttles** | Not in open timetables | Mostly no data | — |
| **London buses away from you** | By design: only routes near you at street zoom (thousands of buses would slow phones) | — | — |

## Beyond the UK (new)

Anywhere without its own feed now shows the trains, trams, metros and ferries running (buses close up) from
**Transitous** open timetables, with their routes drawn as lines. Checked: **Ireland** (Dublin: Irish Rail + Luas),
**France** (Lyon: TGV, OUIGO, metro, trams; rural France: TGV/TER). Dense Paris is very heavy: it works with small
map tiles but the first view can be slow or miss some vehicles.
Live already (own feeds): Finland/Helsinki, Norway, Berlin, Boston, Tallinn, Gdańsk, Vilnius.
**Ready for the Oracle machine** (rail/darwin/SETUP.md; one command, `connect.ps1`): besides Darwin, the server reads big live feeds the relay can't: every bus, tram and metro live in **the Netherlands**, **Rome**, **Kraków**, **Brisbane** and **Tokyo's Toei buses** (no keys; tested), plus **live ferries by AIS** (free AISStream key), **Ireland's live buses** (free NTA key) and **Tokyo Metro** (free ODPT key). The map hides a city's timetable vehicles only where its live feed has that kind (Amsterdam's metro stays from the timetable; Rotterdam's goes live).

**Whole countries** (Explore → a country → *Whole country (trains)*): zoomed out, every high-speed and intercity train in the country; one step in, every regional train too; at city zoom, metros, trams, ferries and buses as before. All from the timetable (Transitous), refreshed every minute. Countries: Ireland (with Northern Ireland), France, Spain, Germany, Poland, Italy, Switzerland, Austria, the Netherlands, Belgium, Denmark, Sweden, Czechia, Portugal and Japan (Finland's is live GPS).

**Gaps in the open timetables** (nothing the app can do until the operator publishes one): Metro de Madrid; the subways in Osaka, Kyoto, Sapporo and Fukuoka (Tokyo's are there). South Korea, Australia and New Zealand have too little in Transitous for a country view yet.

**Explore menu**: Europe (UK, Ireland, France, Spain), North America (Toronto) and **Asia — Japan** (Tokyo, Osaka, Kyoto, Sapporo, Fukuoka). Japan is timetable-only (Transitous) for now. Live Tokyo trains (Tokyo Metro, Toei, some JR East) come from ODPT (developer.odpt.org): free sign-up, approved in a few days; add the key as `ODPT_KEY` on the relay once you have it.

**New live feeds**: **Spain** — Renfe's trains live (~430: Cercanías/Rodalies in Madrid, Barcelona, Seville…; AVE/long distance from the timetable); **Rennes** — every STAR bus live; **Toronto** — TTC streetcars and buses live (~1,150; subway from the timetable).
Other cities checked and not possible without a key: Paris (RATP/IDFM: free PRIM key), Ireland's buses (NTA: free key), Netherlands (live positions open, but no route names without a 200 MB timetable), Brussels, Switzerland, Prague, Warsaw (keys).

## Whole countries drawn like London (overnight 23–24 November)

| Country | Lines and stations | Buses | Live | Departures |
|---|---|---|---|---|
| **France** | Every metro, tram, local train, funicular, cable car and city ferry in each city's official colours (Paris IDFM, Lyon, Marseille, Toulouse, Lille, Rennes, Bordeaux, Nice, Nantes, Strasbourg, Montpellier, Grenoble, Rouen, Brest, Angers, Tours, Dijon, Clermont-Ferrand, Caen, Le Havre, Reims, Orléans, Mulhouse, Besançon, Avignon, Valenciennes, Toulon…); the whole SNCF passenger railway (24,900 km, 2,950 stations) and Corsica's | Every urban and intercity network in transport.data.gouv.fr's catalogue (≈400), routes matched onto the roads where the published shapes are missing or straight; bus stops close up | 137 networks' GTFS-realtime on the London Live server (Lyon, Bordeaux, Rennes, Brest, Rouen, Montpellier, Nice, Dijon…); elsewhere from the timetable | Every station and stop (Transitous, live where shared) |
| **Netherlands** | Amsterdam (GVB metro 50–54, trams, ferries), Rotterdam (RET metro A–E, trams, Waterbus), The Hague (HTM, RandstadRail), Utrecht; the whole railway (467 stations) | Every operator (Qbuzz, Arriva, Connexxion, RRReis, Bravo, Transdev, EBS…) | Everything (OVapi) | Transitous |
| **Belgium** | Brussels (STIB metro and trams), Antwerp, Ghent and the Coast Tram (De Lijn), Charleroi (TEC); the railway from OpenStreetMap, 635 SNCB stations named in their own language | STIB, De Lijn, TEC | From the timetable (no open live positions) | Transitous |
| **Luxembourg** | Luxtram and Luxembourg City's buses; CFL's railway and stations | Every RGTR and TICE regional bus | From the timetable | Transitous |
| **Ireland** | Dublin (Luas Red and Green, DART), Irish Rail's whole network | Dublin Bus, Go-Ahead, Bus Éireann, Local Link and every other operator | Luas and DART from the timetable; live buses need a free NTA key | Transitous |
| **Denmark** | Copenhagen (Metro M1–M4 including the M3 ring, S-tog), Aarhus and Odense light rail; DSB's railway | Every bus in east and west Denmark | From the timetable | Transitous |
| **Lithuania** | Vilnius and Kaunas; LTG Link's railway | Every city bus and trolleybus and every regional bus (visimarsrutai.lt) | From the timetable | Transitous |
| **Estonia** | Tallinn (live trams and buses), Tartu, Pärnu; Elron's railway; the island ferries | Every county and city bus (22 networks) | Tallinn live by GPS; elsewhere from the timetable | Transitous |
| **Latvia** | Riga (trams), Daugavpils (trams), Liepāja (tram), Jelgava, Jūrmala, Ventspils, Rēzekne, Jēkabpils; Vivi's railway (147 stations) | Every city bus and trolleybus and every regional and intercity bus (pieturas.lv's national timetable) | From the timetable | Transitous |
| **Portugal** | Lisbon (Metro, Carris trams, funiculars and Santa Justa lift, Tagus ferries, Metro Sul do Tejo), Porto (Metro), Coimbra (Metro Mondego busway); the railway from OpenStreetMap, 457 CP stations | Carris, Carris Metropolitana, STCP, TCB, MobiCascais, TUB (Braga), SMTUC (Coimbra), the Algarve (Vamus and town buses), Madeira (Horários do Funchal, SIGA) | From the timetable | Transitous |
| **Slovenia** | SŽ's railway from OpenStreetMap | LPP (Ljubljana), Marprom (Maribor), Celje, Kranj, Koper, Novo mesto, Velenje, Ptuj, Murska Sobota, Nova Gorica, Postojna, Sevnica, Brežice, Jesenice; every intercity bus (Nomago, Arriva, AP Murska Sobota) | From the timetable | Transitous |

Also: bikes and scooters for hire in 86 French towns (Vélib', Vélo'v, V³, Lime, Voi, Dott, Pony…); FlixBus and
BlaBlaCar coaches in their own colours; tapping a timetable vehicle shows where it's really going.
**Gaps**: Portugal's regional buses outside Lisbon, Porto, Braga, Coimbra, the Algarve and Madeira publish no open timetable
(Rede Expressos, Transdev, Rodonorte…), so only FlixBus is shown between cities there. Amsterdam's and Le Havre's trams have no official colours in the open data (drawn in one tram green);
Paris has no open live positions (IDFM's need a free PRIM key); Lille and Strasbourg publish live data only as SIRI.

## Before a big public launch
- **Transitous** (journey planning, timetable vehicles): free, community-run; tell them before heavy use
  (they ask to be contacted above ~720 plans a day), or host your own copy on the server.
- **Photon** (place search): fair use; can be self-hosted.
- **Esri** satellite photos: get a free ArcGIS key.
- Credits on screen: "Powered by TfL Open Data", National Rail Enquiries, OpenStreetMap, Transitous.
