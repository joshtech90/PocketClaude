#!/usr/bin/env bash
# PocketClaude server diagnostic dump.
#
# Run on the server (Mini-PC) as a user with sudo. Produces a single text file
# that Claude can read to assess the full state of the deployment.
#
#   curl -sSL <url-to-this-script> | bash         # remote one-shot
#   sudo bash diagnose-server.sh                  # local
#
# Output: /tmp/pocket-claude-diagnose-<timestamp>.txt
# The file is safe to share with Claude: secrets in .env, OAuth tokens and AWS
# keys are redacted — only key NAMES, file sizes/perms and mtimes are dumped.

set -u
OUT="/tmp/pocket-claude-diagnose-$(date +%Y%m%d-%H%M%S).txt"
APP_DIR="/opt/pocket-claude"
APP_USER="pocket-claude"
SERVICE="pocket-claude"

s() { printf '\n===== %s =====\n' "$1" >> "$OUT"; }
run() { printf '\n$ %s\n' "$*" >> "$OUT"; "$@" >> "$OUT" 2>&1 || echo "(exit $?)" >> "$OUT"; }
exists() { [ -e "$1" ] && echo "EXISTS  $1" || echo "MISSING $1"; }

: > "$OUT"
echo "PocketClaude server diagnostic — $(date -u +%FT%TZ)" >> "$OUT"
echo "host: $(hostname)   kernel: $(uname -r)   arch: $(uname -m)" >> "$OUT"

# Firewall/OAuth/home sections need root. Without it they emit "(exit N)" and
# the OAuth-credential probe returns a permission error — make that explicit.
if [ "$(id -u)" -ne 0 ]; then
    WARN="WARNING: not running as root — firewall/OAuth/home sections will be incomplete; re-run with sudo for a full dump."
    echo "$WARN" >> "$OUT"
    echo "$WARN" >&2
fi

s "OS / hardware"
run cat /etc/os-release
run uptime
run free -h
run df -h /
run bash -c 'lscpu | head -20'

s "systemd service: $SERVICE"
run systemctl is-enabled "$SERVICE"
run systemctl is-active "$SERVICE"
run systemctl status "$SERVICE" --no-pager -l
# the OAuth-killer settings — ProtectHome=true breaks OAuth silently
run systemctl show "$SERVICE" -p User,Group,WorkingDirectory,ExecStart,Environment,ProtectHome,ProtectSystem,PrivateTmp,Restart

s "journalctl (last 200 lines)"
run journalctl -u "$SERVICE" -n 200 --no-pager

s "journalctl (errors only, last 24h)"
run journalctl -u "$SERVICE" --since "24 hours ago" -p err --no-pager

s "App directory: $APP_DIR"
run ls -la "$APP_DIR"
exists "$APP_DIR/.env" >> "$OUT"
exists "$APP_DIR/pocket_claude" >> "$OUT"
exists "$APP_DIR/.venv" >> "$OUT"
if [ -f "$APP_DIR/.env" ]; then
    echo "" >> "$OUT"
    echo ".env keys present (values redacted):" >> "$OUT"
    grep -E '^[A-Z_]+=' "$APP_DIR/.env" 2>/dev/null | sed -E 's/=.*/=<redacted>/' >> "$OUT"
fi

s "Python venv"
if [ -x "$APP_DIR/.venv/bin/python" ]; then
    run "$APP_DIR/.venv/bin/python" --version
    run "$APP_DIR/.venv/bin/pip" list --format=columns
else
    echo "venv not found at $APP_DIR/.venv" >> "$OUT"
fi

s "Claude CLI"
run which claude
run claude --version
# bundled CLI inside the SDK (Issue #922 — sometimes needs symlinking to system claude)
BUNDLED=$(find "$APP_DIR/.venv" -path '*/claude_agent_sdk/_bundled/claude' 2>/dev/null | head -1)
if [ -n "$BUNDLED" ]; then
    echo "bundled CLI: $BUNDLED" >> "$OUT"
    run ls -la "$BUNDLED"
    run file "$BUNDLED"
fi

s "OAuth credentials (existence + perms only, no contents)"
CRED="/home/$APP_USER/.claude/.credentials.json"
if [ -e "$CRED" ]; then
    run ls -la "$CRED"
    run stat "$CRED"
else
    echo "MISSING $CRED  — OAuth login was never run, or systemd ProtectHome=true is masking it" >> "$OUT"
fi
# also check the service user can actually see it (rules out ProtectHome silent break)
if id "$APP_USER" >/dev/null 2>&1; then
    run sudo -u "$APP_USER" -- bash -c "ls -la $CRED 2>&1 | head -3"
fi

s "Network — listening ports"
run ss -tulpn
run ss -tulpn '( sport = :8787 or sport = :443 or sport = :80 )'

s "Firewall"
run ufw status verbose
run iptables -L -n -v 2>/dev/null
run nft list ruleset 2>/dev/null

s "Tailscale"
run tailscale version
run tailscale status
run tailscale ip -4
run tailscale funnel status
run tailscale serve status

s "Cloudflare tunnel (if installed)"
run which cloudflared
run cloudflared --version
run systemctl status cloudflared --no-pager -l 2>/dev/null
[ -d "/etc/cloudflared" ] && run ls -la /etc/cloudflared
[ -d "/root/.cloudflared" ] && run ls -la /root/.cloudflared
[ -d "/home/$APP_USER/.cloudflared" ] && run ls -la "/home/$APP_USER/.cloudflared"

s "nginx / reverse proxies (if installed)"
run which nginx
run nginx -v 2>&1
run systemctl status nginx --no-pager -l 2>/dev/null
[ -d "/etc/nginx/sites-enabled" ] && run ls -la /etc/nginx/sites-enabled

s "Process tree (service user)"
run ps -fu "$APP_USER" 2>/dev/null

s "Connectivity smoke-test"
run curl -sS --max-time 3 -o /dev/null -w 'HTTP %{http_code}  total %{time_total}s\n' http://127.0.0.1:8787/health
run curl -sS --max-time 3 -o /dev/null -w 'HTTP %{http_code}  total %{time_total}s\n' http://127.0.0.1:8787/

s "Disk usage of app + state dirs"
run du -sh "$APP_DIR" "$APP_DIR"/* 2>/dev/null
[ -d "/var/lib/$SERVICE" ] && run du -sh "/var/lib/$SERVICE"
[ -d "/home/$APP_USER" ] && run sudo du -sh "/home/$APP_USER"/* 2>/dev/null

s "Recent system errors (dmesg, last 50)"
run bash -c 'dmesg -T --level=err,warn 2>/dev/null | tail -50'

echo "" >> "$OUT"
echo "===== END OF DIAGNOSTIC ($(wc -l < "$OUT") lines) =====" >> "$OUT"

echo "Diagnostic written to: $OUT"
echo "Send it to Claude with: cat $OUT"
