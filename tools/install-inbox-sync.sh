#!/bin/bash
# tools/install-inbox-sync.sh — run once on the hub machine (internet + ssh to the island). Installs:
#   ~/.config/systemd/user/ark-inbox-sync.{service,timer}   tools/inbox-sync.py every 2 h (catch-up after sleep), quiet when the island is away
#   .git/hooks/post-commit                                  a commit that touches manifest*/ starts a sync at once
# Env for the unit: ARK_ISLAND_HOST (default pod-control-ll), ARK_INBOX, ARK_SYNC_MAX_GB; put overrides in ~/.config/ark-inbox-sync.env
set -eu; ARK=$(cd "$(dirname "$0")/.." && pwd); U=~/.config/systemd/user; mkdir -p "$U"
cat > "$U/ark-inbox-sync.service" <<S
[Unit]
Description=ark: fetch manifest rows the island lacks and push them into its inbox
After=network-online.target
[Service]
Type=oneshot
EnvironmentFile=-%h/.config/ark-inbox-sync.env
ExecStart=/usr/bin/python3 $ARK/tools/inbox-sync.py
Nice=10
IOSchedulingClass=idle
TimeoutStartSec=12h
S
cat > "$U/ark-inbox-sync.timer" <<S
[Unit]
Description=ark inbox sync every 2 hours
[Timer]
OnStartupSec=10min
OnUnitActiveSec=2h
Persistent=true
[Install]
WantedBy=timers.target
S
cat > "$ARK/.git/hooks/post-commit" <<'H'
#!/bin/sh
# installed by tools/install-inbox-sync.sh: a manifest change goes to the island without anyone asking
git diff-tree --no-commit-id --name-only -r HEAD | grep -q '^manifest' && systemctl --user start --no-block ark-inbox-sync.service 2>/dev/null
exit 0
H
chmod +x "$ARK/.git/hooks/post-commit"
systemctl --user daemon-reload && systemctl --user enable --now ark-inbox-sync.timer
echo "installed: $(systemctl --user list-timers ark-inbox-sync.timer --no-pager | sed -n 2p)"
