#!/usr/bin/env bash
# =============================================================================
#  PocketClot — Tailscale Funnel Setup (default path)
# =============================================================================
#
#  Makes PocketClot publicly reachable via a persistent URL of the form
#      https://<hostname>.<tailnet>.ts.net
#  e.g. https://my-host.my-tailnet.ts.net
#
#  Benefits:
#    - 100% free (Free plan: 50 GB public bandwidth/month — way more than
#      enough for a personal chat app)
#    - Automatic HTTPS via Let's Encrypt (managed by Tailscale)
#    - URL survives reboots, power outages, Tailscale restarts
#    - No DNS / domain setup, no port forwarding
#
#  Requirements:
#    - Tailscale is installed AND the host is part of the tailnet
#      (visible at https://login.tailscale.com/admin/machines)
#    - In the tailnet admin, MagicDNS + HTTPS are enabled:
#        https://login.tailscale.com/admin/dns
#    - Funnel capability is allowed in the ACLs for this node
#      (default for owner nodes: yes)
#
#  Usage (on the server host):
#      sudo bash /opt/pocket-claude/deploy/setup-tailscale-funnel.sh
#
#  The script is idempotent — safe to run any number of times.
# =============================================================================
set -euo pipefail

LOCAL_PORT="${LOCAL_PORT:-8787}"

c_blue()   { printf '\033[1;34m%s\033[0m\n' "$*"; }
c_green()  { printf '\033[1;32m%s\033[0m\n' "$*"; }
c_yellow() { printf '\033[1;33m%s\033[0m\n' "$*"; }
c_red()    { printf '\033[1;31m%s\033[0m\n' "$*" >&2; }
step()     { echo; c_blue "==> $*"; }

if [[ $EUID -ne 0 ]]; then
    c_red "Please run with sudo."
    exit 1
fi

# ---------------------------------------------------------------- Tailscale check
step "Checking Tailscale status"
if ! command -v tailscale >/dev/null 2>&1; then
    c_yellow "    Tailscale is not installed. Installing via the official script..."
    curl -fsSL https://tailscale.com/install.sh | sh
fi

# Backend must be "Running" — i.e. `tailscale up` has been run at least once.
if ! tailscale status --json 2>/dev/null | grep -q '"BackendState":"Running"'; then
    echo
    c_yellow "    Tailscale is not running / the host is not in the tailnet."
    c_yellow "    Starting login flow — you will get a URL to open on another"
    c_yellow "    device that is already in the tailnet."
    echo
    tailscale up --ssh
fi

# ---------------------------------------------------------------- Determine URL
# Read this node's FQDN from the tailscale status — that's the URL used
# for Funnel later. If MagicDNS is off or the tailnet has no public name
# yet, we abort with a clear hint.
step "Reading tailnet configuration"
TS_FQDN="$(tailscale status --json 2>/dev/null | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    print((d.get("Self", {}).get("DNSName", "") or "").rstrip("."))
except Exception:
    pass
' 2>/dev/null)"

if [[ -z "$TS_FQDN" ]] || [[ "$TS_FQDN" != *.ts.net ]]; then
    c_red "    No Tailscale FQDN found on this node."
    echo "    Make sure MagicDNS is enabled in the tailnet admin:"
    echo "        https://login.tailscale.com/admin/dns"
    exit 1
fi
c_green "    FQDN: $TS_FQDN"

# ---------------------------------------------------------------- HTTPS cert
step "Checking HTTPS cert provisioning"
# `tailscale cert` provisions the cert — if the tailnet feature
# "HTTPS Certificates" is not yet enabled, this fails with a clear error
# message. We do a lightweight probe run.
if ! tailscale cert --cert-file=/tmp/tspc-probe.crt --key-file=/tmp/tspc-probe.key "$TS_FQDN" >/dev/null 2>&1; then
    rm -f /tmp/tspc-probe.crt /tmp/tspc-probe.key
    c_yellow "    HTTPS cert provisioning is not (yet) enabled."
    echo
    echo "    Enable this ONCE in the Tailscale admin:"
    c_yellow "        https://login.tailscale.com/admin/dns"
    echo "        -> \"HTTPS Certificates\" -> Enable"
    echo
    read -rp "    Enabled? Press Enter to retry... " _
    if ! tailscale cert --cert-file=/tmp/tspc-probe.crt --key-file=/tmp/tspc-probe.key "$TS_FQDN" >/dev/null 2>&1; then
        c_red "    Still not working — please enable HTTPS in the admin and re-run the script."
        exit 1
    fi
fi
rm -f /tmp/tspc-probe.crt /tmp/tspc-probe.key
c_green "    HTTPS cert available."

# ---------------------------------------------------------------- Enable Funnel
step "Funnel on port 443 -> localhost:$LOCAL_PORT"
# Tailscale 1.96+ simplified the funnel/serve CLI — `funnel <target>`
# does both (serve + make public) in a single call. Idempotent — any existing
# routes are overwritten.
tailscale funnel reset 2>/dev/null || true
tailscale serve reset 2>/dev/null || true

# Point Funnel directly at the local target — no separate `serve` needed.
tailscale funnel --bg "http://localhost:$LOCAL_PORT"

# ---------------------------------------------------------------- Verification
step "Verification"
# 1. Status output from Tailscale
tailscale funnel status 2>&1 | sed 's/^/    /'

# 2. Quick test: is the PocketClot server running locally?
if curl -fsS --max-time 5 "http://localhost:$LOCAL_PORT/health" >/dev/null 2>&1; then
    c_green "    ✓ PocketClot responds on localhost:$LOCAL_PORT/health"
else
    c_yellow "    ! PocketClot does NOT respond on localhost:$LOCAL_PORT — Funnel is still active."
    c_yellow "      Check:  systemctl status pocket-claude"
fi

echo
echo "============================================================"
c_green "Tailscale Funnel is running."
echo "============================================================"
echo
echo "PocketClot is now PERMANENTLY reachable at:"
c_green "  https://$TS_FQDN"
echo
echo "This URL survives any reboot — enter it in the PocketClot app."
echo
echo "Status:       tailscale funnel status"
echo "Disable:      tailscale funnel reset"
echo "Re-enable:    tailscale funnel --bg http://localhost:$LOCAL_PORT"
echo
