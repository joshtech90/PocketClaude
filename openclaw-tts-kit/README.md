# OpenClaw TTS Kit

Drop-In TTS-Modul für den OpenClaw-Telegram-Agenten — abgeleitet aus dem
PocketClaude-Server (Stand Mai 2026). Macht aus jedem Text (inkl. langer
YouTube-Transkripte) eine vorgelesene Audio-Antwort, mit:

- **Chirp 3 HD** als kostenfreiem Default (1 Mio Zeichen/Monat free über Cloud TTS),
- optional **Gemini 2.5 Flash TTS** und **Gemini 3.1 Flash TTS** als
  kostenpflichtige Premium-Optionen,
- **dynamischem Chunking** (Balanced-DP + Fast-Start-Chunk) für minimale
  Time-to-First-Audio bei langen Texten,
- **Telegram-Inline-Buttons** für den User zum Modell-Wechsel im Chat.

## Inhalt

```
openclaw-tts-kit/
├── tts_engine.py           # Core: synthesize, synthesize_chunked, Chunking
├── telegram_buttons.py     # Picker-Buttons (python-telegram-bot + aiogram)
├── example_bot.py          # Lauffähiges Mini-Beispiel
├── requirements.txt        # google-cloud-texttospeech + python-telegram-bot
├── credentials/
│   ├── README.md           # Service-Account-Setup-Anleitung
│   └── google_tts_credentials.json   # ← hier dein SA-JSON ablegen
└── README.md               # diese Datei
```

## 5-Minuten-Quickstart

```bash
pip install -r requirements.txt

# Service-Account-JSON unter credentials/google_tts_credentials.json ablegen
# (Setup-Doku: credentials/README.md)

export TELEGRAM_BOT_TOKEN=<dein-bot-token>
python example_bot.py
```

In Telegram:

```
/voice                       → blendet die 3 Modell-Buttons ein
/vorlesen Hallo Welt         → liest mit dem aktuell gewählten Modell vor
/vorlesen_youtube <url>      → OpenClaw-Hook: Transkript laden + vorlesen
```

## Die drei Modelle

| Modell                       | Preis                                   | Wann nutzen |
|------------------------------|-----------------------------------------|-------------|
| **Chirp 3 HD** (Default)     | 1 Mio Zeichen/Monat gratis, danach $30/M | Alltag, lange YT-Videos — die User-Voreinstellung |
| **Gemini 2.5 Flash TTS**     | $0.50/M Input + $10/M Audio-Output      | Bessere Prosodie, leicht ausdrucksstärker |
| **Gemini 3.1 Flash TTS**     | $1/M Input + $20/M Audio-Output         | Neueste Generation, am natürlichsten klingend |

Alle drei nutzen denselben Sprecher („Algenib", männlich, deutsch) — der User
kann zwischen ihnen wechseln ohne Voice-Drift zu hören. Internes Voice-Mapping
ist in `tts_engine.py` hart verdrahtet.

## Wie OpenClaw das einbaut

### 1. Modul-Import

```python
from tts_engine import synthesize_chunked, model_by_id, DEFAULT_MODEL
import telegram_buttons as tg
```

### 2. /voice-Command für den Picker

```python
@app.handler("/voice")
async def voice_cmd(update, ctx):
    current = tg.get_user_model(update.effective_chat.id)
    await tg.ptb_send_picker(update, ctx, current_model_id=current)

# Callback-Handler für die Buttons
app.add_handler(CallbackQueryHandler(
    lambda u, c: tg.ptb_handle_callback(u, c,
                                        set_user_model=openclaw_save_pref),
    pattern=r"^ttsmodel:",
))
```

`openclaw_save_pref(chat_id, model_id)` ist OpenClaws bestehende User-Settings-
Logik (Redis/SQLite/whatever) — das Kit hat dafür einen In-Memory-Stub
(`telegram_buttons.set_user_model`), den ihr 1:1 austauschen könnt.

### 3. Beim Vorlesen das gewählte Modell durchreichen

```python
async def read_aloud(update, text):
    chat_id = update.effective_chat.id
    model_id = openclaw_load_pref(chat_id) or DEFAULT_MODEL

    buf = io.BytesIO()
    async for chunk in synthesize_chunked(text, model_id=model_id,
                                          language_code="de-DE"):
        buf.write(chunk)
    buf.seek(0)
    buf.name = "audio.mp3"
    await update.message.reply_voice(voice=buf)
```

Das `synthesize_chunked` streamt MP3-Chunks in Reihenfolge — bei einem langen
YT-Transkript ist der erste Chunk in ~1.5s da (Fast-Start), während die
folgenden parallel im Hintergrund synthetisiert werden. Wenn ihr die Chunks
NICHT puffern wollt sondern als Stream weiterleiten: einfach `async for` direkt
in `bot.send_audio_streaming(...)` durchreichen (Telegram unterstützt das aber
nur über `editMessageMedia`, der einfache Weg ist „alle Bytes sammeln und einmal
schicken").

## Dynamisches Chunking — was passiert da

`synthesize_chunked()` ruft intern `split_into_chunks()` auf, das den Eingangstext
mit zwei Strategien zerlegt:

1. **Fast-Start-Chunk** (≤80 Zeichen, erster Satz oder dessen erster Teilsatz)
   — geht *zuerst* an die TTS-API, ist als erstes wieder da. Der User hört
   Audio bevor der Rest fertig ist.
2. **Balanced-DP für den Rest** — probiert verschiedene Chunk-Caps zwischen
   200 und 500 Zeichen durch und wählt die Partition, die unter
   Wave-Bedingungen (max 50 parallele Calls) die kürzeste Wallclock-Zeit
   ergibt. Vermeidet sowohl Mini-Rest-Chunks am Ende als auch unnötig viele
   Chunks bei sehr langen Texten.

Beide Strategien wurden in PocketClaude empirisch getuned — für deutsche
Texte mit Gemini-TTS sind die Defaults gut.

## Bekannte Stolpersteine

- **Billing nicht aktiv** → `RuntimeError: Cloud-TTS: Billing für das Cloud-
  Projekt aktivieren …`. Cloud Console → Billing → My Projects → Projekt
  verknüpfen.
- **Gemini-Voice ohne Vertex AI** → `RuntimeError: …Gemini-Voices brauchen
  aktive Vertex AI / Agent Platform API…`. APIs & Services → Library →
  `Vertex AI API` aktivieren.
- **Permission denied** → Service-Account hat nicht die Rolle
  `Cloud Text-to-Speech User` (für Chirp) bzw. zusätzlich `Vertex AI User`
  (für Gemini-Voices).

## Was NICHT im Kit ist (bewusst weggelassen)

- **Multi-API-Key-Pool** (PocketClaude hat das für Gemini-Direct-API-Free-Tier)
  — OpenClaw nutzt den Cloud-TTS-Pfad mit einem einzigen Service-Account, daher
  unnötig.
- **Edge-TTS** (Microsoft) — PocketClaud hat das als 3. Provider, hier nicht
  vorgesehen weil User explizit Chirp + Gemini Flash will.
- **Multi-User-Auth / Rate-Limiting** — OpenClaw hat seine eigenen Mechanismen.
- **Caching** — OpenClaw entscheidet selbst, ob/wo Audio-Files gecached werden.
  Die Engine returnt rohe MP3-Bytes, der Caller kann sie speichern wie er mag.

## Lizenz / Herkunft

Extrahiert aus `~/Projects/PocketClaude/server/pocket_claude/tts.py` (Joschas
PocketClaude-Server, Mai 2026). Frei zur Nutzung in OpenClaw.
