#!/usr/bin/env bash
# =============================================================================
#  Pocket Claude — clean removal from the Linux host
# =============================================================================
#
#  Stops + removes:
#    - pocket-claude.service (systemd)
#    - cloudflared.service (tunnel)
#    - /opt/pocket-claude/  (code + data — data is backed up first)
#    - pocket-claude (service user)
#
#  Usage:
#      sudo bash /opt/pocket-claude/deploy/helpers/uninstall.sh
#
#  Data is written before deletion to ~/pocket-claude-backup-<TS>.tar.gz in the
#  home of the invoking user — in case you ever want to restore.
# =============================================================================
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/pocket-claude}"
SERVICE_USER="${SERVICE_USER:-pocket-claude}"
SERVICE_NAME="pocket-claude"

c_blue()   { printf '\033[1;34m%s\033[0m\n' "$*"; }
c_green()  { printf '\033[1;32m%s\033[0m\n' "$*"; }
c_yellow() { printf '\033[1;33m%s\033[0m\n' "$*"; }
c_red()    { printf '\033[1;31m%s\033[0m\n' "$*" >&2; }

if [[ $EUID -ne 0 ]]; then
    c_red "Please run with sudo."
    exit 1
fi

echo
c_red "WARNING: This removes Pocket Claude completely from the system."
echo "What happens:"
echo "  - stop + disable systemd services"
echo "  - back up data as a tar.gz in the home of your sudo user"
echo "  - fully delete $INSTALL_DIR"
echo "  - delete user '$SERVICE_USER'"
echo
read -rp "Really? Type 'YES' to confirm: " confirm
[[ "$confirm" == "YES" ]] || { echo "Aborted."; exit 0; }

c_blue "==> Backing up data"
SUDO_USER_HOME="$(eval echo ~"${SUDO_USER:-root}")"
TS=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="$SUDO_USER_HOME/pocket-claude-backup-$TS.tar.gz"
MEMBERS=()
[[ -d "$INSTALL_DIR/data" ]] && MEMBERS+=(data)
[[ -f "$INSTALL_DIR/.env" ]] && MEMBERS+=(.env)
if [[ ${#MEMBERS[@]} -gt 0 ]]; then
    if tar -czf "$BACKUP_FILE" -C "$INSTALL_DIR" "${MEMBERS[@]}"; then
        chown "${SUDO_USER:-root}:${SUDO_USER:-root}" "$BACKUP_FILE" 2>/dev/null || true
        c_green "    Backup: $BACKUP_FILE"
    else
        c_red "    Backup FAILED — aborting before destructive removal."
        exit 1
    fi
fi

c_blue "==> Stopping services"
systemctl disable --now "$SERVICE_NAME" 2>/dev/null || true
systemctl disable --now cloudflared 2>/dev/null || true

c_blue "==> Removing systemd units"
rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload

c_blue "==> Removing code directory"
rm -rf "$INSTALL_DIR"

c_blue "==> Removing service user"
if id -u "$SERVICE_USER" >/dev/null 2>&1; then
    c_yellow "    NOTE: the Claude OAuth login in /home/$SERVICE_USER/.claude is being permanently deleted and is NOT in the backup — a fresh 'claude login' will be required on reinstall."
    userdel -r "$SERVICE_USER" 2>/dev/null || userdel "$SERVICE_USER"
fi

echo
c_green "Pocket Claude removed."
echo "Data backup: $BACKUP_FILE"
c_yellow "The cloudflared binary + ~/.cloudflared have been LEFT IN PLACE — if you want to remove them too:"
echo "    sudo apt remove cloudflared   # or dnf remove cloudflared"
echo "    sudo rm -rf /root/.cloudflared /etc/cloudflared"
