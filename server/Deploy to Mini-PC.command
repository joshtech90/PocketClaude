#!/usr/bin/env bash
# =============================================================================
#  Doppelklick-Helfer: Migration vom Mac auf den Mini-PC
# =============================================================================
#
#  Wenn Du das hier doppelklickst, fragt der Mac nach dem SSH-Ziel und ruft
#  dann deploy/migrate-to-server.sh auf. Soll für den Nicht-CLI-User die
#  Migration zum One-Click-Erlebnis machen.
#
#  Vor dem ersten Lauf: auf dem Mini-PC einmal install-linux.sh ausführen.
# =============================================================================
set -e

cd "$(dirname "$0")"

echo "═══════════════════════════════════════════════════"
echo " PocketClot — Migration vom Mac auf den Mini-PC"
echo "═══════════════════════════════════════════════════"
echo
echo "Voraussetzungen:"
echo "  · Auf dem Mini-PC: install-linux.sh wurde schon ausgeführt"
echo "  · Du hast SSH-Zugang (ssh-copy-id einmal gemacht)"
echo
read -rp "SSH-Ziel (z.B. joscha@mini-pc.local oder ubuntu@10.0.0.42): " TARGET

if [[ -z "$TARGET" ]]; then
    echo "Kein Ziel angegeben — abgebrochen."
    read -rp "Drücke Enter zum Schließen…" _
    exit 1
fi

bash ./deploy/migrate-to-server.sh "$TARGET"

echo
echo "Fenster offen lassen oder schließen — fertig."
read -rp "Drücke Enter zum Schließen…" _
