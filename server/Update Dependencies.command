#!/usr/bin/env bash
# PocketClot server: refresh Python dependencies inside the venv.
# Double-click helper for macOS dev hosts. Use this after `requirements.txt`
# gained a new entry (e.g. pyzipper for encrypted backups).

set -e
cd "$(dirname "$0")"

# Falls .venv noch nicht existiert: scripts/run-dev.sh hat das in der Vergangenheit angelegt.
if [ ! -d ".venv" ]; then
    echo "❌ .venv fehlt. Bitte einmal 'bash scripts/run-dev.sh' laufen lassen — das legt das venv an."
    echo
    read -p "Fenster schließen mit Enter… " _
    exit 1
fi

echo "▶︎ Aktiviere venv…"
. .venv/bin/activate

echo "▶︎ Installiere / aktualisiere Dependencies aus requirements.txt…"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo
echo "✓ Fertig. Jetzt den Server-Manager neu starten (Stop + Start),"
echo "  damit der Server-Prozess die neuen Module lädt."
echo
read -p "Fenster schließen mit Enter… " _
