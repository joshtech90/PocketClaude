#!/usr/bin/env bash
# PocketClot Server — Doppelklick-Starter.
#
# Öffnet die Manager-GUI. Wenn ein .venv existiert, wird das venv-Python
# verwendet (damit FastAPI etc. verfügbar sind, falls Du Tkinter unter
# venv brauchst). Sonst System-Python — Tkinter ist da überall an Bord.
set -euo pipefail

cd "$(dirname "$0")"

# venv-Python bevorzugen — sonst System-Python
if [[ -x .venv/bin/python ]]; then
    PY=".venv/bin/python"
else
    PY="$(command -v python3 || true)"
fi

if [[ -z "$PY" ]]; then
    osascript -e 'display alert "Python 3 nicht gefunden" message "Bitte python3 installieren (z.B. `brew install python`) und nochmal versuchen."'
    exit 1
fi

# GUI im Hintergrund — Terminal kann zumachen.
"$PY" pocket_claude_manager.py
