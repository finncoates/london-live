#!/usr/bin/env bash
# Install the London Live server (Darwin trains, live ferries, live city feeds) on a fresh Oracle Cloud free-tier machine:
# Ubuntu (user ubuntu) or Oracle Linux (user opc). Safe to run again: it updates the code and keeps the settings.
# Run as the default user:  bash install.sh
# Settings: connect.ps1 (on the PC) puts them in /etc/london-live-darwin.env, or by hand: sudo nano /etc/london-live-darwin.env
set -euo pipefail
node_ok(){ command -v node >/dev/null && [ "$(node -p 'process.versions.node.split(".")[0]')" -ge 20 ]; }
if command -v apt-get >/dev/null; then # Ubuntu / Debian
  sudo apt-get update -y
  sudo apt-get install -y git curl ca-certificates cron
  node_ok || { curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -; sudo apt-get install -y nodejs; }
else # Oracle Linux / RHEL
  sudo dnf install -y git curl ca-certificates cronie
  sudo systemctl enable --now crond
  node_ok || { sudo dnf module reset -y nodejs && sudo dnf module enable -y nodejs:22 && sudo dnf install -y nodejs npm; } || true
  node_ok || { curl -fsSL https://rpm.nodesource.com/setup_22.x | sudo bash -; sudo dnf install -y nodejs; }
fi
node_ok || { echo "Couldn't install Node.js 20+"; exit 1; }
NODE=$(command -v node)
cd ~
[ -d london-live ] || git clone --depth 1 https://github.com/finncoates/london-live.git
cd london-live && git pull --ff-only
cd rail/darwin && npm ci --omit=dev
# settings file (secrets), readable only by root and the service
if [ ! -f /etc/london-live-darwin.env ]; then
  sudo tee /etc/london-live-darwin.env >/dev/null <<'EOF'
# From the Rail Data Marketplace → Darwin Real Time Train Information → Specification / credentials
DARWIN_BOOTSTRAP=
DARWIN_USERNAME=
DARWIN_PASSWORD=
DARWIN_TOPIC=
DARWIN_GROUP=
# A long random secret; the same value goes on the relay as RELAY_TOKEN
RELAY_TOKEN=
PORT=8080
# Live ferries: a free key from https://aisstream.io (sign in with GitHub → API Keys)
AISSTREAM_KEY=
# Ireland's live buses: a free key from https://developer.nationaltransport.ie
NTA_KEY=
# Tokyo's live trains: a free key from https://developer.odpt.org
ODPT_KEY=
EOF
  sudo chmod 600 /etc/london-live-darwin.env
fi
sudo tee /etc/systemd/system/london-live-darwin.service >/dev/null <<EOF
[Unit]
Description=London Live server (Darwin, ferries, live feeds)
After=network-online.target
Wants=network-online.target

[Service]
User=$USER
WorkingDirectory=$HOME/london-live/rail/darwin
EnvironmentFile=/etc/london-live-darwin.env
ExecStart=$NODE server.mjs
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now london-live-darwin
# open port 80 (the relay calls http://IP.sslip.io, port 80, which goes to the server on 8080) in the machine's own firewall:
# Oracle's images block everything but SSH by default. (Oracle's Security List needs port 80 open too: see SETUP.md.)
if command -v firewall-cmd >/dev/null && sudo firewall-cmd --state >/dev/null 2>&1; then # Oracle Linux: firewalld
  sudo firewall-cmd --permanent --add-port=80/tcp --add-port=8080/tcp >/dev/null
  sudo firewall-cmd --permanent --query-forward-port=port=80:proto=tcp:toport=8080 >/dev/null 2>&1 || sudo firewall-cmd --permanent --add-forward-port=port=80:proto=tcp:toport=8080 >/dev/null
  sudo firewall-cmd --reload >/dev/null
else # Ubuntu: iptables
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y iptables-persistent >/dev/null 2>&1 || true
  for port in 80 8080; do sudo iptables -C INPUT -p tcp --dport $port -j ACCEPT 2>/dev/null || sudo iptables -I INPUT 5 -p tcp --dport $port -j ACCEPT; done
  sudo iptables -t nat -C PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8080 2>/dev/null || sudo iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8080
  sudo netfilter-persistent save >/dev/null 2>&1 || true
fi
# keep the code current: pull and restart every night at 04:10
( crontab -l 2>/dev/null | grep -v london-live-update; echo "10 4 * * * cd $HOME/london-live && git pull --ff-only -q && cd rail/darwin && npm ci --omit=dev --silent && sudo systemctl restart london-live-darwin # london-live-update" ) | crontab -
sudo systemctl restart london-live-darwin
echo "Installed. Check: curl http://localhost:8080/health"
