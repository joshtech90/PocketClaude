"""Telegram-Button-Picker für die drei Modell-Optionen.

OpenClaw soll im Chat einen Inline-Keyboard mit drei Buttons einblenden,
über den der User zwischen Chirp (kostenlos) und den zwei kostenpflichtigen
Gemini-Modellen wählt. Die Auswahl wird per-Chat persistiert.

Funktioniert mit zwei verbreiteten Telegram-Bot-Libraries:
  - python-telegram-bot v20+ (async)         → siehe `ptb_handlers`
  - aiogram v3+                               → siehe `aiogram_handlers`

Beide Snippets sind so geschrieben, dass OpenClaw sie als Drop-In einbauen
kann — Storage ist ein einfaches Dict, das gegen Redis/SQLite getauscht
werden kann.
"""
from __future__ import annotations

from typing import Callable

from tts_engine import AVAILABLE_MODELS, DEFAULT_MODEL, model_by_id


# Callback-Data-Prefix für die Picker-Buttons. Telegram erlaubt 64 Bytes pro
# callback_data → wir nutzen ein kurzes Prefix.
CB_PREFIX = "ttsmodel:"


def build_inline_keyboard_rows() -> list[list[dict]]:
    """Roh-Repräsentation des Inline-Keyboards (provider-agnostisch).
    Eine Reihe pro Modell → besser lesbar auf schmalen Telegram-Clients.
    """
    rows = []
    for m in AVAILABLE_MODELS:
        rows.append([{
            "text": m.label,
            "callback_data": f"{CB_PREFIX}{m.id}",
        }])
    return rows


# ----------------------------------------------------------------------------
# python-telegram-bot (PTB) v20+ Integration
# ----------------------------------------------------------------------------

def ptb_keyboard():
    """Returns telegram.InlineKeyboardMarkup für PTB v20+."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    rows = [
        [InlineKeyboardButton(m.label, callback_data=f"{CB_PREFIX}{m.id}")]
        for m in AVAILABLE_MODELS
    ]
    return InlineKeyboardMarkup(rows)


async def ptb_send_picker(update, context, *, current_model_id: str | None = None):
    """Schickt die Auswahl-Buttons in den Chat.
    Aufruf z.B. aus einem /voice-CommandHandler:

        async def cmd_voice(update, context):
            await ptb_send_picker(update, context,
                                  current_model_id=user_prefs.get(chat_id))
    """
    cur = model_by_id(current_model_id)
    text = (
        "Welches TTS-Modell soll ich nutzen?\n"
        f"Aktuell: *{cur.short}* ({'kostenlos' if cur.is_free else cur.price_hint})"
    )
    await update.effective_chat.send_message(
        text,
        reply_markup=ptb_keyboard(),
        parse_mode="Markdown",
    )


async def ptb_handle_callback(update, context, *,
                              set_user_model: Callable[[int, str], None] | None = None):
    """Verarbeitet den Button-Click. `set_user_model(chat_id, model_id)` ist
    der Storage-Hook in OpenClaws bestehende User-Settings-Logik.

    Hookup im Application-Setup:

        app.add_handler(CallbackQueryHandler(
            lambda u, c: ptb_handle_callback(u, c, set_user_model=save_pref),
            pattern=r"^ttsmodel:"
        ))
    """
    q = update.callback_query
    await q.answer()  # Spinner aus
    if not q.data or not q.data.startswith(CB_PREFIX):
        return
    new_model_id = q.data[len(CB_PREFIX):]
    choice = model_by_id(new_model_id)
    if set_user_model is not None:
        set_user_model(q.message.chat.id, choice.id)
    confirm = (
        f"Modell gewechselt: *{choice.short}*\n"
        f"{'Kostenlos (1 Mio Zeichen/Monat Free-Tier)' if choice.is_free else choice.price_hint}"
    )
    await q.edit_message_text(confirm, parse_mode="Markdown")


# ----------------------------------------------------------------------------
# aiogram v3 Integration
# ----------------------------------------------------------------------------

def aiogram_keyboard():
    """Returns aiogram InlineKeyboardMarkup für aiogram v3+."""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup  # type: ignore
    rows = [
        [InlineKeyboardButton(text=m.label, callback_data=f"{CB_PREFIX}{m.id}")]
        for m in AVAILABLE_MODELS
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def aiogram_send_picker(message, *, current_model_id: str | None = None):
    """`message` = aiogram.types.Message. Aufruf z.B. aus einem /voice-Handler."""
    cur = model_by_id(current_model_id)
    text = (
        "Welches TTS-Modell soll ich nutzen?\n"
        f"Aktuell: *{cur.short}* ({'kostenlos' if cur.is_free else cur.price_hint})"
    )
    await message.answer(text, reply_markup=aiogram_keyboard(), parse_mode="Markdown")


async def aiogram_handle_callback(
    callback,
    *,
    set_user_model: Callable[[int, str], None] | None = None,
):
    """`callback` = aiogram.types.CallbackQuery. Im Router:

        @router.callback_query(F.data.startswith("ttsmodel:"))
        async def cb_ttsmodel(c: CallbackQuery):
            await aiogram_handle_callback(c, set_user_model=save_pref)
    """
    await callback.answer()
    if not callback.data or not callback.data.startswith(CB_PREFIX):
        return
    new_model_id = callback.data[len(CB_PREFIX):]
    choice = model_by_id(new_model_id)
    if set_user_model is not None:
        set_user_model(callback.message.chat.id, choice.id)
    confirm = (
        f"Modell gewechselt: *{choice.short}*\n"
        f"{'Kostenlos (1 Mio Zeichen/Monat Free-Tier)' if choice.is_free else choice.price_hint}"
    )
    await callback.message.edit_text(confirm, parse_mode="Markdown")


# ----------------------------------------------------------------------------
# In-Memory User-Model-Storage (Drop-In Default — gegen Redis/SQLite tauschen)
# ----------------------------------------------------------------------------

_user_model: dict[int, str] = {}


def get_user_model(chat_id: int) -> str:
    """Liefert die User-Wahl oder DEFAULT_MODEL (Chirp)."""
    return _user_model.get(chat_id, DEFAULT_MODEL)


def set_user_model(chat_id: int, model_id: str) -> None:
    """Speichert die User-Wahl. Validiert dass model_id bekannt ist."""
    _user_model[chat_id] = model_by_id(model_id).id
