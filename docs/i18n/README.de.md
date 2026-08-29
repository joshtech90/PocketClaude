<div align="center">

<img src="../../assets/logo.png" alt="PocketClot" width="160" height="160">

# PocketClot

**Dein persönlicher Claude auf dem Handy — wahlweise über Dein eigenes Pro/Max-Abo, einen Anthropic-API-Key oder AWS Bedrock. Gehostet auf Deiner eigenen Hardware.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](../../LICENSE)
[![Platform](https://img.shields.io/badge/platform-Android%2012%2B%20%7C%20Web-blue)](#)
[![Server](https://img.shields.io/badge/server-Python%203.10%2B-yellow)](#)
[![Status](https://img.shields.io/badge/status-public%20beta-green)](#)

[English](../../README.md) · **Deutsch** · [Español](README.es.md) · [Français](README.fr.md) · [Português (BR)](README.pt-BR.md) · [中文](README.zh.md) · [日本語](README.ja.md)

</div>

---

## Worum geht's

**PocketClot** ist ein selbst-gehostetes Chat-Frontend für Anthropic's [Claude](https://claude.ai). Ein kleiner Python-Server läuft auf Deinem eigenen Linux-Host (Mini-PC, Raspberry Pi, alter Laptop, NAS); eine native Android-App und eine integrierte Web-UI sprechen via [Tailscale Funnel](https://tailscale.com/kb/1223/funnel) oder Cloudflare-Tunnel von überall mit ihm.

**Backend pro User frei wählbar**, jederzeit in der App umschaltbar:

- **Pro/Max-Abo** (Default) — nutzt die OAuth-Session eines lokalen `claude`-CLI auf dem Server, kein API-Key nötig, läuft auf Deinem Pro/Max-Kontingent.
- **Anthropic-API-Key** — `sk-ant-…` aus der [Anthropic Console](https://console.anthropic.com), Pay-as-you-go-Abrechnung.
- **AWS Bedrock** — Deine AWS-Credentials, unterstützt Claude Opus 4.7 über die Bedrock-spezifischen Modell-IDs.

**Warum?** Anthropics offizielle Claude-Apps sind super — PocketClot ist für die Dinge da, die sie (noch) nicht können:

- **Open Source.** Quellcode einsehbar, forkbar, erweiterbar. Keine Mystery-Telemetrie, keine überraschend entfernten Features.
- **Mehr Features.** TTS-Vorlesen (drei Provider, Lockscreen-Controls), Bild-Generation, ChatGPT-Style-Einklappen langer Nachrichten, Volltextsuche über alle Chats, verschlüsselte Backups, vier wählbare System-Prompt-Modi.
- **Multi-User auf einem Abo.** Teile Dein Pro/Max-Abo mit Familie oder Kollegen — jeder User hat eigene Chats, eigene Settings und eigene API-Keys für Bild-Gen und TTS.
- **Ein zweiter "Claude" sauber getrennt.** Privat und Job strikt trennen, ohne zwei Anthropic-Accounts zu jonglieren? Eigenen Server hochziehen, parallel zum offiziellen Client einloggen, fertig.
- **Deine Daten gehören Dir.** Konversationen liegen in einer SQLite-DB auf Deiner Hardware. Migrierbar, backup-bar, direkt abfragbar.

**Kein zusätzlicher Anthropic-API-Key nötig.** Authentifizierung läuft über die OAuth-Session, die Dein lokal installiertes Claude-Code-CLI nutzt (`claude login`). PocketClot spawnt das CLI; das CLI macht den Rest — auf demselben Pro/Max-Kontingent, das Du bereits bezahlst.

> **Hinweis** — das ist ein selbst-gehostetes Hobby-Projekt, kein Anthropic-Produkt. Du bringst Dein eigenes Pro/Max-Abo mit. Wir sehen oder proxien Deine Konversationen nie.

## Highlights

- 💬 **Native Android-App** (Kotlin + Jetpack Compose, kein Web-Wrapper) und eine **integrierte Web-UI** als Fallback bzw. Desktop-Option
- 👨‍👩‍👧 **Multi-User-Auth** mit scrypt-Passwort-Hashing — die ganze Familie/das Team teilt ein Pro/Max-Konto, jeder hat eigene Chats und Settings
- 📡 **SSE-Streaming** mit korrektem Backpressure, Retry-Interceptor und 60-Sek-Connection-Keep-Alive (stabil über Tailscale Funnel)
- 📎 **Liberale Datei-Anhänge** — Bilder, PDFs, Code, Configs, JSON, CSV, beliebige Text-Formate. Inline embedded oder via Claudes `Read`-Tool referenziert
- 🔍 **Volltextsuche** über die ganze Chat-Historie (SQLite FTS5), mit Spring-to-Match in der App
- 🔊 **Drei TTS-Provider** zum Vorlesen — Microsoft Edge (gratis, kein Setup), Gemini Direct API (Free Tier), Google Cloud TTS (Chirp 3 HD, 1 Mio Zeichen/Monat gratis). Lockscreen-Audio-Controls via Media3
- 🎨 **Bild-Generation** via Gemini Nano Banana — eigener Screen, Galerie, Share, Image-to-Image-Editing
- 🎭 **Vier System-Prompt-Modi** — Standard (Anthropic-Default), Permissiv, Ultra-Liberal und Custom
- 🛠 **Skill-Toggles pro Chat** — WebSearch, WebFetch, Bash-Ausführung
- 🔐 **AES-256-verschlüsselte Backups** von Konversationen + Einstellungen
- 🌐 **7 Sprachen** — Englisch, Deutsch, Spanisch, Französisch, brasilianisches Portugiesisch, vereinfachtes Chinesisch, Japanisch
- 🌗 Edge-to-Edge Material-You-Design mit Light- und Dark-Theme

## Architektur

```
                ┌───────────────────────────┐
                │  PocketClot (Android)  │
                │       oder Web-UI         │
                └─────────────┬─────────────┘
                              │ HTTPS  (persistente URL)
                              ▼
              ┌─────────────────────────────────┐
              │  Tailscale Funnel               │
              │  (oder Cloudflare Named Tunnel) │
              └─────────────┬───────────────────┘
                              │ Outbound-Tunnel — kein Port-Forwarding
                              ▼
                ┌────────────────────────────┐
                │     Dein Linux-Host        │
                │   ┌──────────────────────┐ │
                │   │  pocket-claude.svc   │ │ ── FastAPI + SQLite (FTS5)
                │   │   (systemd-Unit)     │ │
                │   │     │                │ │
                │   │     └─ spawnt:       │ │
                │   │        claude-code   │ │ ── Dein Pro/Max-OAuth
                │   └──────────────────────┘ │
                │   ┌──────────────────────┐ │
                │   │   tailscaled.svc     │ │
                │   └──────────────────────┘ │
                └────────────────────────────┘
```

Zwei Komponenten, ein Repo:

| Pfad        | Was ist drin                                                              |
|-------------|---------------------------------------------------------------------------|
| `server/`   | Python-FastAPI-Backend + integrierte Web-UI. Spawnt das `claude`-CLI.     |
| `app/`      | Android-Client (Kotlin + Jetpack Compose, Material 3).                    |

## Quickstart

### 1 — Server installieren (Linux-Host, ~5 Minuten)

Auf einer frischen Ubuntu-/Debian-/Fedora-Box:

```bash
curl -fsSL https://raw.githubusercontent.com/joshtech90/PocketClot/main/server/deploy/install-linux.sh | sudo bash
```

Der Installer legt einen `pocket-claude`-Systemuser an, deployt den Code nach `/opt/pocket-claude/`, installiert das Claude-Code-CLI + Python-Dependencies in ein venv, schreibt eine systemd-Unit und startet sie auf Port `8787` (Loopback).

### 2 — Mit Deinem Pro/Max-Account einloggen

```bash
sudo -u pocket-claude -H claude login
```

OAuth-Flow läuft im Terminal. Derselbe Login, den Claude-Code nutzt.

### 3 — Persistente Public-URL einrichten (Tailscale Funnel, gratis)

```bash
sudo bash /opt/pocket-claude/deploy/setup-tailscale-funnel.sh
```

Gibt am Ende die öffentliche URL aus — sieht aus wie `https://dein-host.dein-tailnet.ts.net`. Im `deploy/`-Ordner liegt auch ein Cloudflare-Named-Tunnel-Setup-Skript, falls Du lieber Deine eigene Domain nutzen willst.

### 4 — Android-App installieren

Entweder APK aus dem [letzten Release](https://github.com/joshtech90/PocketClot/releases) ziehen oder selbst bauen:

```bash
cd app && ./gradlew assembleDebug
adb install app/build/outputs/apk/debug/app-debug.apk
```

App öffnen → **Profil hinzufügen** → URL + initiales Admin-Passwort eintragen (steht beim ersten Server-Start in `/opt/pocket-claude/data/INITIAL_PASSWORD.txt`). Passwort beim ersten Login ändern.

### 5 — (Optional) Web-UI statt App

Tunnel-URL einfach im Browser öffnen. Die Web-UI wird vom selben FastAPI-Prozess ausgeliefert.

Vollständige Doku inkl. Cloudflare-Pfad, Host-zu-Host-Migration, Daily-Update-Workflow und Troubleshooting: **[`server/deploy/README.md`](../../server/deploy/README.md)**.

## Multi-User

Beim ersten Start wird ein `Admin`-User angelegt, das initiale Passwort steht in `/opt/pocket-claude/data/INITIAL_PASSWORD.txt`. Über den **Benutzer**-Screen in der App (nur Admin) kannst Du weitere User anlegen — jeder bekommt eigene Konversationen, Settings und API-Keys, alles läuft über Dein eines Pro/Max-Abo.

## TTS-Vorlesen

Drei Provider, pro User wählbar:

| Provider           | Stimmqualität | Setup                          | Kosten                                          |
|--------------------|---------------|--------------------------------|-------------------------------------------------|
| **Microsoft Edge** | Gut           | Keins                          | Gratis (Microsoft hostet)                       |
| **Gemini Direct**  | Sehr gut      | AI-Studio-API-Key              | Free Tier (10 Requests/Tag pro Key)             |
| **Google Cloud TTS** | Sehr gut (Chirp 3 HD) | Service-Account-JSON | 1 Mio Zeichen/Monat gratis, dann ~$16/M Zeichen |

In der App: **Einstellungen → Vorlesen → Provider** auswählen. Auto-Speak, Voice-Picker, Sprechgeschwindigkeit, Multi-Key-Pool für den Gemini-Direct-Free-Tier.

## Bild-Generation (Gemini Nano Banana)

AI-Studio-API-Key mitbringen (Free-Tier reicht für gelegentliche Nutzung). Eigener Screen, Galerie, Share-to-other-Apps, Image-to-Image-Editing. UI deaktiviert wenn kein Key konfiguriert ist.

## Tech-Stack

**Server.** Python 3.10+, FastAPI, Uvicorn, `sse-starlette` für SSE, aiosqlite, SQLite + FTS5, [`claude-agent-sdk`](https://pypi.org/project/claude-agent-sdk/), `scrypt` (stdlib) für Passwort-Hashing, `pyzipper` für AES-256-Backups, `edge-tts` + Google Cloud TTS SDK + REST für Gemini Direct.

**App.** Kotlin 2.0.21, Android Gradle Plugin 8.7.3, compileSdk 35, minSdk 31, Jetpack Compose Material 3 (BOM 2024.12.01), OkHttp + okhttp-sse, DataStore Preferences, Coil 3, AndroidX Media3 (ExoPlayer + MediaSession), `compose-richtext` für Markdown.

**Web-UI.** Vanilla JS, kein Build-Step, wird als statische Files vom selben FastAPI-Prozess ausgeliefert.

## Roadmap

- [ ] iOS-Client
- [ ] Docker / Docker Compose Deployment als One-Liner-Alternative zum System-Install-Skript
- [ ] Voice-Input (Whisper-basiert) auf der App-Seite
- [ ] Tool-Budgets pro Konversation

## Mitmachen

Pull Requests werden angenommen. Siehe [CONTRIBUTING.md](../../CONTRIBUTING.md) für den Workflow.

## Lizenz

MIT — siehe [LICENSE](../../LICENSE).

## Danksagungen

- [Anthropic](https://www.anthropic.com/) für Claude und das Claude-Code-CLI
- [Tailscale](https://tailscale.com/) dafür, dass Zero-Config-Public-Tunnels für Privatgebrauch gratis sind
- [`claude-agent-sdk`](https://github.com/anthropics/claude-agent-sdk-python) für das saubere CLI-Spawning-Interface
- Die Compose-, FastAPI- und SQLite-Teams
