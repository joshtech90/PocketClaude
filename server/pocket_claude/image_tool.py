"""Tool-Definition und Ausfuehrung fuer die Bildgenerierung (generate_image).

Wird sowohl im Claude-Pfad (via In-Process MCP) als auch im Gateway-Pfad
(OpenAI-kompatible Tool Calls) verwendet.
"""
from __future__ import annotations

import asyncio
import logging
import secrets
from typing import Any

from pocket_claude import db, image_engine
from pocket_claude.config import settings

log = logging.getLogger(__name__)

TOOL_NAME = "generate_image"

TOOL_DESCRIPTION = (
    "Erzeugt ein Bild aus einer Bildbeschreibung und zeigt es direkt im Chat. "
    "Nutze das Werkzeug, wenn der Nutzer ein Bild, eine Illustration, ein Logo, "
    "ein Icon oder eine Grafik moechte. Die Beschreibung sollte ausfuehrlich "
    "und auf Englisch sein, das liefert bessere Ergebnisse."
)

# Die Aufloesung steht bewusst NICHT im Schema: sie ist eine Nutzer-Einstellung
# (Einstellungen, Abschnitt Bilder), keine Entscheidung des Modells. Sonst
# wuerde jedes Modell nach Lust und Laune eine andere Groesse waehlen und die
# eingestellte Vorgabe waere wertlos. Seitenverhaeltnis und Anzahl darf das
# Modell dagegen selbst waehlen, das haengt am Bildinhalt.
PARAMETERS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "prompt": {
            "type": "string",
            "description": (
                "Ausfuehrliche Bildbeschreibung, am besten auf Englisch: Motiv, "
                "Stil, Licht, Perspektive, Hintergrund."
            ),
        },
        "aspect_ratio": {
            "type": "string",
            "enum": ["1:1", "16:9", "9:16", "4:3", "3:4"],
            "description": "Seitenverhaeltnis. Ohne Angabe gilt die Nutzer-Vorgabe.",
        },
        "count": {
            "type": "integer",
            "minimum": 1,
            "maximum": 4,
            "description": "Anzahl Varianten. Ohne Angabe eine.",
        },
    },
    "required": ["prompt"],
}


async def store_images(images: list[image_engine.GeneratedImage], user_id: str) -> list[dict]:
    """Speichert generierte Bilder auf der Festplatte und registriert sie in der DB.

    Uebernommen aus der Endpoint-Logik von server.py:
    - Zufalls-Dateiname mit secrets.token_urlsafe(10)
    - Dateiendung aus mime_type
    - Speicherung im konfigurierten uploads_dir (via asyncio.to_thread)
    - Attachment-Eintrag in der Datenbank

    Rueckgabe je Bild: dict mit id, filename, mime_type, size_bytes, text.
    """
    out_atts: list[dict] = []
    for img in images:
        ext = "png" if "png" in img.mime_type else (img.mime_type.split("/")[-1] or "bin")
        disk_name = f"img_{secrets.token_urlsafe(10)}.{ext}"
        target = settings.uploads_dir / disk_name
        await asyncio.to_thread(target.write_bytes, img.data)
        filename = f"gemini-image-{img.index + 1}.{ext}"
        aid = await db.add_attachment(
            filename=filename,
            mime_type=img.mime_type,
            size_bytes=len(img.data),
            path=target,
            user_id=user_id,
        )
        out_atts.append({
            "id": aid,
            "filename": filename,
            "mime_type": img.mime_type,
            "size_bytes": len(img.data),
            "text": img.text,
        })
    return out_atts


async def run(user_id: str, args: dict, defaults: dict | None = None) -> dict:
    """Fuehrt die Bildgenerierung fuer das Tool aus und speichert die Ergebnisse.

    Prioritaet: args vor defaults vor Modul-Defaults.
    Rueckgabe: {"ok": bool, "attachments": [...], "text": str}
    """
    defaults = defaults or {}

    prompt = (args.get("prompt") or "").strip()
    if not prompt:
        return {
            "ok": False,
            "attachments": [],
            "text": "Kein Prompt fuer die Bildgenerierung angegeben.",
        }

    aspect_ratio = (
        args.get("aspect_ratio")
        or defaults.get("aspect_ratio")
        or defaults.get("image_default_aspect")
        or "1:1"
    )
    # Aufloesung kommt IMMER aus den Nutzer-Einstellungen, nie vom Modell.
    size = (
        defaults.get("size")
        or defaults.get("image_default_size")
        or image_engine.DEFAULT_IMAGE_SIZE
    )
    model = (
        args.get("model")
        or defaults.get("model")
        or defaults.get("image_default_model")
        or None
    )

    try:
        raw_count = args.get("count") if args.get("count") is not None else defaults.get("count")
        count_val = int(raw_count) if raw_count is not None else 1
    except (TypeError, ValueError):
        count_val = 1

    # Kein Schluessel mehr noetig: die Bilder entstehen ueber das Gateway und
    # damit ueber die dort eingeloggten Google-Konten.
    try:
        images = await image_engine.generate(
            prompt=prompt,
            model=model,
            aspect_ratio=aspect_ratio,
            image_size=size,
            count=count_val,
        )
    except image_engine.ImageGenError as e:
        return {
            "ok": False,
            "attachments": [],
            "text": f"Fehler bei der Bildgenerierung: {e}",
        }
    except Exception as e:
        log.exception("Unerwarteter Fehler bei generate_image")
        return {
            "ok": False,
            "attachments": [],
            "text": f"Unerwarteter Fehler bei der Bildgenerierung: {e}",
        }

    # Speichern kann auch schiefgehen (Platte voll, Verzeichnis nicht
    # beschreibbar, DB-Fehler). Das darf NICHT als Exception aus dem Werkzeug
    # herausfallen, sonst kippt der ganze Chat-Turn.
    try:
        attachments = await store_images(images, user_id=user_id)
    except Exception as e:  # noqa: BLE001
        log.exception("Bilder konnten nicht gespeichert werden")
        return {
            "ok": False,
            "attachments": [],
            "text": f"Die Bilder konnten nicht gespeichert werden: {e}",
        }

    count_done = len(attachments)
    if count_done == 1:
        summary = (
            "1 Bild wurde erfolgreich generiert und dem Nutzer bereits im Chat angezeigt. "
            "Erfinde keinen Markdown-Bild-Link oder Dateipfad im Text."
        )
    else:
        summary = (
            f"{count_done} Bilder wurden erfolgreich generiert und dem Nutzer bereits im Chat angezeigt. "
            "Erfinde keine Markdown-Bild-Links oder Dateipfade im Text."
        )

    return {
        "ok": True,
        "attachments": attachments,
        "text": summary,
    }
