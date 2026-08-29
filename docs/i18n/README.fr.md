<div align="center">

<img src="../../assets/logo.png" alt="PocketClot" width="160" height="160">

# PocketClot

**Votre Claude personnel sur votre téléphone — propulsé par votre propre abonnement Pro/Max, une clé API Anthropic ou AWS Bedrock. Hébergé sur votre propre matériel.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](../../LICENSE)
[![Platform](https://img.shields.io/badge/platform-Android%2012%2B%20%7C%20Web-blue)](#)
[![Server](https://img.shields.io/badge/server-Python%203.10%2B-yellow)](#)
[![Status](https://img.shields.io/badge/status-public%20beta-green)](#)

[English](../../README.md) · [Deutsch](README.de.md) · [Español](README.es.md) · **Français** · [Português (BR)](README.pt-BR.md) · [中文](README.zh.md) · [日本語](README.ja.md)

</div>

---

## À propos

**PocketClot** est une interface de chat auto-hébergée pour [Claude](https://claude.ai) d'Anthropic. Un petit serveur Python tourne sur votre propre machine Linux (Mini-PC, Raspberry Pi, vieux portable, NAS) ; une application Android native et une interface web intégrée dialoguent avec lui depuis n'importe où via [Tailscale Funnel](https://tailscale.com/kb/1223/funnel) ou un tunnel Cloudflare.

**Choisissez le backend par utilisateur**, interchangeable à tout moment depuis l'application :

- **Abonnement Pro/Max** (par défaut) — utilise la session OAuth d'un CLI `claude` local installé sur le serveur, aucune clé API requise, fonctionne sur votre quota Pro/Max.
- **Clé API Anthropic** — `sk-ant-…` depuis la [Console Anthropic](https://console.anthropic.com), facturation à l'usage.
- **AWS Bedrock** — vos identifiants AWS, prise en charge de Claude Opus 4.7 via les IDs de modèle spécifiques à Bedrock.

**Pourquoi ce projet existe.** Les applications officielles de Claude sont très bien — PocketClot existe pour ce qu'elles ne font pas (encore) :

- **Open source.** Auditez-le, forkez-le, étendez-le. Pas de télémétrie cachée, pas de fonctionnalités qui disparaissent du jour au lendemain.
- **Des fonctionnalités en plus.** Lecture vocale TTS (trois fournisseurs, contrôles sur écran verrouillé), génération d'images, repliage des longs messages à la ChatGPT, recherche en texte intégral sur toutes vos discussions, sauvegardes chiffrées, quatre modes de system prompt au choix.
- **Plusieurs utilisateurs, un seul abonnement.** Partagez votre forfait Pro/Max avec la famille ou des collègues — chacun a ses propres discussions privées, ses propres réglages et ses propres clés API pour la génération d'images et le TTS.
- **Un second « Claude » bien net.** Vous voulez une séparation stricte perso/pro sans jongler entre deux comptes Anthropic ? Vous montez votre propre serveur, vous vous connectez en parallèle du client officiel, c'est réglé.
- **Vos données vous appartiennent.** Vos conversations vivent dans une base SQLite sur votre propre matériel. Migrez-la, sauvegardez-la, interrogez-la directement — elle est à vous.

**Aucune clé API Anthropic supplémentaire requise.** L'authentification, c'est la session OAuth qu'utilise votre CLI Claude Code installé localement (`claude login`). PocketClot lance le CLI ; le CLI fait le reste — en s'appuyant sur le même quota Pro/Max que vous payez déjà.

> **Note** — il s'agit d'un projet perso auto-hébergé, pas d'un produit Anthropic. Vous apportez votre propre abonnement Pro/Max. Nous ne voyons jamais vos conversations et ne servons jamais de relais.

## Points forts

- 💬 **Client Android natif** (Kotlin + Jetpack Compose, sans wrapper web) et une **interface web** intégrée comme solution de repli ou option desktop
- 👨‍👩‍👧 **Authentification multi-utilisateurs** avec hachage de mot de passe scrypt — toute votre famille ou équipe partage un seul compte Pro/Max, chacun avec ses propres chats et paramètres privés
- 📡 **Streaming SSE** avec contre-pression appropriée, intercepteur de réessai et keep-alive de connexion de 60 secondes (résilient sur Tailscale Funnel)
- 📎 **Pièces jointes généreuses** — images, PDF, code, fichiers de configuration, JSON, CSV, tout format texte. Intégrées en ligne ou référencées via l'outil `Read` de Claude
- 🔍 **Recherche en texte intégral** dans tout votre historique de chat (SQLite FTS5), avec saut vers la correspondance dans l'application
- 🔊 **Trois fournisseurs TTS** pour la lecture vocale — Microsoft Edge (gratuit, sans configuration), API Gemini Direct (palier gratuit) et Google Cloud TTS (Chirp 3 HD, 1 M de caractères/mois gratuits). Commandes audio sur écran verrouillé via Media3
- 🎨 **Génération d'images** via Gemini Nano Banana — écran dédié, galerie, partage, édition image-vers-image
- 🎭 **Quatre modes de system prompt** — Standard (défaut Anthropic), Permissif, Ultra-Libéral et Personnalisé
- 🛠 **Activation des skills par chat** — WebSearch, WebFetch, exécution Bash
- 🔐 **Sauvegardes chiffrées AES-256** des conversations et paramètres
- 🌐 **7 langues** — anglais, allemand, espagnol, français, portugais brésilien, chinois simplifié, japonais
- 🌗 Design Material You bord à bord avec thèmes clair et sombre

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

Deux composants, un seul dépôt :

| Chemin      | Ce que c'est                                                              |
|-------------|---------------------------------------------------------------------------|
| `server/`   | Backend Python FastAPI + interface web intégrée. Lance le CLI `claude`.   |
| `app/`      | Client Android (Kotlin + Jetpack Compose, Material 3).                    |

## Démarrage rapide

### 1 — Installer le serveur (machine Linux, ~5 minutes)

Sur une machine Ubuntu / Debian / Fedora fraîche :

```bash
curl -fsSL https://raw.githubusercontent.com/joshtech90/PocketClot/main/server/deploy/install-linux.sh | sudo bash
```

L'installateur crée un utilisateur système `pocket-claude`, dépose le code dans `/opt/pocket-claude/`, installe le CLI Claude Code, installe les dépendances Python dans un venv, écrit une unité systemd et la démarre sur le port `8787` (loopback).

### 2 — Se connecter à Claude avec votre compte Pro/Max

```bash
sudo -u pocket-claude -H claude login
```

Le flux OAuth s'exécute dans votre terminal. Même connexion que celle utilisée par Claude Code.

### 3 — Exposer le serveur avec une URL persistante (Tailscale Funnel, gratuit)

```bash
sudo bash /opt/pocket-claude/deploy/setup-tailscale-funnel.sh
```

Affiche l'URL publique une fois terminé — elle ressemble à `https://your-host.your-tailnet.ts.net`. Alternativement, le dossier deploy contient également un script de configuration Cloudflare Named Tunnel si vous préférez utiliser un domaine personnalisé.

### 4 — Installer l'application Android

Soit téléchargez l'APK depuis [la dernière version](https://github.com/joshtech90/PocketClot/releases), soit compilez-le vous-même :

```bash
cd app && ./gradlew assembleDebug
adb install app/build/outputs/apk/debug/app-debug.apk
```

Ouvrez l'application → **Ajouter un profil** → saisissez votre URL et le mot de passe administrateur initial (affiché au premier démarrage du serveur dans `/opt/pocket-claude/data/INITIAL_PASSWORD.txt`). Changez le mot de passe à la première connexion.

### 5 — (Optionnel) Utiliser l'interface web au lieu de l'application

Ouvrez simplement votre URL de tunnel dans n'importe quel navigateur. L'interface web est servie depuis le même processus FastAPI.

Configuration complète incluant le chemin Cloudflare, la migration d'hôte à hôte, le workflow de mise à jour quotidienne et le dépannage : **[`server/deploy/README.md`](../../server/deploy/README.md)**.

## Multi-utilisateurs

Après le premier démarrage, un utilisateur `Admin` est créé et le mot de passe initial est écrit dans `/opt/pocket-claude/data/INITIAL_PASSWORD.txt`. Utilisez l'écran **Utilisateurs** dans l'application (admin uniquement) pour ajouter d'autres utilisateurs — ils ont chacun leurs propres conversations, paramètres et clés API, le tout fonctionnant via votre seul abonnement Pro/Max.

## Lecture vocale TTS

Trois fournisseurs, sélectionnables par utilisateur :

| Fournisseur          | Qualité vocale         | Configuration                  | Coût                                              |
|----------------------|------------------------|--------------------------------|---------------------------------------------------|
| **Microsoft Edge**   | Bonne                  | aucune                         | gratuit (hébergé par Microsoft)                   |
| **Gemini Direct**    | Excellente             | clé API AI Studio              | palier gratuit (10 requêtes/jour par clé)         |
| **Google Cloud TTS** | Excellente (Chirp 3 HD) | JSON de compte de service     | 1 M caractères/mois gratuits, puis ~16 $/M caractères |

Dans l'application : **Paramètres → Lecture vocale → Fournisseur** et choisissez ce qui vous convient. Lecture automatique, sélecteurs de voix, vitesse de parole, pool multi-clés pour le palier gratuit de Gemini Direct.

## Génération d'images (Gemini Nano Banana)

Apportez votre propre clé API AI Studio (palier gratuit suffisant pour un usage occasionnel). Écran dédié, galerie, partage vers d'autres applications, édition image-vers-image. Désactivé dans l'interface si aucune clé n'est configurée.

## Stack technique

**Serveur.** Python 3.10+, FastAPI, Uvicorn, `sse-starlette` pour SSE, aiosqlite, SQLite + FTS5, [`claude-agent-sdk`](https://pypi.org/project/claude-agent-sdk/), `scrypt` (stdlib) pour le hachage de mot de passe, `pyzipper` pour les sauvegardes AES-256, `edge-tts` + SDK Google Cloud TTS + REST pour Gemini Direct.

**Application.** Kotlin 2.0.21, Android Gradle Plugin 8.7.3, compileSdk 35, minSdk 31, Jetpack Compose Material 3 (BOM 2024.12.01), OkHttp + okhttp-sse, DataStore Preferences, Coil 3, AndroidX Media3 (ExoPlayer + MediaSession), `compose-richtext` pour Markdown.

**Interface web.** JS vanilla, sans étape de build, servie en tant que fichiers statiques depuis le même processus FastAPI.

## Feuille de route

- [ ] Client iOS
- [ ] Déploiement Docker / Docker Compose en une ligne comme alternative au script d'installation système
- [ ] Saisie vocale (basée sur Whisper) côté application
- [ ] Budgets d'outils par conversation

## Contribuer

Les pull requests sont acceptées. Voir [CONTRIBUTING.md](../../CONTRIBUTING.md) pour le workflow.

## Licence

MIT — voir [LICENSE](../../LICENSE).

## Remerciements

- [Anthropic](https://www.anthropic.com/) pour Claude et le CLI Claude Code
- [Tailscale](https://tailscale.com/) pour rendre les tunnels publics zéro-config gratuits pour un usage personnel
- [`claude-agent-sdk`](https://github.com/anthropics/claude-agent-sdk-python) pour la surface propre de lancement du CLI
- Les équipes Compose, FastAPI et SQLite
