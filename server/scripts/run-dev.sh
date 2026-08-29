#!/usr/bin/env bash
# PocketClot — run locally (for development on macOS / Linux)
set -euo pipefail

cd "$(dirname "$0")/.."

# Claude Code CLI must be present
if ! command -v claude >/dev/null 2>&1; then
    echo "==> 'claude' not found in PATH."
    echo "    Install Claude Code: npm install -g @anthropic-ai/claude-code"
    echo "    Then sign in:         claude login"
    exit 1
fi
echo "==> Claude CLI: $(command -v claude)"

if [[ ! -f .venv/bin/activate ]]; then
    if [[ -d .venv ]]; then
        echo "==> Broken .venv detected — removing and recreating..."
        rm -rf .venv
    else
        echo "==> Creating venv..."
    fi
    python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

# Sync dependencies — pip install -r is idempotent and cached.
# We hash requirements.txt and skip the install if nothing changed.
REQUIREMENTS_HASH_FILE=".venv/.requirements.sha"
CURRENT_HASH=$(shasum -a 256 requirements.txt | cut -d' ' -f1)
LAST_HASH=$([ -f "$REQUIREMENTS_HASH_FILE" ] && cat "$REQUIREMENTS_HASH_FILE" || echo "")
if [[ "$CURRENT_HASH" != "$LAST_HASH" ]] || ! python -c "import fastapi" 2>/dev/null; then
    echo "==> Installing/updating dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
    echo "$CURRENT_HASH" > "$REQUIREMENTS_HASH_FILE"
fi

if [[ ! -f .env ]]; then
    echo "==> Creating .env from .env.example..."
    cp .env.example .env
    TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
    if [[ "$(uname)" == "Darwin" ]]; then
        sed -i '' "s|^SERVER_TOKEN=.*|SERVER_TOKEN=$TOKEN|" .env
    else
        sed -i "s|^SERVER_TOKEN=.*|SERVER_TOKEN=$TOKEN|" .env
    fi
    echo ""
    echo "    Generated SERVER_TOKEN: $TOKEN"
    echo "    → enter this under Settings → Bearer token in the Android app."
    echo ""
fi

echo "==> PocketClot starting on http://localhost:8787 ..."
exec python -m pocket_claude
