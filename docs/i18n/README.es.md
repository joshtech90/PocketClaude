<div align="center">

<img src="../../assets/logo.png" alt="PocketClot" width="160" height="160">

# PocketClot

**Tu Claude personal en tu teléfono — respaldado por tu propia suscripción Pro/Max, una clave de API de Anthropic o AWS Bedrock. Alojado en tu propio hardware.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](../../LICENSE)
[![Platform](https://img.shields.io/badge/platform-Android%2012%2B%20%7C%20Web-blue)](#)
[![Server](https://img.shields.io/badge/server-Python%203.10%2B-yellow)](#)
[![Status](https://img.shields.io/badge/status-public%20beta-green)](#)

[English](../../README.md) · [Deutsch](README.de.md) · **Español** · [Français](README.fr.md) · [Português (BR)](README.pt-BR.md) · [中文](README.zh.md) · [日本語](README.ja.md)

</div>

---

## Acerca de

**PocketClot** es un front-end de chat autoalojado para [Claude](https://claude.ai) de Anthropic. Un pequeño servidor Python se ejecuta en tu propia máquina Linux (Mini-PC, Raspberry Pi, laptop vieja, NAS); una aplicación nativa para Android y una interfaz web integrada se comunican con él desde cualquier lugar a través de [Tailscale Funnel](https://tailscale.com/kb/1223/funnel) o un túnel de Cloudflare.

**Elige el backend por usuario**, intercambiable en cualquier momento desde la app:

- **Suscripción Pro/Max** (predeterminado) — usa la sesión OAuth de una CLI `claude` local en el servidor, sin clave de API, contra tu cuota Pro/Max.
- **Clave de API de Anthropic** — `sk-ant-…` desde la [Consola de Anthropic](https://console.anthropic.com), facturación por consumo.
- **AWS Bedrock** — tus credenciales de AWS, compatible con Claude Opus 4.7 mediante los IDs de modelo específicos de Bedrock.

**Por qué existe.** Las aplicaciones oficiales de Claude de Anthropic son geniales — PocketClot existe para las cosas que ellas (todavía) no hacen:

- **Código abierto.** Audítalo, bifúrcalo, extiéndelo. Sin telemetría misteriosa, sin eliminaciones sorpresa de funciones.
- **Funciones extra.** Lectura en voz alta con TTS (tres proveedores, controles en la pantalla de bloqueo), generación de imágenes, colapso de mensajes largos al estilo ChatGPT, búsqueda de texto completo en todos tus chats, copias de seguridad cifradas, cuatro modos seleccionables de prompt del sistema.
- **Multiusuario, una suscripción.** Comparte tu plan Pro/Max con tu familia o tus colegas — cada usuario tiene chats privados, ajustes privados y sus propias claves de API para generación de imágenes y TTS.
- **Un segundo "Claude" limpio.** ¿Quieres una separación estricta entre lo personal y el trabajo sin tener que malabarear dos cuentas de Anthropic? Levanta tu propio servidor, inicia sesión en paralelo con el cliente oficial, listo.
- **Tú eres dueño de los datos.** Tus conversaciones viven en una base de datos SQLite en tu hardware. Migrala, respáldala, consúltala directamente — es tuya.

**No se requiere una clave de API adicional de Anthropic.** La autenticación es la sesión OAuth que utiliza tu CLI de Claude Code instalada localmente (`claude login`). PocketClot inicia la CLI; la CLI se encarga del resto — funcionando con la misma cuota Pro/Max que ya pagas.

> **Nota** — esto es un proyecto autoalojado por afición, no un producto de Anthropic. Tú aportas tu propia suscripción Pro/Max. Nunca vemos ni intermediamos tus conversaciones.

## Destacados

- 💬 **Cliente nativo de Android** (Kotlin + Jetpack Compose, sin envoltorio web) y una **interfaz web** integrada como opción de respaldo / escritorio
- 👨‍👩‍👧 **Autenticación multiusuario** con hashing de contraseñas scrypt — toda tu familia/equipo comparte una sola cuenta Pro/Max, cada uno con chats y ajustes privados
- 📡 **Streaming SSE** con backpressure adecuado, interceptor de reintentos y keep-alive de conexión de 60 segundos (resistente sobre Tailscale Funnel)
- 📎 **Adjuntos de archivos generosos** — imágenes, PDFs, código, configuraciones, JSON, CSV, cualquier formato de texto. Insertados en línea o referenciados mediante la herramienta `Read` de Claude
- 🔍 **Búsqueda de texto completo** en todo tu historial de chat (SQLite FTS5), con salto a la coincidencia en la aplicación
- 🔊 **Tres proveedores de TTS** para lectura en voz alta — Microsoft Edge (gratis, sin configuración), Gemini Direct API (capa gratuita) y Google Cloud TTS (Chirp 3 HD, 1M caracteres/mes gratis). Controles de audio en la pantalla de bloqueo mediante Media3
- 🎨 **Generación de imágenes** mediante Gemini Nano Banana — pantalla separada, galería, compartir, edición imagen a imagen
- 🎭 **Cuatro modos de prompt del sistema** — Estándar (predeterminado de Anthropic), Permisivo, Ultra-Liberal y Personalizado
- 🛠 **Conmutadores de habilidades por chat** — WebSearch, WebFetch, ejecución de Bash
- 🔐 **Copias de seguridad cifradas con AES-256** de conversaciones + ajustes
- 🌐 **7 idiomas** — Inglés, alemán, español, francés, portugués brasileño, chino simplificado, japonés
- 🌗 Diseño Material You edge-to-edge con temas claro + oscuro

## Arquitectura

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

Dos componentes, un repositorio:

| Ruta        | Qué es                                                                    |
|-------------|---------------------------------------------------------------------------|
| `server/`   | Backend Python FastAPI + interfaz web integrada. Inicia la CLI `claude`.  |
| `app/`      | Cliente Android (Kotlin + Jetpack Compose, Material 3).                   |

## Inicio rápido

### 1 — Instalar el servidor (host Linux, ~5 minutos)

En una máquina Ubuntu / Debian / Fedora nueva:

```bash
curl -fsSL https://raw.githubusercontent.com/joshtech90/PocketClot/main/server/deploy/install-linux.sh | sudo bash
```

El instalador crea un usuario de sistema `pocket-claude`, coloca el código en `/opt/pocket-claude/`, instala la CLI de Claude Code, instala las dependencias de Python en un venv, escribe una unidad systemd y la inicia en el puerto `8787` (loopback).

### 2 — Inicia sesión en Claude con tu cuenta Pro/Max

```bash
sudo -u pocket-claude -H claude login
```

El flujo OAuth se ejecuta en tu terminal. El mismo inicio de sesión que usa Claude Code.

### 3 — Expón el servidor con una URL persistente (Tailscale Funnel, gratis)

```bash
sudo bash /opt/pocket-claude/deploy/setup-tailscale-funnel.sh
```

Imprime la URL pública cuando termina — se ve como `https://your-host.your-tailnet.ts.net`. Alternativamente, la carpeta deploy también incluye un script de configuración de Cloudflare Named Tunnel si prefieres usar un dominio personalizado.

### 4 — Instala la aplicación Android

Descarga el APK desde [la última release](https://github.com/joshtech90/PocketClot/releases) o constrúyelo tú mismo:

```bash
cd app && ./gradlew assembleDebug
adb install app/build/outputs/apk/debug/app-debug.apk
```

Abre la aplicación → **Añadir perfil** → introduce tu URL + la contraseña inicial de administrador (impresa en el primer arranque del servidor en `/opt/pocket-claude/data/INITIAL_PASSWORD.txt`). Cambia la contraseña al primer inicio de sesión.

### 5 — (Opcional) Usa la interfaz web en lugar de la aplicación

Simplemente abre la URL de tu túnel en cualquier navegador. La interfaz web se sirve desde el mismo proceso FastAPI.

Configuración completa incluyendo la ruta de Cloudflare, migración host-a-host, flujo de actualización diaria y resolución de problemas: **[`server/deploy/README.md`](../../server/deploy/README.md)**.

## Multiusuario

Después del primer arranque, se crea un usuario `Admin` y la contraseña inicial se escribe en `/opt/pocket-claude/data/INITIAL_PASSWORD.txt`. Usa la pantalla **Usuarios** en la aplicación (solo admin) para añadir más usuarios — cada uno obtiene sus propias conversaciones, ajustes y claves de API, todo funcionando a través de tu única suscripción Pro/Max.

## Lectura en voz alta con TTS

Tres proveedores, seleccionables por usuario:

| Proveedor          | Calidad de voz | Configuración                  | Costo                                            |
|--------------------|----------------|--------------------------------|--------------------------------------------------|
| **Microsoft Edge** | Buena          | ninguna                        | gratis (alojado por Microsoft)                   |
| **Gemini Direct**  | Excelente      | clave de API de AI Studio      | capa gratuita (10 solicitudes/día por clave)     |
| **Google Cloud TTS** | Excelente (Chirp 3 HD) | JSON de cuenta de servicio | 1M caracteres/mes gratis, luego ~$16/M caracteres |

En la aplicación: **Ajustes → Lectura en voz alta → Proveedor** y elige lo que te convenga. Auto-lectura, selectores de voz, velocidad de habla, pool multi-clave para la capa gratuita de Gemini Direct.

## Generación de imágenes (Gemini Nano Banana)

Aporta tu propia clave de API de AI Studio (la capa gratuita es suficiente para uso casual). Pantalla dedicada, galería, compartir a otras aplicaciones, edición imagen a imagen. Deshabilitado en la interfaz si no hay clave configurada.

## Stack técnico

**Servidor.** Python 3.10+, FastAPI, Uvicorn, `sse-starlette` para SSE, aiosqlite, SQLite + FTS5, [`claude-agent-sdk`](https://pypi.org/project/claude-agent-sdk/), `scrypt` (stdlib) para hashing de contraseñas, `pyzipper` para copias de seguridad AES-256, `edge-tts` + SDK de Google Cloud TTS + REST para Gemini Direct.

**Aplicación.** Kotlin 2.0.21, Android Gradle Plugin 8.7.3, compileSdk 35, minSdk 31, Jetpack Compose Material 3 (BOM 2024.12.01), OkHttp + okhttp-sse, DataStore Preferences, Coil 3, AndroidX Media3 (ExoPlayer + MediaSession), `compose-richtext` para Markdown.

**Interfaz web.** JS vanilla, sin paso de build, servida como archivos estáticos desde el mismo proceso FastAPI.

## Hoja de ruta

- [ ] Cliente iOS
- [ ] Despliegue Docker / Docker Compose como alternativa de una línea al script de instalación del sistema
- [ ] Entrada de voz (basada en Whisper) en el lado de la aplicación
- [ ] Presupuestos de herramientas por conversación

## Contribuir

Se aceptan pull requests. Consulta [CONTRIBUTING.md](../../CONTRIBUTING.md) para el flujo de trabajo.

## Licencia

MIT — ver [LICENSE](../../LICENSE).

## Agradecimientos

- [Anthropic](https://www.anthropic.com/) por Claude y la CLI de Claude Code
- [Tailscale](https://tailscale.com/) por hacer que los túneles públicos sin configuración sean gratuitos para uso personal
- [`claude-agent-sdk`](https://github.com/anthropics/claude-agent-sdk-python) por la limpia superficie de invocación de la CLI
- Los equipos de Compose, FastAPI y SQLite
