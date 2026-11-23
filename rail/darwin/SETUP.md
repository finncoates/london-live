# Darwin server: every National Rail train from its real running

What it does: reads National Rail's **Darwin Push Port** (every train's actual and expected times at every station
and junction, live) and gives the map every train in view. The relay fetches from it, so the map needs no changes.
Without it, the map uses departure boards plus the timetable (see COVERAGE.md).

It's built and tested (`npm test`; an end-to-end test placed trains correctly on the map). It needs a small
always-on machine because Darwin is a constant stream. **Oracle Cloud's free tier** runs it for £0.

## 1. You (about 20 minutes, at home)
1. Sign up at https://www.oracle.com/cloud/free/ (needs a card for identity checks; the free tier isn't charged).
   Choose the home region nearest you (e.g. UK South, London).
2. **Create a VM**: Compute → Instances → Create.
   - Image: **Ubuntu 24.04**. Shape: **VM.Standard.A1.Flex** (Ampere, free) with 1 OCPU / 6 GB, or VM.Standard.E2.1.Micro.
   - Networking: keep "assign a public IPv4 address". Add your SSH public key (or let it make one and download it).
3. **Open port 8080**: Networking → your VCN → Security List → Add Ingress Rule: source `0.0.0.0/0`, TCP, port `8080`.
   (Only the relay calls it, and the server also checks a secret token.)
4. Tell Claude the VM's public IP address. Claude can then do the rest over SSH if you allow it, or you can run:

## 2. Install (Claude or you)
```
ssh ubuntu@YOUR-IP
curl -fsSLO https://raw.githubusercontent.com/finncoates/london-live/main/rail/darwin/install.sh && bash install.sh
sudo nano /etc/london-live-darwin.env    # fill in the Darwin settings below
sudo systemctl restart london-live-darwin
curl http://localhost:8080/health        # "messages" should start counting up
```

## 3. Darwin settings (from the Rail Data Marketplace)
Subscriptions → **Darwin Real Time Train Information** (the Kafka / pub-sub one) → its connection details:
`DARWIN_BOOTSTRAP` (bootstrap server, host:port), `DARWIN_USERNAME`, `DARWIN_PASSWORD`, `DARWIN_TOPIC`,
`DARWIN_GROUP` (consumer group id). Put them in `/etc/london-live-darwin.env` on the server — never in the code or chat.
Make up a long random `RELAY_TOKEN` too.

## 4. Connect the relay (Cloudflare → london-rail → Settings → Variables and secrets)
- `DARWIN_URL` (Text): `http://YOUR-IP:8080`
- `RELAY_TOKEN` (Secret): the same token as on the server
Deploy. The relay's `/health` then shows `"darwin":true` and the map switches to Darwin by itself (falling back to the
boards if the server is down).

## Notes
- Darwin's stream drops now and then; the server reconnects by itself and keeps what it knew (saved every minute).
- Trains appear as their Darwin updates arrive (within minutes of the server starting).
- Test without Kafka: `DARWIN_REPLAY=messages.xml node server.mjs` (Push Port XML, one message per line).
