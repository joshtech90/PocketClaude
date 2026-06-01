#!/usr/bin/env bash
# =============================================================================
#  Pocket Claude — migration from a source host to the target server
# =============================================================================
#
#  What gets transferred:
#      - data/pocket_claude.db          (SQLite with all chats + users + sessions)
#      - data/uploads/                  (attachments)
#      - data/google_tts_credentials.json (Cloud TTS service account, if present)
#      - .env                            (server token + model setting)
#
#  What does NOT get transferred:
#      - ~/.claude/credentials.json (claude CLI login) — must be redone on the
#        target host (`claude login` as the pocket-claude user).
#        Reason: claude CLI sessions are often bound to device fingerprints.
#      - Cloudflare tunnel credentials — these are created via
#        setup-cloudflare-tunnel.sh on the target. (Bonus: source and target can
#        both have their own tunnels, enabling failover.)
#
#  Usage from the source host (in the source repo root):
#      ./deploy/migrate-to-server.sh your-user@minipc.local
#  or with an explicit target path:
#      ./deploy/migrate-to-server.sh your-user@10.0.0.42:/opt/pocket-claude
#
#  Requirements:
#      - `install-linux.sh` has already been run on the target (= /opt/pocket-claude
#        exists, service user `pocket-claude` exists, the service is enabled).
#      - SSH access works (`ssh user@host` lets you in).
# =============================================================================
set -euo pipefail

c_blue()   { printf '\033[1;34m%s\033[0m\n' "$*"; }
c_green()  { printf '\033[1;32m%s\033[0m\n' "$*"; }
c_yellow() { printf '\033[1;33m%s\033[0m\n' "$*"; }
c_red()    { printf '\033[1;31m%s\033[0m\n' "$*" >&2; }
step()     { echo; c_blue "==> $*"; }

TARGET=""
if [[ $# -ge 1 ]]; then
    TARGET="$1"
fi

# If no target is given: try to find one via Tailscale.
# We list all Linux nodes from `tailscale status` for selection.
if [[ -z "$TARGET" ]] && command -v tailscale >/dev/null 2>&1; then
    echo "No SSH target given — looking in the tailnet..."
    TS_CANDIDATES="$(tailscale status --json 2>/dev/null | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    for p in (d.get("Peer") or {}).values():
        if p.get("OS","").lower() in ("linux","unknown"):
            dns = (p.get("DNSName","") or "").rstrip(".")
            host = p.get("HostName","")
            if dns and "Online" in str(p.get("Online", "")) or p.get("Online", False):
                print(f"{host}\t{dns}")
except Exception:
    pass
' 2>/dev/null)"
    if [[ -n "$TS_CANDIDATES" ]]; then
        echo
        echo "Tailnet nodes:"
        echo "$TS_CANDIDATES" | awk -F'\t' '{printf "    %d) %s  (%s)\n", NR, $1, $2}'
        echo
        read -rp "SSH user (default: current user '$USER'): " SSH_USER
        SSH_USER="${SSH_USER:-$USER}"
        # Default: first match
        DEFAULT_HOST="$(echo "$TS_CANDIDATES" | head -1 | awk -F'\t' '{print $2}')"
        read -rp "SSH target host (default: $DEFAULT_HOST): " SSH_HOST
        SSH_HOST="${SSH_HOST:-$DEFAULT_HOST}"
        TARGET="$SSH_USER@$SSH_HOST"
    fi
fi

if [[ -z "$TARGET" ]]; then
    c_red "Usage: $0 <user@host[:remote-path]>"
    echo
    echo "Examples:"
    echo "  $0 your-user@minipc"
    echo "  $0 your-user@minipc.tailnet-name.ts.net"
    echo "  $0 your-user@10.0.0.42:/opt/pocket-claude"
    exit 1
fi
REMOTE_PATH="/opt/pocket-claude"
if [[ "$TARGET" == *":"* ]]; then
    REMOTE_PATH="${TARGET#*:}"
    TARGET="${TARGET%%:*}"
fi

LOCAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="$LOCAL_DIR/data"
ENV_FILE="$LOCAL_DIR/.env"

if [[ ! -d "$DATA_DIR" ]]; then
    c_red "data/ not found in $LOCAL_DIR — are you in the correct repo?"
    exit 1
fi

# ---------------------------------------------------------------- Pre-flight
step "Pre-flight check: SSH to target ($TARGET)"
if ! ssh -o BatchMode=yes -o ConnectTimeout=10 "$TARGET" 'echo OK' >/dev/null 2>&1; then
    c_red "    SSH access failed."
    echo "    Tip: test 'ssh $TARGET' manually. If needed, copy an SSH key with:"
    echo "        ssh-copy-id $TARGET"
    exit 1
fi
c_green "    SSH OK."

step "Pre-flight: is Pocket Claude installed on the target?"
if ! ssh "$TARGET" "test -d $REMOTE_PATH" 2>/dev/null; then
    c_red "    $REMOTE_PATH does not exist on the target."
    echo "    Run on the target first:"
    echo "        sudo bash $REMOTE_PATH/deploy/install-linux.sh"
    echo "    (or place the install-linux.sh script somewhere else and run it)"
    exit 1
fi
c_green "    Installation found."

# ---------------------------------------------------------------- Stop source server?
LOCAL_RUNNING=false
if pgrep -f "python.*pocket_claude" >/dev/null 2>&1 || \
   pgrep -f "pocket_claude_manager" >/dev/null 2>&1; then
    LOCAL_RUNNING=true
    echo
    c_yellow "A Pocket Claude process is still running on this host."
    echo "Recommendation: stop the local server before migrating so the SQLite DB"
    echo "is in a clean state (no open write transaction)."
    echo
    read -rp "Stop the local server now? [Y/n] " yn
    if [[ ! "$yn" =~ ^[Nn]$ ]]; then
        pkill -f "python.*pocket_claude" 2>/dev/null || true
        pkill -f "pocket_claude_manager" 2>/dev/null || true
        sleep 1
        c_green "    Server stopped."
    fi
fi

# ---------------------------------------------------------------- Create bundle
step "Create data bundle"
TMP_BUNDLE="$(mktemp /tmp/pocket-claude-migrate-XXXXXX.tar.gz)"
trap "rm -f '$TMP_BUNDLE'" EXIT

INCLUDE=()
[[ -f "$DATA_DIR/pocket_claude.db" ]] && INCLUDE+=("data/pocket_claude.db")
[[ -d "$DATA_DIR/uploads" ]] && INCLUDE+=("data/uploads")
[[ -f "$DATA_DIR/google_tts_credentials.json" ]] && INCLUDE+=("data/google_tts_credentials.json")
[[ -f "$ENV_FILE" ]] && INCLUDE+=(".env")

if [[ ${#INCLUDE[@]} -eq 0 ]]; then
    c_red "    Nothing to migrate — data/ is empty and no .env present."
    exit 1
fi

# `tar -C` keeps the paths relative; symlink dereferencing not needed
# (everything is a real file). gzip-9 since it only runs once.
tar -czf "$TMP_BUNDLE" -C "$LOCAL_DIR" "${INCLUDE[@]}" || { c_red "    Bundle creation failed."; exit 1; }
BUNDLE_SIZE=$(du -h "$TMP_BUNDLE" | awk '{print $1}')
c_green "    Bundle: $BUNDLE_SIZE — ${#INCLUDE[@]} paths"
for p in "${INCLUDE[@]}"; do echo "        - $p"; done

# ---------------------------------------------------------------- Upload
step "Upload via scp"
REMOTE_TMP="/tmp/pocket-claude-migrate.tar.gz"
scp -q "$TMP_BUNDLE" "$TARGET:$REMOTE_TMP"
c_green "    Bundle on target host: $REMOTE_TMP"

# ---------------------------------------------------------------- Target ops
step "On the target: backup, extract, ownership, restart"

# We handle this all in a single remote bash block — more atomic.
# We need `sudo` because /opt/pocket-claude is owned by pocket-claude:pocket-claude.
ssh "$TARGET" bash <<REMOTE_EOF
set -euo pipefail
REMOTE_PATH='$REMOTE_PATH'
REMOTE_TMP='$REMOTE_TMP'
SERVICE_NAME='pocket-claude'

# 1. Stop the service so the DB isn't overwritten in flight
if sudo systemctl is-active --quiet "\$SERVICE_NAME"; then
    echo "    -> stopping systemd service"
    sudo systemctl stop "\$SERVICE_NAME"
fi

# 2. Backup of the current state (if present)
TS=\$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="\$REMOTE_PATH/data/.pre-migration-backup-\$TS"
if [[ -f "\$REMOTE_PATH/data/pocket_claude.db" ]]; then
    echo "    -> backing up existing data to \$BACKUP_DIR"
    sudo mkdir -p "\$BACKUP_DIR"
    sudo cp -a "\$REMOTE_PATH/data/pocket_claude.db" "\$BACKUP_DIR/" 2>/dev/null || true
    [[ -d "\$REMOTE_PATH/data/uploads" ]] && \\
        sudo cp -a "\$REMOTE_PATH/data/uploads" "\$BACKUP_DIR/" 2>/dev/null || true
    [[ -f "\$REMOTE_PATH/.env" ]] && \\
        sudo cp -a "\$REMOTE_PATH/.env" "\$BACKUP_DIR/" 2>/dev/null || true
fi

# 3. Extract the bundle
echo "    -> extracting into \$REMOTE_PATH"
sudo tar -xzf "\$REMOTE_TMP" -C "\$REMOTE_PATH"
sudo chown -R pocket-claude:pocket-claude "\$REMOTE_PATH/data" "\$REMOTE_PATH/.env" 2>/dev/null || true
sudo chmod 600 "\$REMOTE_PATH/.env" 2>/dev/null || true
[[ -f "\$REMOTE_PATH/data/google_tts_credentials.json" ]] && \\
    sudo chmod 600 "\$REMOTE_PATH/data/google_tts_credentials.json"

# 4. Clean up the bundle
rm -f "\$REMOTE_TMP"

# 5. Start the service again
echo "    -> starting systemd service"
sudo systemctl start "\$SERVICE_NAME"
sleep 2
if sudo systemctl is-active --quiet "\$SERVICE_NAME"; then
    echo "    ✓ Service running."
else
    echo "    ! Service not active — check logs on the target:"
    echo "         journalctl -u \$SERVICE_NAME -n 50"
fi
REMOTE_EOF

echo
echo "============================================================"
c_green "Migration complete."
echo "============================================================"
echo
echo "Pocket Claude is now running on the target host with your data."
echo
echo "Verify:"
echo "  ssh $TARGET 'sudo systemctl status pocket-claude'"
echo "  ssh $TARGET 'journalctl -u pocket-claude -n 30'"
echo
echo "Reminder: for the first start on the target you MAY still need:"
echo "  1. claude CLI login (if not yet done):"
echo "       ssh $TARGET 'sudo -u pocket-claude -H claude login'"
echo "  2. Set up a tunnel (if not yet done):"
echo "       ssh $TARGET 'sudo bash $REMOTE_PATH/deploy/setup-cloudflare-tunnel.sh'"
echo
c_yellow "Note: the local server is stopped (if you answered Y above). You can now"
c_yellow "disable or fully uninstall it — the target host takes over the hosting"
c_yellow "role. App side: update the server URL in the profile settings to the new"
c_yellow "tunnel URL."
