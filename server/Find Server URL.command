#!/usr/bin/env bash
# =============================================================================
#  Doppelklick: zeigt die Tailscale-URL des Mini-PCs an + kopiert sie in die
#  Zwischenablage. Aus der App heraus dann einfach in „Server-URL" pasten.
# =============================================================================
set -e

echo "═══════════════════════════════════════════════════"
echo " PocketClot — Server-URL ermitteln"
echo "═══════════════════════════════════════════════════"
echo

# Tailscale-CLI suchen (Mac hat sie unter /usr/local/bin oder als
# /Applications/Tailscale.app)
TS_CMD=""
if command -v tailscale >/dev/null 2>&1; then
    TS_CMD="tailscale"
elif [[ -x /Applications/Tailscale.app/Contents/MacOS/Tailscale ]]; then
    TS_CMD="/Applications/Tailscale.app/Contents/MacOS/Tailscale"
else
    echo "✗ Tailscale ist nicht auf diesem Mac installiert."
    echo "  Lade es runter von https://tailscale.com/download — danach erneut versuchen."
    read -rp "Drücke Enter zum Schließen…" _
    exit 1
fi

# Tailnet-Topologie auslesen und alle aktiven Linux-Knoten anzeigen
LINUX_HOSTS=$("$TS_CMD" status --json 2>/dev/null | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    for p in (d.get("Peer") or {}).values():
        os_str = (p.get("OS","") or "").lower()
        dns = (p.get("DNSName","") or "").rstrip(".")
        host = p.get("HostName","")
        online = p.get("Online", False)
        if os_str in ("linux","openbsd","freebsd") and dns:
            mark = "ONLINE " if online else "offline"
            print(f"{mark}\t{host}\t{dns}")
except Exception:
    pass
')

if [[ -z "$LINUX_HOSTS" ]]; then
    echo "✗ Keine Linux-Knoten im Tailnet gefunden."
    echo "  Stelle sicher, dass der Mini-PC im Tailnet eingetragen ist:"
    echo "  https://login.tailscale.com/admin/machines"
    read -rp "Drücke Enter zum Schließen…" _
    exit 1
fi

echo "Linux-Knoten in Deinem Tailnet:"
echo
printf '%s\n' "$LINUX_HOSTS" | awk -F'\t' '{printf "  %d) [%s] %-25s https://%s\n", NR, $1, $2, $3}'
echo

# Default: erster Online-Host (oder einfach der erste)
DEFAULT_URL=$(printf '%s\n' "$LINUX_HOSTS" | awk -F'\t' '$1=="ONLINE" {print "https://" $3; exit}')
[[ -z "$DEFAULT_URL" ]] && DEFAULT_URL=$(printf '%s\n' "$LINUX_HOSTS" | head -1 | awk -F'\t' '{print "https://" $3}')

read -rp "URL des Pocket-Claude-Servers (default: $DEFAULT_URL): " URL
URL="${URL:-$DEFAULT_URL}"

# In Zwischenablage kopieren
echo -n "$URL" | pbcopy
echo
echo "✓ URL in Zwischenablage:"
echo "    $URL"
echo
echo "In der App: Einstellungen → Profil hinzufügen → Server-URL = paste"
echo
read -rp "Drücke Enter zum Schließen…" _
