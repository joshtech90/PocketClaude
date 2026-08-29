# Contributing to PocketClot

Thanks for wanting to help. This is a small hobby project, so the process is light: open an issue, send a PR, keep diffs focused.

## Quick orientation

- `server/` — Python FastAPI backend + built-in web UI
- `app/` — Android client (Kotlin + Jetpack Compose)
- `docs/i18n/` — translated READMEs
- `assets/` — logo + screenshots

For the architecture overview, read the [top-level README](README.md). For the deployment-specific details, read [`server/deploy/README.md`](server/deploy/README.md).

## Adding a new language

There are three places to touch. **All three should land in a single PR** so the language is consistent end-to-end.

### 1. Android app

Copy the default English strings file and translate the contents:

```bash
cp app/app/src/main/res/values/strings.xml \
   app/app/src/main/res/values-<locale>/strings.xml
```

Use Android's locale qualifier syntax: `values-fr/`, `values-es/`, `values-pt-rBR/`, `values-zh/`, etc. Translate the `<string>` *contents* only — keep the `name="..."` keys exactly as in `values/strings.xml`. Format specifiers like `%1$s` stay verbatim, but you may move them within the sentence as natural in your language.

Then add the language to the picker in `app/app/src/main/java/de/smartzone/pocketclaude/data/LocalePrefs.kt` (add the BCP-47 tag to `SUPPORTED`) and to the dropdown in `SettingsScreen.kt` → `LanguageCard()`.

Verify with `cd app && ./gradlew assembleDebug` — Android's resource compiler will complain about missing format specifiers or unescaped apostrophes.

### 2. Web UI

In `server/pocket_claude/webui/i18n.js`, add your locale code to `SUPPORTED_LOCALES`, then add a translation dictionary alongside `en`, `de`, etc. Use the same keys as the English dictionary. Add a `<option>` for the locale to the language picker in `server/pocket_claude/webui/index.html` (Settings → Language section).

### 3. README

Copy `README.md` and translate. Save as `docs/i18n/README.<locale>.md`. Update the language switcher at the top of every README (English original and all translations) to include your new language. Use the same relative-path style as existing translations.

Add the new language to the README highlights line ("7 languages" → "8 languages").

## Code style

- **Don't add features outside the scope of the PR.** A translation PR translates; an iOS PR builds the iOS client. Refactors get their own PR.
- **Don't add comments that just repeat what the code does.** Good identifiers replace most comments. Only comment the *why* when it isn't obvious (workaround for a specific bug, non-obvious invariant, surprising platform behavior).
- **Android:** follow the patterns already in the codebase — Compose Material 3, DataStore for prefs, OkHttp for networking. No Hilt.
- **Server:** Python 3.10+, FastAPI, type hints. Don't add a new dependency without checking what we already have.

## Pull-request workflow

1. **Open an issue first** to discuss scope, especially for anything bigger than a translation or a one-file fix.
2. Branch from `main`, keep the diff focused on one logical change.
3. Run the relevant build before pushing:
   - Server: `cd server && python -m pocket_claude` (smoke-test locally)
   - App: `cd app && ./gradlew assembleDebug`
4. Open the PR against `main`. Use the template (it auto-loads).
5. Describe **what** and **why**; how-tested is enough on the verification side.

## Bug reports

Please include:
- What you did (steps to reproduce)
- What you expected
- What happened
- Server: relevant lines from `journalctl -u pocket-claude` or the local log
- App: device + Android version, plus the stack trace from `adb logcat | grep -i pocket`

## Code of conduct

Be kind. This is a hobby project; people contribute on their own time.

## License

By submitting a PR you agree that your contribution is licensed under the [MIT License](LICENSE).
