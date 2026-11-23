#!/usr/bin/env bash
# Install the London Live Darwin server on a fresh Ubuntu machine (Oracle Cloud free tier).
# Run as the default user (ubuntu):  bash install.sh
# Then put the Darwin settings in /etc/london-live-darwin.env (see SETUP.md) and: sudo systemctl restart london-live-darwin
set -euo pipefail
sudo apt-get update -y
sudo apt-get install -y git curl ca-certificates
if ! command -v node >/dev/null || [ "$(node -p 'process.versions.node.split(".")[0]')" -lt 20 ]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi
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
EOF
  sudo chmod 600 /etc/london-live-darwin.env
fi
sudo tee /etc/systemd/system/london-live-darwin.service >/dev/null <<EOF
[Unit]
Description=London Live Darwin server
After=network-online.target
Wants=network-online.target

[Service]
User=$USER
WorkingDirectory=$HOME/london-live/rail/darwin
EnvironmentFile=/etc/london-live-darwin.env
ExecStart=/usr/bin/node server.mjs
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now london-live-darwin
# open the port in Ubuntu's own firewall (Oracle images block everything but SSH by default)
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8080 -j ACCEPT && sudo netfilter-persistent save || true
echo "Installed. Check: curl http://localhost:8080/health"
