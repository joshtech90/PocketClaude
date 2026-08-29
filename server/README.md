# PocketClot — Server

Self-hosted FastAPI backend for [PocketClot](../README.md). Talks to Claude through one of three pluggable backends — the [Claude Code CLI](https://github.com/anthropics/claude-code) (OAuth / Pro/Max), a direct Anthropic API key, or AWS Bedrock — and exposes it as a multi-user chat API plus a built-in web UI.

For the full project overview, architecture diagram, and quickstart, see the [top-level README](../README.md).

## Layout

```
server/
├── pocket_claude/
│   ├── server.py             FastAPI app — endpoints, SSE streaming, mounts
│   ├── claude_engine.py      Wraps claude-agent-sdk, threads per-user auth env
│   ├── auth_modes.py         Multi-provider auth resolver (Pro/Max | API | Bedrock)
│   ├── usage.py              Per-user token-usage tracking (input/output/cache)
│   ├── tts.py                Three-provider TTS (Edge / Gemini / Cloud TTS)
│   ├── image_engine.py       Gemini Nano Banana image generation
│   ├── billing.py            Optional Google-Cloud-billing status widget
│   ├── backup.py             AES-256 encrypted ZIP export/import
│   ├── db.py                 aiosqlite + FTS5 search
│   ├── webui/                Built-in web UI (vanilla JS + i18n, no build step)
│   └── ...
├── deploy/                   Install/setup scripts for Linux + tunnel setup
├── scripts/                  Dev helpers (run-dev.sh, etc.)
├── requirements.txt
└── pocket_claude_manager.py  Optional macOS dev GUI (Tkinter)
```

## Run from source (dev)

```bash
cd server
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m pocket_claude
```

Server listens on `http://127.0.0.1:8787`. First start prints the initial admin password (also saved to `data/INITIAL_PASSWORD.txt`).

## Deploy to a Linux host

See [`deploy/README.md`](deploy/README.md). One-line install:

```bash
curl -fsSL https://raw.githubusercontent.com/joshtech90/PocketClot/main/server/deploy/install-linux.sh | sudo bash
```

## API surface

All endpoints except `/auth/login` and `/health` require `Authorization: Bearer <SESSION_TOKEN>`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/auth/login` | Username + password → session token |
| POST | `/auth/logout`, `/auth/logout-all` | End session(s) |
| POST | `/auth/change-password` | Self-service password change |
| GET | `/me` | Current user info |
| GET / PUT | `/me/claude-auth` | Per-user Claude backend (`pro_max` \| `api_key` \| `bedrock`) + credentials |
| GET | `/me/usage?period=month\|all` | Aggregated per-user token usage |
| GET / POST / PATCH / DELETE | `/conversations[/{id}]` | Chat CRUD |
| POST | `/conversations/{id}/messages` | Send message (SSE stream) |
| GET / POST / DELETE | `/conversations/{id}/skills` | Per-chat skill override |
| GET / POST | `/attachments[/{id}]` | File uploads |
| GET / PUT | `/tts/*` | TTS status / provider / voice / model |
| GET | `/messages/{id}/audio` | TTS audio stream |
| POST | `/images/generate` | Image generation (Gemini Nano Banana) |
| GET / POST | `/backup[/...]` | Encrypted backup |
| GET / POST | `/settings/export`, `/settings/import` | Settings export/import (includes auth + TTS + image config) |
| GET / POST / DELETE | `/users/...` | User management (admin) |
| GET | `/billing/status` | Optional Google Cloud spend widget (opt-in via env var) |

## Security

- The systemd unit ships with hardening (`NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, `ProtectKernelTunables/Modules/ControlGroups`). **NOT** `ProtectHome=true` — see the warning in [`deploy/README.md`](deploy/README.md#chat-hangs--journal-shows-control-request-timeout-initialize).
- `ALLOW_BASH` is **off by default** in `.env`. With it off, the per-chat "Bash" toggle in the app is a no-op — Bash is stripped from the tool list server-side regardless of what the client requests. Closes a hole where any app user could otherwise execute commands as the `pocket-claude` system user.
- All endpoints require a Bearer session token. Sessions are stored hashed in SQLite; expire on logout.

## License

MIT — see [`../LICENSE`](../LICENSE).
