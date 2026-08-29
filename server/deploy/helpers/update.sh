#!/usr/bin/env bash
# =============================================================================
#  PocketClot — update (on the server host)
# =============================================================================
#
#  Fetches the latest version from GitHub and restarts the service.
#  Idempotent — nothing breaks if already up to date.
#
#  Usage:
#      sudo bash /opt/pocket-claude/deploy/helpers/update.sh
# =============================================================================
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/pocket-claude}"
SERVICE_USER="${SERVICE_USER:-pocket-claude}"
SERVICE_NAME="pocket-claude"

c_blue()  { printf '\033[1;34m%s\033[0m\n' "$*"; }
c_green() { printf '\033[1;32m%s\033[0m\n' "$*"; }
step()    { echo; c_blue "==> $*"; }

if [[ $EUID -ne 0 ]]; then
    echo "Please run with sudo." >&2
    exit 1
fi

step "Updating repo ($INSTALL_DIR)"
if [[ ! -d "$INSTALL_DIR/.git" ]]; then
    echo "    No git repo under $INSTALL_DIR — skipping pull (dev install via rsync?)."
else
    sudo -u "$SERVICE_USER" git -C "$INSTALL_DIR" fetch --quiet origin
    BEFORE=$(sudo -u "$SERVICE_USER" git -C "$INSTALL_DIR" rev-parse HEAD)
    sudo -u "$SERVICE_USER" git -C "$INSTALL_DIR" reset --hard origin/main
    AFTER=$(sudo -u "$SERVICE_USER" git -C "$INSTALL_DIR" rev-parse HEAD)
    if [[ "$BEFORE" == "$AFTER" ]]; then
        c_green "    Already up to date."
    else
        c_green "    Update: $BEFORE -> $AFTER"
    fi
fi

step "Updating dependencies"
sudo -u "$SERVICE_USER" "$INSTALL_DIR/.venv/bin/pip" install --quiet --upgrade -r "$INSTALL_DIR/requirements.txt"

step "Re-rendering systemd unit (in case the template changed)"
sed -e "s|@PROJECT_DIR@|$INSTALL_DIR|g" -e "s|@SERVICE_USER@|$SERVICE_USER|g" \
    "$INSTALL_DIR/deploy/systemd/pocket-claude.service" > "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload

step "Restarting service"
systemctl restart "$SERVICE_NAME"
sleep 2
if systemctl is-active --quiet "$SERVICE_NAME"; then
    c_green "    ✓ Service running."
else
    echo "    ! Service not active — logs: journalctl -u $SERVICE_NAME -n 50"
fi
