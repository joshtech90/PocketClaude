#!/usr/bin/env bash
# =============================================================================
#  Pocket Claude — Cloudflare Named Tunnel Setup
# =============================================================================
#
#  Sets up a PERSISTENT Cloudflare tunnel:
#    - Custom subdomain (e.g. pocket-claude.your-domain.com)
#    - Persistent tunnel ID + credentials in /etc/cloudflared/
#    - Runs as a systemd service -> auto-restart, auto-start on boot
#    - Survives reboot: same URL, no manual action needed
#
#  Requirements:
#    - You have a domain managed by Cloudflare (free: transfer any domain
#      there or use Cloudflare as your DNS provider).
#    - You have already run `install-linux.sh`.
#
#  If you don't have your own domain: use `setup-tailscale-funnel.sh` instead.
# =============================================================================
set -euo pipefail

TUNNEL_NAME="${TUNNEL_NAME:-pocket-claude}"
LOCAL_TARGET="${LOCAL_TARGET:-http://localhost:8787}"
CRED_DIR="/etc/cloudflared"

# ---------------------------------------------------------------- Pretty-Print
c_blue()   { printf '\033[1;34m%s\033[0m\n' "$*"; }
c_green()  { printf '\033[1;32m%s\033[0m\n' "$*"; }
c_yellow() { printf '\033[1;33m%s\033[0m\n' "$*"; }
c_red()    { printf '\033[1;31m%s\033[0m\n' "$*" >&2; }
step()     { echo; c_blue "==> $*"; }

# ---------------------------------------------------------------- Root-Check
if [[ $EUID -ne 0 ]]; then
    c_red "Please run with sudo."
    exit 1
fi

# ---------------------------------------------------------------- cloudflared
step "Installing cloudflared (if missing)"
if ! command -v cloudflared >/dev/null 2>&1; then
    if [[ -f /etc/debian_version ]]; then
        mkdir -p --mode=0755 /usr/share/keyrings
        curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg \
            | tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
        . /etc/os-release
        CODENAME="${VERSION_CODENAME:-$(lsb_release -cs 2>/dev/null)}"
        [[ -n "$CODENAME" ]] || { c_red "Could not determine Debian codename"; exit 1; }
        echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared $CODENAME main" \
            | tee /etc/apt/sources.list.d/cloudflared.list
        apt-get update -qq
        apt-get install -y cloudflared
    else
        # Fedora/RHEL — fetch binary directly
        ARCH=$(uname -m)
        case "$ARCH" in
            x86_64) BIN="cloudflared-linux-amd64" ;;
            aarch64|arm64) BIN="cloudflared-linux-arm64" ;;
            *) c_red "Unknown architecture: $ARCH"; exit 1 ;;
        esac
        curl -fsSL "https://github.com/cloudflare/cloudflared/releases/latest/download/$BIN" \
            -o /usr/local/bin/cloudflared
        chmod +x /usr/local/bin/cloudflared
    fi
    c_green "    cloudflared installed."
else
    c_green "    cloudflared already present ($(cloudflared --version 2>&1 | head -1))."
fi

# ---------------------------------------------------------------- Login
step "Cloudflare login"
# We log in as root because the later systemd service also runs as root
# and credentials are expected under /etc/cloudflared.
if [[ ! -f /root/.cloudflared/cert.pem ]]; then
    echo
    c_yellow "    The browser will ask you to grant access to a domain."
    c_yellow "    If the host has no browser: copy the printed URL, open it"
    c_yellow "    on another device, select the domain there, then return here."
    echo
    cloudflared tunnel login
else
    c_green "    Login already present ($(ls -la /root/.cloudflared/cert.pem | awk '{print $6, $7, $8}'))."
fi

# ---------------------------------------------------------------- Create tunnel
step "Create tunnel '$TUNNEL_NAME' (if missing)"
# `cloudflared tunnel list` returns tabular output. We parse column 2 (NAME).
if ! cloudflared tunnel list 2>/dev/null | awk 'NR>1 && $2==t {f=1} END{exit !f}' t="$TUNNEL_NAME"; then
    cloudflared tunnel create "$TUNNEL_NAME"
    c_green "    Tunnel created."
else
    c_green "    Tunnel already exists."
fi

TUNNEL_ID="$(cloudflared tunnel list 2>/dev/null | awk -v t="$TUNNEL_NAME" 'NR>1 && $2==t {print $1; exit}')"
if [[ -z "$TUNNEL_ID" ]]; then
    c_red "Could not determine tunnel ID."
    exit 1
fi
c_green "    Tunnel ID: $TUNNEL_ID"

# ---------------------------------------------------------------- Credentials file
step "Move credentials to $CRED_DIR (for systemd run as root)"
mkdir -p "$CRED_DIR"
# Source: ~/.cloudflared/$TUNNEL_ID.json (created by `tunnel create`)
SRC_CRED="/root/.cloudflared/$TUNNEL_ID.json"
DST_CRED="$CRED_DIR/$TUNNEL_ID.json"
if [[ -f "$SRC_CRED" && ! -f "$DST_CRED" ]]; then
    cp "$SRC_CRED" "$DST_CRED"
    chmod 600 "$DST_CRED"
fi
if [[ ! -f "$DST_CRED" ]]; then
    c_red "Credentials file $DST_CRED not found — did tunnel create fail?"
    exit 1
fi

# ---------------------------------------------------------------- Hostname prompt
step "Configure DNS record"
echo
echo "Which subdomain should the tunnel use?"
echo "(Example: pocket-claude.your-domain.com — the domain must be managed by Cloudflare.)"
read -rp "Hostname: " HOSTNAME
if [[ -z "$HOSTNAME" ]]; then
    c_red "No hostname provided."
    exit 1
fi

# ---------------------------------------------------------------- Config file
step "Writing tunnel config"
cat > "$CRED_DIR/config.yml" <<EOF
# Auto-generated by deploy/setup-cloudflare-tunnel.sh
# Editable by hand — afterwards: sudo systemctl restart cloudflared

tunnel: $TUNNEL_ID
credentials-file: $DST_CRED

# Outbound connection to Cloudflare; no port forwarding in the router required.
ingress:
  - hostname: $HOSTNAME
    service: $LOCAL_TARGET
    originRequest:
      # SSE streams (chat) need long read phases -> no aggressive timeout.
      noTLSVerify: false
      connectTimeout: 30s
      tlsTimeout: 10s
      tcpKeepAlive: 30s
      keepAliveConnections: 10
      keepAliveTimeout: 90s
  # Catch-all for everything else
  - service: http_status:404
EOF
chmod 644 "$CRED_DIR/config.yml"

# ---------------------------------------------------------------- DNS route
step "Create DNS record at Cloudflare"
# `route dns` is idempotent — no error on existing record.
cloudflared tunnel route dns "$TUNNEL_NAME" "$HOSTNAME" || \
    c_yellow "    DNS route may already exist — no error."

# ---------------------------------------------------------------- systemd service
step "Install cloudflared as a systemd service"
# `cloudflared service install` creates /etc/systemd/system/cloudflared.service
# and reads from /etc/cloudflared/config.yml.
if ! systemctl list-unit-files | grep -q '^cloudflared.service'; then
    cloudflared service install
fi
systemctl daemon-reload
systemctl enable --now cloudflared
sleep 2
if systemctl is-active --quiet cloudflared; then
    c_green "    ✓ cloudflared running."
else
    c_yellow "    cloudflared not active — logs: journalctl -u cloudflared -n 50"
fi

# ---------------------------------------------------------------- Success
echo
echo "============================================================"
c_green "Cloudflare Named Tunnel is running."
echo "============================================================"
echo
echo "Pocket Claude is now PERMANENTLY reachable at:"
c_green "  https://$HOSTNAME"
echo
echo "This URL survives any reboot — enter it in the Pocket Claude app."
echo
echo "Status:    systemctl status cloudflared"
echo "Logs:      journalctl -u cloudflared -f"
echo "Config:    $CRED_DIR/config.yml"
echo
