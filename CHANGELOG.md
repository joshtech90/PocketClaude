# Changelog

All notable changes to PocketClot are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [SemVer](https://semver.org/).

## [0.2.0] — 2026-05-19

### Added

- **Multi-provider Claude authentication** — per-user selectable backend:
  - Pro/Max OAuth (default): runs against your Claude subscription via the local `claude login` session
  - Anthropic API: direct API key, pay-as-you-go billing
  - AWS Bedrock: routes through Amazon Bedrock with your AWS credentials, supports Claude Opus 4.7 on pinned model IDs
- **Token usage tracking** — per-user aggregate of input/output/cache tokens persisted to the database, exposed via `GET /me/usage?period=month`, surfaced in **Settings → Token usage** in both clients.
- **Auth mode + credential forms** in the app's Settings screen and the web UI's settings modal.
- **Complete localization** — every user-facing string in the app and web UI is now translated into all 7 supported languages (was partial in v0.1.0).
- Settings backup/export covers the new auth-mode + Bedrock model-ID fields.

### Changed

- `claude-agent-sdk` constraint raised to `>=0.2.82,<1.0` (was `>=0.1.81,<0.2`); the 0.1 line is no longer compatible with current Claude Code CLI builds.
- `install-linux.sh` now detects an existing system-wide `claude` binary and skips the Node + npm + claude-cli install when one is on PATH — saves time and avoids version collisions on hosts that already have it. Also warns when the binary isn't visible to the `pocket-claude` service user.
- `install-linux.sh` default `REPO_URL` updated to the new mono-repo (`joshtech90/PocketClot`).
- README rewritten — replaced an incorrect claim about Anthropic API billing with the actual reasons to self-host (open source, extra features, multi-user on one subscription, clean second-Claude separation, data ownership).

### Security

- **Bash skill is off by default at the server level.** Set `ALLOW_BASH=1` in `.env` to opt in. Closes a hole where any app-account user could request the Bash tool and execute commands as the `pocket-claude` system user.
- `BILLING_ACCOUNT_ID` is no longer hardcoded — set via `POCKET_CLAUDE_BILLING_ACCOUNT_ID`; the billing widget hides itself when the env var is unset.

### Fixed

- **"New chat" button** in the drawer no longer scrolls to the end of the current chat. Now creates a fresh conversation directly.
- Personal references removed from Python module headers + deploy scripts.

[0.2.0]: https://github.com/joshtech90/PocketClot/releases/tag/v0.2.0

## [0.1.0] — 2026-05-19

### Added

- Initial public release.
- **Server** (Python 3.10+, FastAPI, SQLite + FTS5)
  - Multi-user authentication (scrypt + session tokens), admin user-management endpoints.
  - SSE streaming of Claude replies via `claude-agent-sdk`.
  - File attachments (images, PDFs, code, configs, JSON, CSV, arbitrary text formats).
  - Full-text search across all conversations.
  - Three TTS providers: Microsoft Edge (free), Gemini Direct API (free tier), Google Cloud TTS (Chirp 3 HD).
  - Image generation via Gemini Nano Banana (separate from chat).
  - Four system-prompt modes: Standard, Permissive, Ultra-Liberal, Custom.
  - Per-chat skill toggles (WebSearch, WebFetch, Bash).
  - AES-256 encrypted backups.
  - Built-in web UI as a desktop / browser alternative to the app.
  - Linux deployment via `deploy/install-linux.sh`, Tailscale Funnel setup, optional Cloudflare Named Tunnel.
- **Android app** (Kotlin 2.0.21, Jetpack Compose Material 3, minSdk 31)
  - Multi-profile login (one app instance can talk to multiple servers / families).
  - Native chat with Markdown rendering, code-block highlighting, native text selection.
  - In-chat full-text search with spring-to-match navigation.
  - Lock-screen TTS audio controls via Media3 ExoPlayer + MediaSession.
  - Liberal file uploads matching the server's accepted types.
  - Image generation screen with gallery and image-to-image editing.
  - ChatGPT-style collapse for long user messages.
  - Encrypted backup + settings export/import.
- **Internationalization**
  - 7 languages: English (default), German, Spanish, French, Brazilian Portuguese, Simplified Chinese, Japanese.
  - In-app language picker under **Settings → Appearance → Language**.
  - Web-UI language picker in **Settings → Language**.
  - Top-level README + per-language README translations under `docs/i18n/`.
- **Documentation**
  - Comprehensive English `README.md` with logo, architecture diagram, quickstart for server + app.
  - Multilingual READMEs for all 7 supported languages.
  - `server/deploy/README.md` covering Tailscale + Cloudflare paths, host migration, troubleshooting.
  - `server/deploy/WORKFLOW.md` for the daily Mac → Mini-PC development loop.

[0.1.0]: https://github.com/joshtech90/PocketClot/releases/tag/v0.1.0
