# PocketClot — Android App

Native Android client for [PocketClot](../README.md). Kotlin + Jetpack Compose Material 3, no web wrapper.

For project overview, architecture, and quickstart, see the [top-level README](../README.md).

## What's inside

- **First-run sign-in card** — when no profile exists, the Settings screen renders an inline Server URL + Username + Password form directly. No detour through a separate "+ Add profile" dialog.
- **Multi-profile management** — once at least one profile exists, switch between server accounts, rename, delete, re-login.
- **Per-user Claude backend** — pick **Pro/Max OAuth**, **Anthropic API key**, or **AWS Bedrock** under **Settings → Claude connection**. Switching modes invalidates cached CLI sessions across your conversations automatically.
- **Token-usage widget** — this-month aggregate of input/output/cache tokens under **Settings → Token usage**. Useful for the API-key + Bedrock paths.
- **7 languages** — language picker under **Settings → Appearance → Language**.
- **Lock-screen audio controls** via Media3 ExoPlayer + MediaSession for the TTS read-aloud feature.
- **In-chat search** with spring-to-match, native text selection, copy button on both assistant and user bubbles, ChatGPT-style collapse for long messages.

## Layout

```
app/
├── app/                          The Android module
│   ├── src/main/
│   │   ├── java/de/smartzone/pocketclaude/
│   │   │   ├── MainActivity.kt
│   │   │   ├── data/             Repositories, models, system prompts
│   │   │   ├── ui/               Chat, settings, conversations, images
│   │   │   ├── service/          StreamingService + NotificationHelper
│   │   │   └── ...
│   │   └── res/
│   │       ├── values/strings.xml         English (default)
│   │       ├── values-de/strings.xml      German
│   │       ├── values-es/strings.xml      Spanish
│   │       ├── values-fr/strings.xml      French
│   │       ├── values-pt-rBR/strings.xml  Brazilian Portuguese
│   │       ├── values-zh/strings.xml      Simplified Chinese
│   │       └── values-ja/strings.xml      Japanese
│   └── build.gradle.kts
├── build.gradle.kts
├── settings.gradle.kts
└── gradle/
```

## Build

```bash
cd app
./gradlew assembleDebug
# APK: app/build/outputs/apk/debug/app-debug.apk

# Or directly to a connected device with USB debugging:
./gradlew installDebug
```

## Stack

- **Kotlin 2.0.21**, Android Gradle Plugin 8.7.3, Gradle 8.9
- **Jetpack Compose** Material 3 (BOM 2024.12.01) + Navigation Compose
- **OkHttp + okhttp-sse** for the SSE message stream
- **AndroidX Media3** (ExoPlayer + MediaSession) for TTS playback with lock-screen controls
- **Coil 3** for image loading
- **DataStore Preferences** for settings + locale persistence
- **compose-richtext** for Markdown rendering
- **compileSdk 35**, **minSdk 31** (Android 12+)

## Translations

Strings live in `app/src/main/res/values-XX/strings.xml`. To add a language, copy `values/strings.xml`, translate the contents, and place it in `values-<locale>/strings.xml`. The in-app language picker in **Settings → Appearance → Language** will pick it up automatically.

## License

MIT — see [`../LICENSE`](../LICENSE).
