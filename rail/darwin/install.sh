#!/usr/bin/env bash
# Install the London Live server (Darwin trains, live ferries, live city feeds) on a fresh Oracle Cloud free-tier machine:
# Ubuntu (user ubuntu) or Oracle Linux (user opc). Safe to run again: it updates the code and keeps the settings.
# Run as the default user:  bash install.sh
# Settings: connect.ps1 (on the PC) puts them in /etc/london-live-darwin.env, or by hand: sudo nano /etc/london-live-darwin.env
set -euo pipefail
export PATH="/opt/node/bin:$PATH"
node_ok(){ command -v node >/dev/null && [ "$(node -p 'process.versions.node.split(".")[0]')" -ge 20 ]; }
# The free 1 GB machines run out of memory while installing (dnf especially): add a 2 GB swap file once,
# and stop Oracle Linux's hourly package-list refresh, which can freeze a machine this small.
if [ ! -f /swapfile ] && [ "$(free -m | awk '/Mem:/{print $2}')" -lt 2000 ]; then
  sudo dd if=/dev/zero of=/swapfile bs=1M count=2048 status=none && sudo chmod 600 /swapfile && sudo mkswap /swapfile >/dev/null && sudo swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi
sudo systemctl disable --now dnf-makecache.timer packagekit 2>/dev/null || true
node_tarball(){ # official Node.js 22 build, checksum-checked, into /opt/node (no package manager needed)
  local arch; arch=$(uname -m); case "$arch" in x86_64) arch=x64;; aarch64) arch=arm64;; esac
  local base=https://nodejs.org/dist/latest-v22.x line file
  line=$(curl -fsSL "$base/SHASUMS256.txt" | grep "linux-$arch.tar.xz$"); file=${line##* }
  curl -fsSL "$base/$file" -o "/tmp/$file"
  echo "$line" | sed "s#  #  /tmp/#" | sha256sum -c - >/dev/null
  sudo rm -rf /opt/node && sudo mkdir -p /opt/node && sudo tar -xJf "/tmp/$file" -C /opt/node --strip-components=1 && rm -f "/tmp/$file"; }
if command -v apt-get >/dev/null; then # Ubuntu / Debian
  sudo apt-get update -y
  sudo apt-get install -y git curl ca-certificates cron
  node_ok || { curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -; sudo apt-get install -y nodejs; }
else # Oracle Linux / RHEL
  node_ok || node_tarball
fi
node_ok || { echo "Couldn't install Node.js 20+"; exit 1; }
NODE=$(command -v node)
cd ~
# the code: git if the machine has it, otherwise GitHub's download (no package manager needed)
if [ -d london-live/.git ] && command -v git >/dev/null; then (cd london-live && git pull --ff-only)
elif command -v git >/dev/null && [ ! -d london-live ]; then git clone --depth 1 https://github.com/finncoates/london-live.git
else
  curl -fsSL https://codeload.github.com/finncoates/london-live/tar.gz/refs/heads/main -o /tmp/ll.tgz
  mkdir -p london-live && tar -xzf /tmp/ll.tgz -C london-live --strip-components=1 && rm -f /tmp/ll.tgz
fi
cd london-live
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
DARWIN_SASL=
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
# keep the code current: a systemd timer reruns this script every night at 04:10 (it updates and restarts)
cp -f "$HOME/london-live/rail/darwin/install.sh" "$HOME/london-live-update.sh"
sudo tee /etc/systemd/system/london-live-update.service >/dev/null <<UNIT
[Service]
Type=oneshot
User=$USER
Environment=PATH=/opt/node/bin:/usr/local/bin:/usr/bin:/bin
WorkingDirectory=$HOME
ExecStart=/bin/bash $HOME/london-live-update.sh
UNIT
sudo tee /etc/systemd/system/london-live-update.timer >/dev/null <<'UNIT'
[Timer]
OnCalendar=*-*-* 04:10
Persistent=true
[Install]
WantedBy=timers.target
UNIT
sudo systemctl daemon-reload && sudo systemctl enable --now london-live-update.timer >/dev/null
if command -v crontab >/dev/null; then ( crontab -l 2>/dev/null | grep -v london-live-update || true ) | crontab -; fi
sudo systemctl restart london-live-darwin
echo "Installed. Check: curl http://localhost:8080/health"
