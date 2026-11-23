#!/usr/bin/env bash
# Put settings into /etc/london-live-darwin.env without them ever appearing on a command line or in the shell history:
# reads NAME=VALUE lines from stdin (blank values are ignored), replaces or adds each one, then restarts the server.
#   used by connect.ps1; by hand:  bash setenv.sh   then type NAME=VALUE lines and Ctrl+D
set -euo pipefail
F=/etc/london-live-darwin.env
tmp=$(mktemp); sudo cat "$F" > "$tmp"
changed=0
while IFS= read -r line || [ -n "$line" ]; do
  line=${line%$'\r'}
  name=${line%%=*}; value=${line#*=}
  [[ "$name" =~ ^[A-Z_][A-Z0-9_]*$ ]] || continue
  [ -n "$value" ] || continue
  esc=${value//\\/\\\\}; esc=${esc//\"/\\\"}            # systemd EnvironmentFile: "…" with \\ and \" escapes
  grep -v "^${name}=" "$tmp" > "$tmp.new" || true; mv "$tmp.new" "$tmp"
  printf '%s="%s"\n' "$name" "$esc" >> "$tmp"
  echo "set $name"; changed=1
done
if [ "$changed" = 1 ]; then sudo install -m 600 -o root -g root "$tmp" "$F"; sudo systemctl restart london-live-darwin; echo "restarted"; fi
rm -f "$tmp"
