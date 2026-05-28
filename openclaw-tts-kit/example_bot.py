"""Lauffähiges Mini-Beispiel — zeigt OpenClaw wie alle Teile zusammenspielen.

Basis: python-telegram-bot v20+. Drei Commands:
  /voice     → blendet die 3 Modell-Buttons ein (Chirp / 2.5 Flash / 3.1 Flash)
  /vorlesen <text>   → liest den Text mit dem aktuell gewählten Modell vor
  /vorlesen_youtube <url>  → Stub: Transkript laden + vorlesen (OpenClaw hat
                              dafür schon Logik, hier nur die TTS-Anbindung)

Starten:
    export TELEGRAM_BOT_TOKEN=...
    export OPENCLAW_TTS_CREDENTIALS=/pfad/zur/google_tts_credentials.json
    python example_bot.py
"""
from __future__ import annotations

import io
import logging
import os
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import telegram_buttons as tg
from tts_engine import (
    AVAILABLE_MODELS,
    DEFAULT_MODEL,
    is_configured,
    model_by_id,
    synthesize_chunked,
)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


# --- /voice — Modell-Picker einblenden -------------------------------------
async def cmd_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    current = tg.get_user_model(chat_id)
    await tg.ptb_send_picker(update, ctx, current_model_id=current)


# --- /vorlesen <text> — synthesize & send ----------------------------------
async def cmd_vorlesen(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_configured():
        await update.message.reply_text(
            "Google-TTS-Credentials fehlen. Lade das Service-Account-JSON unter "
            "credentials/google_tts_credentials.json ab oder setze die Env-"
            "Variable OPENCLAW_TTS_CREDENTIALS."
        )
        return

    text = " ".join(ctx.args) if ctx.args else ""
    if not text and update.message.reply_to_message:
        text = update.message.reply_to_message.text or ""
    if not text:
        await update.message.reply_text(
            "Sag mir was ich vorlesen soll: `/vorlesen Hallo Welt` "
            "oder antworte mit `/vorlesen` auf eine Nachricht.",
            parse_mode="Markdown",
        )
        return

    chat_id = update.effective_chat.id
    model_id = tg.get_user_model(chat_id)
    choice = model_by_id(model_id)
    await update.message.reply_text(
        f"Synthese läuft (Modell: {choice.short})…"
    )

    # Stream alle MP3-Chunks in einen Buffer, dann als ein File schicken.
    # Alternative: pro Chunk eine eigene Voice-Nachricht — schneller spürbar,
    # aber im Chat unübersichtlich. Bei langen Texten lohnt's sich.
    buf = io.BytesIO()
    try:
        async for audio_bytes in synthesize_chunked(
            text, model_id=model_id, language_code="de-DE"
        ):
            buf.write(audio_bytes)
    except Exception as exc:
        await update.message.reply_text(f"TTS-Fehler: {exc}")
        return

    buf.seek(0)
    buf.name = "vorlesen.mp3"
    await update.message.reply_voice(voice=buf)


# --- /vorlesen_youtube <url> — Stub für OpenClaws YT-Pipeline ---------------
async def cmd_vorlesen_youtube(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    url = ctx.args[0] if ctx.args else ""
    if not url:
        await update.message.reply_text("Format: /vorlesen_youtube <url>")
        return

    # OpenClaw hat bereits eine Funktion um YT-Transkripte zu holen — die
    # Stelle hier ist NUR die Anbindung an die TTS-Engine. Pseudo:
    #
    #   transcript = await openclaw.fetch_youtube_transcript(url)
    #   await _stream_tts_into_chat(update, transcript)
    #
    transcript = f"[Hier würde OpenClaw das Transkript von {url} laden.]"
    chat_id = update.effective_chat.id
    model_id = tg.get_user_model(chat_id)
    await update.message.reply_text(
        f"YT-Transkript würde mit Modell '{model_by_id(model_id).short}' "
        f"vorgelesen werden. (Stub — Anbindung an OpenClaws YT-Loader fehlt.)"
    )


# --- Callback für die Modell-Buttons ---------------------------------------
async def cb_ttsmodel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await tg.ptb_handle_callback(update, ctx, set_user_model=tg.set_user_model)


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN env-var fehlt.")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("voice", cmd_voice))
    app.add_handler(CommandHandler("vorlesen", cmd_vorlesen))
    app.add_handler(CommandHandler("vorlesen_youtube", cmd_vorlesen_youtube))
    app.add_handler(CallbackQueryHandler(cb_ttsmodel, pattern=r"^ttsmodel:"))

    log.info("OpenClaw-TTS-Bot startet… (Default-Modell: %s)", DEFAULT_MODEL)
    log.info("Verfügbare Modelle:")
    for m in AVAILABLE_MODELS:
        marker = "★" if m.is_free else " "
        log.info("  %s %-40s — %s", marker, m.label,
                 m.price_hint if not m.is_free else "kostenlos")
    app.run_polling()


if __name__ == "__main__":
    main()
