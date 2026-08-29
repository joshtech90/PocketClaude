"""Google Gemini Image Generation (Nano Banana).

Direkter REST-Aufruf an `generativelanguage.googleapis.com`, kein extra Package
noetig. Unterstuetzt:

- Text-to-Image  (nur `prompt`)
- Image-to-Image (Editing: `prompt` + 1..n Referenz-Bilder als Inline-Data)
- Aspect-Ratio   (1:1, 16:9, 9:16, 4:3, 3:4 via `imageConfig.aspectRatio`)
- Aufloesung     (1K, 2K, 4K via `imageConfig.imageSize`)
- Mehrere Output-Bilder pro Call (`candidateCount`)
- Modell-Wahl   (Nano-Banana 2.5 / 3.1 preview)

Liefert eine Liste von `GeneratedImage`-Objekten (bytes + mime_type + index).
Fehler werden als `ImageGenError` mit aussagekraeftiger Message geworfen.
"""
from __future__ import annotations

import base64
import logging
from dataclasses import dataclass

import httpx

log = logging.getLogger(__name__)

# Modelle die wir anbieten. Modellnamen via ListModels-Endpoint verifiziert.
# Nano Banana = Gemini-Image. Pro = beste Qualitaet, Flash = schneller.
AVAILABLE_MODELS: list[dict] = [
    {
        "id": "gemini-3.1-flash-image-preview",
        "label": "Nano Banana 2 (Gemini 3.1 Flash Image)",
        "default": True,
        "description": "Aktuellster Flash: sehr gute Qualitaet, schnell. Beste Allround-Wahl.",
    },
    {
        "id": "gemini-3-pro-image-preview",
        "label": "Nano Banana Pro (Gemini 3 Pro Image)",
        "default": False,
        "description": "Hoechste Qualitaet: Photo-Realismus, komplexe Komposition. Langsamer und teurer.",
    },
    {
        "id": "gemini-2.5-flash-image",
        "label": "Nano Banana (Gemini 2.5 Flash Image)",
        "default": False,
        "description": "Stabile Vorversion. Guenstigste Option, immer noch sehr gute Qualitaet.",
    },
]

ASPECT_RATIOS: list[dict] = [
    {"id": "1:1",  "label": "Quadrat (1:1)"},
    {"id": "16:9", "label": "Querformat (16:9)"},
    {"id": "9:16", "label": "Hochformat (9:16)"},
    {"id": "4:3",  "label": "Foto Quer (4:3)"},
    {"id": "3:4",  "label": "Foto Hoch (3:4)"},
]

IMAGE_SIZES: list[dict] = [
    {"id": "1K", "label": "Standard (1K)"},
    {"id": "2K", "label": "Hoch (2K)"},
    {"id": "4K", "label": "Sehr hoch (4K)"},
]

DEFAULT_IMAGE_SIZE = "2K"

MAX_CANDIDATES = 4  # Anzahl Bilder pro Call: Gemini cappt bei 4

API_BASE = "https://generativelanguage.googleapis.com/v1beta"


class ImageGenError(RuntimeError):
    """Generations-Fehler. Frontend zeigt `str(e)` direkt an."""


@dataclass
class GeneratedImage:
    index: int           # 0..n innerhalb dieses Calls
    mime_type: str       # i.d.R. "image/png"
    data: bytes          # rohe Bild-Bytes
    text: str | None = None  # falls das Modell Text zusaetzlich produziert hat


@dataclass
class ReferenceImage:
    """Input-Bild fuer Editing/Variations."""
    mime_type: str
    data: bytes


async def generate(
    *,
    api_key: str,
    prompt: str,
    model: str | None = None,
    aspect_ratio: str | None = None,
    image_size: str | None = None,
    count: int = 1,
    references: list[ReferenceImage] | None = None,
    timeout: float = 90.0,
) -> list[GeneratedImage]:
    """Generiert `count` Bilder aus `prompt` (optional mit `references` als
    Edit-Input). Wirft `ImageGenError` bei Problemen."""
    if not api_key or not api_key.strip():
        raise ImageGenError("Kein Gemini-API-Key gesetzt: bitte in Einstellungen eintragen.")
    if not prompt or not prompt.strip():
        raise ImageGenError("Prompt darf nicht leer sein.")

    model = (model or AVAILABLE_MODELS[0]["id"]).strip()
    count = max(1, min(int(count), MAX_CANDIDATES))

    # Request-Body bauen
    parts: list[dict] = [{"text": prompt.strip()}]
    for ref in references or []:
        parts.append({
            "inlineData": {
                "mimeType": ref.mime_type,
                "data": base64.b64encode(ref.data).decode("ascii"),
            }
        })

    body: dict = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "candidateCount": count,
        },
    }

    image_config: dict[str, str] = {}
    if aspect_ratio and aspect_ratio.strip():
        image_config["aspectRatio"] = aspect_ratio.strip()
    if image_size and image_size.strip():
        image_config["imageSize"] = image_size.strip()
    if image_config:
        body["generationConfig"]["imageConfig"] = image_config

    url = f"{API_BASE}/models/{model}:generateContent"

    log.info(
        "image-gen: model=%s aspect=%s size=%s count=%d refs=%d prompt=%r",
        model, aspect_ratio, image_size, count, len(references or []), prompt[:80],
    )

    async def _send_request(req_body: dict) -> httpx.Response:
        try:
            async with httpx.AsyncClient(timeout=timeout) as cli:
                return await cli.post(
                    url,
                    params={"key": api_key},
                    headers={"Content-Type": "application/json"},
                    json=req_body,
                )
        except httpx.TimeoutException as e:
            raise ImageGenError(f"Timeout nach {timeout:.0f}s: Bild zu komplex oder API ueberlastet.") from e
        except httpx.RequestError as e:
            raise ImageGenError(f"Netzwerk-Fehler: {e}") from e

    r = await _send_request(body)

    # Retry ohne imageSize bei HTTP 400 wenn das Modell imageSize nicht unterstuetzt
    if r.status_code == 400 and image_size:
        err_lower = r.text.lower()
        if "imagesize" in err_lower or "image_config" in err_lower or "imageconfig" in err_lower:
            log.info(
                "image-gen: API meldet Fehler zu imageSize fuer Modell %s, wiederhole ohne imageSize",
                model,
            )
            retry_body = {
                "contents": body["contents"],
                "generationConfig": {
                    "responseModalities": body["generationConfig"]["responseModalities"],
                    "candidateCount": body["generationConfig"]["candidateCount"],
                },
            }
            if aspect_ratio and aspect_ratio.strip():
                retry_body["generationConfig"]["imageConfig"] = {"aspectRatio": aspect_ratio.strip()}
            r = await _send_request(retry_body)

    if r.status_code >= 400:
        # Versuche, die Google-Fehlermeldung lesbar zu machen
        msg = r.text[:400]
        try:
            j = r.json()
            err = j.get("error") or {}
            msg = err.get("message") or msg
            status = err.get("status") or ""
            if status:
                msg = f"[{status}] {msg}"
        except Exception:
            pass
        log.warning("image-gen API %d: %s", r.status_code, msg)
        raise ImageGenError(f"Gemini-API-Fehler (HTTP {r.status_code}): {msg}")

    try:
        data = r.json()
    except Exception as e:
        raise ImageGenError(f"Antwort konnte nicht geparst werden: {e}") from e

    images = _extract_images(data)
    if not images:
        # Manchmal blockt Google den Prompt (Safety): finishReason mitgeben
        finish_reasons = []
        for cand in data.get("candidates", []):
            fr = cand.get("finishReason")
            if fr:
                finish_reasons.append(fr)
        fr_str = ", ".join(finish_reasons) or "unbekannt"
        raise ImageGenError(
            f"Keine Bilder erhalten (finishReason: {fr_str}). "
            "Haeufig: Prompt wurde blockiert (Safety) oder das Modell hat nur Text zurueckgegeben."
        )
    return images


def _extract_images(payload: dict) -> list[GeneratedImage]:
    out: list[GeneratedImage] = []
    for ci, cand in enumerate(payload.get("candidates", [])):
        content = cand.get("content") or {}
        for pi, part in enumerate(content.get("parts", [])):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
                try:
                    raw = base64.b64decode(inline["data"])
                except Exception:
                    continue
                out.append(GeneratedImage(index=ci, mime_type=mime, data=raw,
                                          text=_collect_text(content)))
                break  # ein Bild pro Candidate
    return out


def _collect_text(content: dict) -> str | None:
    texts = [p.get("text") for p in content.get("parts", []) if p.get("text")]
    if not texts:
        return None
    joined = " ".join(t.strip() for t in texts if t.strip())
    return joined or None


def get_config() -> dict:
    """Statische Config-Info fuers Frontend (Modelle, Aspect-Ratios, Bildgroessen, Limits)."""
    return {
        "models": AVAILABLE_MODELS,
        "aspect_ratios": ASPECT_RATIOS,
        "image_sizes": IMAGE_SIZES,
        "max_candidates": MAX_CANDIDATES,
        "default_model": next(m["id"] for m in AVAILABLE_MODELS if m.get("default")),
        "default_aspect": "1:1",
        "default_image_size": DEFAULT_IMAGE_SIZE,
    }
