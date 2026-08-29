<div align="center">

<img src="assets/logo.png" alt="PocketClot" width="160" height="160">

# PocketClot

**Your personal Claude on your phone — backed by your own Pro/Max subscription, an Anthropic API key, or AWS Bedrock. Hosted on your own hardware.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Android%2012%2B%20%7C%20Web-blue)](#)
[![Server](https://img.shields.io/badge/server-Python%203.10%2B-yellow)](#)
[![Status](https://img.shields.io/badge/status-public%20beta-green)](#)

[English](README.md) · [Deutsch](docs/i18n/README.de.md) · [Español](docs/i18n/README.es.md) · [Français](docs/i18n/README.fr.md) · [Português (BR)](docs/i18n/README.pt-BR.md) · [中文](docs/i18n/README.zh.md) · [日本語](docs/i18n/README.ja.md)

</div>

---

## About

**PocketClot** is a self-hosted chat front-end for Anthropic's [Claude](https://claude.ai). A small Python server runs on your own Linux box (Mini-PC, Raspberry Pi, old laptop, NAS); a native Android app and a built-in web UI talk to it from anywhere via [Tailscale Funnel](https://tailscale.com/kb/1223/funnel) or a Cloudflare tunnel.

**Pick the backend per user**, switchable any time in the app:

- **Pro/Max subscription** (default) — uses the OAuth session of a local `claude` CLI on the server, no API key needed, runs against your Pro/Max quota.
- **Anthropic API key** — `sk-ant-…` from the [Anthropic Console](https://console.anthropic.com), pay-as-you-go billing.
- **AWS Bedrock** — your AWS credentials, supports Claude Opus 4.7 on Bedrock-pinned model IDs.

**Why this exists.** Anthropic's official Claude apps are great — PocketClot exists for the things they don't (yet) do:

- **Open source.** Audit it, fork it, extend it. No mystery telemetry, no surprise feature removals.
- **Extra features.** TTS read-aloud (three providers, lock-screen controls), image generation, ChatGPT-style long-message collapse, full-text search across all your chats, encrypted backups, four selectable system-prompt modes.
- **Multi-user, one subscription.** Share your Pro/Max plan with family or colleagues — each user has private chats, private settings, and their own API keys for image-gen and TTS.
- **A clean second "Claude".** Want a strict personal/work separation without juggling two Anthropic accounts? Spin up your own server, log in side-by-side with the official client, done.
- **You own the data.** Your conversations live in a SQLite database on your hardware. Migrate it, back it up, query it directly — it's yours.

**No additional Anthropic API key required.** Authentication is the OAuth session your locally-installed Claude Code CLI uses (`claude login`). PocketClot spawns the CLI; the CLI handles the rest — running on the same Pro/Max quota you already pay for.

> **Note** — this is a self-hosted hobby project, not an Anthropic product. You bring your own Pro/Max subscription. We never see or proxy your conversations.

## Screenshots

<table>
  <tr>
    <td align="center" width="25%"><img src="assets/screenshots/android-app-04.jpg" alt="Android chat" width="240"><br><sub>Android chat</sub></td>
    <td align="center" width="25%"><img src="assets/screenshots/android-app-02.jpg" alt="Conversations drawer" width="240"><br><sub>Drawer with recent chats</sub></td>
    <td align="center" width="25%"><img src="assets/screenshots/android-app-03.jpg" alt="Settings" width="240"><br><sub>Settings — system prompt, skills, providers</sub></td>
  </tr>
</table>

<p align="center">
  <img src="assets/screenshots/desktop-ui-01.png" alt="Web UI" width="720"><br>
  <sub>Built-in web UI (desktop)</sub>
</p>

<sub>More screenshots in <a href="assets/screenshots/"><code>assets/screenshots/</code></a> — 15 phone shots + 6 desktop shots showing TTS, image generation, multi-user admin, backup/restore, etc.</sub>

## Highlights

- 💬 **Native Android client** (Kotlin + Jetpack Compose, no web wrapper) and a built-in **web UI** as a fallback / desktop option
- 👨‍👩‍👧 **Multi-user authentication** with scrypt password hashing — your whole family/team shares one Pro/Max account, each with private chats and settings
- 📡 **SSE streaming** with proper backpressure, retry interceptor, and 60-second connection keep-alive (resilient over Tailscale Funnel)
- 📎 **Liberal file attachments** — images, PDFs, code, configs, JSON, CSV, any text format. Inlined or referenced via the Claude `Read` tool
- 🔍 **Full-text search** across your whole chat history (SQLite FTS5), with spring-to-match in the app
- 🔊 **Three TTS providers** for read-aloud — Microsoft Edge (free, no setup), Gemini Direct API (free tier), and Google Cloud TTS (Chirp 3 HD, 1M chars/month free). Lock-screen audio controls via Media3
- 🎨 **Image generation** via Gemini Nano Banana — separate screen, gallery, share, image-to-image editing
- 🎭 **Four system-prompt modes** — Standard (Anthropic default), Permissive, Ultra-Liberal, and Custom
- 🛠 **Per-chat skill toggles** — WebSearch, WebFetch, Bash execution
- 🔐 **AES-256-encrypted backups** of conversations + settings
- 🌐 **7 languages** — English, German, Spanish, French, Brazilian Portuguese, simplified Chinese, Japanese
- 🌗 Edge-to-edge Material You design with light + dark themes

## Architecture

```
                ┌───────────────────────────┐
                │  PocketClot (Android)  │
                │      or built-in web UI   │
                └─────────────┬─────────────┘
                              │ HTTPS  (persistent URL)
                              ▼
              ┌─────────────────────────────────┐
              │  Tailscale Funnel               │
              │  (or Cloudflare Named Tunnel)   │
              └─────────────┬───────────────────┘
                              │ outbound tunnel — no port forwarding
                              ▼
                ┌────────────────────────────┐
                │      Your Linux host       │
                │   ┌──────────────────────┐ │
                │   │  pocket-claude.svc   │ │ ── FastAPI + SQLite (FTS5)
                │   │   (systemd unit)     │ │
                │   │     │                │ │
                │   │     └─ spawns:       │ │
                │   │        claude-code   │ │ ── your Pro/Max OAuth
                │   └──────────────────────┘ │
                │   ┌──────────────────────┐ │
                │   │   tailscaled.svc     │ │
                │   └──────────────────────┘ │
                └────────────────────────────┘
```

Two components, one repository:

| Path        | What it is                                                                |
|-------------|---------------------------------------------------------------------------|
| `server/`   | Python FastAPI backend + built-in web UI. Spawns the `claude` CLI.        |
| `app/`      | Android client (Kotlin + Jetpack Compose, Material 3).                    |

## Quickstart

### 1 — Install the server (Linux host, ~5 minutes)

On a fresh Ubuntu / Debian / Fedora box:

```bash
curl -fsSL https://raw.githubusercontent.com/joshtech90/PocketClot/main/server/deploy/install-linux.sh | sudo bash
```

The installer creates a `pocket-claude` system user, drops the code into `/opt/pocket-claude/`, installs the Claude Code CLI, installs Python dependencies into a venv, writes a systemd unit, and starts it on port `8787` (loopback).

### 2 — Log into Claude with your Pro/Max account

```bash
sudo -u pocket-claude -H claude login
```

OAuth flow runs in your terminal. Same login Claude Code uses.

### 3 — Expose the server with a persistent URL (Tailscale Funnel, free)

```bash
sudo bash /opt/pocket-claude/deploy/setup-tailscale-funnel.sh
```

Prints the public URL when it's done — looks like `https://your-host.your-tailnet.ts.net`. Alternatively, the deploy folder also has a Cloudflare Named Tunnel setup script if you'd rather use a custom domain.

### 4 — Install the Android app

Either download the APK from [the latest release](https://github.com/joshtech90/PocketClot/releases) or build it yourself:

```bash
cd app && ./gradlew assembleDebug
adb install app/build/outputs/apk/debug/app-debug.apk
```

Open the app → **Add profile** → enter your URL + the initial admin password (printed at first server start in `/opt/pocket-claude/data/INITIAL_PASSWORD.txt`). Change the password on first login.

### 5 — (Optional) Use the web UI instead of the app

Just open your tunnel URL in any browser. The web UI is served from the same FastAPI process.

Full setup including the Cloudflare path, host-to-host migration, daily-update workflow, and troubleshooting: **[`server/deploy/README.md`](server/deploy/README.md)**.

## Multi-user

After first start, an `Admin` user is created and the initial password is written to `/opt/pocket-claude/data/INITIAL_PASSWORD.txt`. Use the **Users** screen in the app (admin only) to add more users — they each get their own conversations, settings, and API keys, all running through your one Pro/Max subscription.

## TTS read-aloud

Three providers, selectable per user:

| Provider           | Voice quality | Setup                          | Cost                                            |
|--------------------|---------------|--------------------------------|-------------------------------------------------|
| **Microsoft Edge** | Good          | none                           | free (Microsoft hosts)                          |
| **Gemini Direct**  | Excellent     | AI Studio API key              | free tier (10 requests/day per key)             |
| **Google Cloud TTS** | Excellent (Chirp 3 HD) | Service account JSON | 1M chars/month free, then ~$16/M chars |

In the app: **Settings → Read aloud → Provider** and pick what fits. Auto-speak, voice pickers, speech rate, multi-key pool for the Gemini Direct free tier.

## Image generation (Gemini Nano Banana)

Bring your own AI Studio API key (free tier sufficient for casual use). Dedicated screen, gallery, share-to-other-apps, image-to-image editing. Disabled in the UI if no key is configured.

## Tech stack

**Server.** Python 3.10+, FastAPI, Uvicorn, `sse-starlette` for SSE, aiosqlite, SQLite + FTS5, [`claude-agent-sdk`](https://pypi.org/project/claude-agent-sdk/), `scrypt` (stdlib) for password hashing, `pyzipper` for AES-256 backups, `edge-tts` + Google Cloud TTS SDK + REST for Gemini Direct.

**App.** Kotlin 2.0.21, Android Gradle Plugin 8.7.3, compileSdk 35, minSdk 31, Jetpack Compose Material 3 (BOM 2024.12.01), OkHttp + okhttp-sse, DataStore Preferences, Coil 3, AndroidX Media3 (ExoPlayer + MediaSession), `compose-richtext` for Markdown.

**Web UI.** Vanilla JS, no build step, served as static files from the same FastAPI process.

## Roadmap

- [ ] iOS client
- [ ] Docker / Docker Compose deployment as a one-liner alternative to the system-install script
- [ ] Voice input (Whisper-based) on the app side
- [ ] Per-conversation tool budgets

## Contributing

Pull requests are accepted. See [CONTRIBUTING.md](CONTRIBUTING.md) for the workflow.

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgements

- [Anthropic](https://www.anthropic.com/) for Claude and the Claude Code CLI
- [Tailscale](https://tailscale.com/) for making zero-config public tunnels free for personal use
- [`claude-agent-sdk`](https://github.com/anthropics/claude-agent-sdk-python) for the clean CLI-spawning surface
- The Compose, FastAPI, and SQLite teams
