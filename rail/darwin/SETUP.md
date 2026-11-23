# The London Live server (Oracle Cloud, free)

One small always-on machine runs three things the Cloudflare relay can't. Each one starts by itself once its key is in:

| Part | What you get on the map | Needs |
|---|---|---|
| **Live city feeds** (`feeds.json`) | Every bus, tram and metro live in **the Netherlands** (~2,000: Amsterdam, Rotterdam, The Hague, Utrecht…), **Rome** (~1,400), **Kraków**, **Brisbane** and **Tokyo's Toei buses** | Nothing: they start straight away |
| **Darwin** | Every National Rail train from its real running, not just the ones on station boards | Darwin Kafka details (Rail Data Marketplace) |
| **Live ferries** (AIS) | Real ship positions for every ferry and fast boat around the UK, Ireland, the Channel, North Sea, Baltic and Mediterranean (CalMac, Red Funnel, Wightlink, Stena, Irish Ferries…) | A free AISStream key |
| Ireland's live buses | Every Dublin Bus, Bus Éireann and Go-Ahead Ireland bus live | A free NTA key |
| Tokyo live trains | Tokyo Metro live | A free ODPT key (endpoint to confirm when it arrives) |

Until the machine exists the map works as before: it falls back to station boards, the timetable and the relay.

## 1. Before you start (optional, 5 minutes each, can be done any time)
- **AISStream** (live ferries): https://aisstream.io → *Sign in with GitHub* → *API Keys* → create one.
- **NTA** (Ireland's live buses): https://developer.nationaltransport.ie → sign up → subscribe to *GTFS-R* → copy the primary key.
- **ODPT** (Tokyo live trains): https://developer.odpt.org → register (approval takes a few days).
- **Darwin**: Rail Data Marketplace → subscribe to *Darwin Real Time Train Information* (the Kafka / pub-sub one) → its
  connection details: bootstrap server, username, password, topic, consumer group.

You don't need any of these to start: the city feeds run without keys, and you can add keys later by running the script
again with `-KeysOnly`.

## 2. Make the machine (about 15 minutes)
1. Sign up at https://www.oracle.com/cloud/free/ (needs a card for identity checks; the free tier isn't charged).
   Choose the home region nearest you (UK South (London)).
2. **Compute → Instances → Create instance**
   - Image: **Canonical Ubuntu 24.04**. Shape: **VM.Standard.A1.Flex** (Ampere, "Always Free") with **1 OCPU, 6 GB**.
     (If A1 says "out of capacity", try again later or pick VM.Standard.E2.1.Micro.)
   - Networking: keep *Assign a public IPv4 address*.
   - SSH keys: *Generate a key pair for me* → **Save private key** (e.g. to `C:\Users\Finn\.ssh\oracle.key`).
   - Create. Copy the **Public IP address** when it's running.
3. **Open port 80**: on the instance page → the *Subnet* link → *Default Security List* → *Add Ingress Rules*:
   Source CIDR `0.0.0.0/0`, IP protocol TCP, Destination port `80` → Add.

## 3. Connect it (one command, on this PC)
```powershell
.\rail\darwin\connect.ps1 -Ip YOUR-IP -Key C:\Users\Finn\.ssh\oracle.key
```
It installs the server, makes a secret token and gives it to the server and the Cloudflare relay, points the relay at
the machine, then asks for your keys in hidden prompts (Enter skips one). Keys go straight to the machine's settings
file (`/etc/london-live-darwin.env`), never into the code, chat or this PC. At the end it checks the server and relay.
Or tell Claude the IP and key path and it can run the parts that don't need your keys (`-NoPrompt`), then you run
`.\rail\darwin\connect.ps1 -Ip YOUR-IP -Key … -KeysOnly` to type the keys yourself.

That's it: the map switches each part on by itself (the relay's `/health` shows `"server":true`).

## Day to day
- The machine pulls new code and restarts every night (04:10). Run `connect.ps1` again to update immediately.
- Status: `http://YOUR-IP.sslip.io/health` (what's running, how many vehicles each feed has, any errors).
- Logs: `ssh -i KEY ubuntu@YOUR-IP journalctl -u london-live-darwin -f`
- Add a feed: an entry in `feeds.json` (GTFS-realtime vehicle positions + its GTFS zip); turn one off with
  `FEEDS_OFF=id1,id2` in the settings.
- Darwin's stream drops now and then; the server reconnects by itself and keeps what it knew (saved every minute).
- Test without Kafka: `DARWIN_REPLAY=messages.xml node server.mjs` (Push Port XML, one message per line). `npm test`.

## How it fits together
map → Cloudflare relay (`/darwin/trains`, `/srv/rt`, `/srv/ferries`, `/srv/health`) → `http://IP.sslip.io` (port 80 →
the server on 8080; the relay sends the secret token, so only it can ask). sslip.io gives the IP a name, because
Cloudflare Workers can't fetch a bare IP address.
