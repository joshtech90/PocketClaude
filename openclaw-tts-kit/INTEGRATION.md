# Integration in OpenClaw — Schritt-für-Schritt

Dieses Dokument richtet sich an den OpenClaw-Agenten selbst (Stand: Mai 2026):
hier ist die Liste der Eingriffe, die in OpenClaws bestehenden Code zu machen
sind, damit das TTS-Kit produktiv läuft.

## 0. Voraussetzungen

- OpenClaw läuft bereits auf Telegram (Token vorhanden, Bot reagiert)
- Python ≥ 3.10
- Google-Cloud-Account mit aktiviertem Billing (Setup-Anleitung in
  `credentials/README.md`)

## 1. Files in OpenClaws Codebase einbinden

Variante A — als Submodul/Package:
```
openclaw/
├── ...
└── tts_kit/                    ← Kopie dieses Ordners
    ├── tts_engine.py
    ├── telegram_buttons.py
    └── credentials/...
```

Variante B — als externes pip-package (siehe `setup.py` falls als Library
gepackt — aktuell aber direkt-File-Approach am einfachsten).

Imports innerhalb von OpenClaw:
```python
from openclaw.tts_kit import tts_engine
from openclaw.tts_kit import telegram_buttons as tg
```

## 2. User-Pref-Storage anbinden

Der Kit hat ein In-Memory-Dict als Default (`telegram_buttons._user_model`),
das beim Bot-Restart vergessen wird. OpenClaw hat eigene User-Storage —
diese binden:

```python
# in openclaw/handlers/tts.py

from openclaw.db import session_scope  # oder was-auch-immer
from openclaw.tts_kit import tts_engine

def openclaw_save_model(chat_id: int, model_id: str) -> None:
    with session_scope() as s:
        prefs = s.get_or_create(UserPref, chat_id=chat_id)
        prefs.tts_model_id = model_id

def openclaw_load_model(chat_id: int) -> str:
    with session_scope() as s:
        prefs = s.get(UserPref, chat_id=chat_id)
        return (prefs and prefs.tts_model_id) or tts_engine.DEFAULT_MODEL
```

## 3. Commands registrieren

OpenClaw nutzt vermutlich `python-telegram-bot` (PTB) — Snippets sind dafür
geschrieben. Falls aiogram: in `telegram_buttons.py` stehen die aiogram-
Pendants direkt darunter, gleicher Aufbau.

### 3.1 /voice-Command — Picker einblenden

```python
from telegram.ext import CommandHandler, CallbackQueryHandler

async def cmd_voice(update, ctx):
    chat_id = update.effective_chat.id
    current = openclaw_load_model(chat_id)
    await tg.ptb_send_picker(update, ctx, current_model_id=current)

app.add_handler(CommandHandler("voice", cmd_voice))
```

### 3.2 Callback-Handler für die Buttons

```python
async def cb_ttsmodel(update, ctx):
    await tg.ptb_handle_callback(
        update, ctx, set_user_model=openclaw_save_model,
    )

app.add_handler(CallbackQueryHandler(cb_ttsmodel, pattern=r"^ttsmodel:"))
```

### 3.3 Bestehende Vorlese-Funktion an die Engine anbinden

OpenClaw hat bereits Code wie `read_youtube_transcript(url) -> str` und
`read_text(text) -> str`. Den TTS-Output-Punkt umstellen auf das Kit:

```python
import io
from openclaw.tts_kit import tts_engine

async def speak(update, text: str) -> None:
    chat_id = update.effective_chat.id
    model_id = openclaw_load_model(chat_id)

    buf = io.BytesIO()
    try:
        async for chunk in tts_engine.synthesize_chunked(
            text,
            model_id=model_id,
            language_code="de-DE",
        ):
            buf.write(chunk)
    except RuntimeError as e:
        # Konfig-Fehler (Billing, Permission) — User-freundliche Meldung
        await update.message.reply_text(f"TTS-Fehler: {e}")
        return

    buf.seek(0)
    buf.name = "openclaw_voice.mp3"
    await update.message.reply_voice(voice=buf)
```

`synthesize_chunked` ist ein AsyncIterator — du kannst die Chunks auch
einzeln rausschicken (mehrere `reply_voice`-Calls), aber für Telegram-UX ist
„alles in einer Voice-Nachricht" angenehmer.

## 4. Default-Verhalten überprüfen

Der Default ist Chirp. Das bedeutet:
- Ein neuer User, der gar nichts wählt, bekommt automatisch Chirp.
- `openclaw_load_model(chat_id)` ohne gespeicherte Wahl → `MODEL_CHIRP`.
- Wenn der User `/voice` aufruft, ist „Chirp (kostenlos)" als „Aktuell"-
  Hinweis im Picker-Text markiert.

## 5. Testlauf

1. Service-Account-JSON in `tts_kit/credentials/google_tts_credentials.json`
   ablegen (`chmod 600`).
2. Bot starten, in Telegram `/voice` schicken → 3 Buttons müssen kommen.
3. Default „Chirp (kostenlos)" auswählen → Confirm-Nachricht „Modell
   gewechselt: Chirp 3 HD" erscheint.
4. `/vorlesen Hallo Welt` → Voice-Nachricht kommt zurück, klingt natürlich-
   männlich, deutsch.
5. `/voice` erneut → auf „Gemini 2.5 Flash (kostenpflichtig)" wechseln,
   nochmal `/vorlesen Hallo Welt` → leicht anderer Klang (gleicher Sprecher
   „Algenib", aber Gemini-Inferenz).

## 6. Migration / Rollout

Falls OpenClaw aktuell schon TTS hat (anderer Provider) und du auf das Kit
umstellst:

- Bestehende User behalten ihre voice_settings einfach ohne `tts_model_id` —
  `openclaw_load_model()` returnt dann Default (Chirp), keine Disruption.
- Wenn jemand einen anderen Provider gewohnt war: einmaliges Onboarding-
  Banner mit Hinweis auf das `/voice`-Command einblenden.

## 7. Monitoring

`tts_engine` loggt:
- pro Synthese: `tts: synthesizing N chars model=X lang=Y rate=Z`
- pro Chunk-Stream: `TTS-Stream: model=X chunks=N concurrency=50 ...`
- pro Chunk-Ready: `TTS-Stream: chunk i/N ready (B bytes)`

Wenn OpenClaw zentralen Logger hat: das `tts_engine`-Logger-Modul ist
`tts_engine`, lässt sich per `logging.getLogger("tts_engine").setLevel(INFO)`
in OpenClaws Log-Pipeline einklinken.

## 8. Bekannte Edge-Cases

- **Sehr lange YouTube-Videos** (>30 min Transkript ≈ 30k Zeichen):
  funktioniert; das Kit cappt bei 100k Zeichen sicherheitshalber. Chunking
  produziert dann ~150 Chunks à 200 Zeichen, alle parallel — Cloud-TTS macht
  bei 50 Concurrency-Slots ≈ 3 Wellen. Time-to-First-Audio bleibt unter 2s.
- **Texte mit viel Code/Markdown**: `strip_for_tts()` killt Code-Blocks,
  Bilder, URLs, Emojis vor der Synthese — das willst du auch (sonst werden
  Backticks und URLs einzeln vorgelesen).
- **Cloud-TTS-Limit erreicht** (1M Zeichen Chirp/Monat): API gibt 429,
  der Aufruf raised. OpenClaw sollte dem User dann anbieten, auf
  Gemini 2.5 Flash zu switchen.
