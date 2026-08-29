"""Bilderzeugung ueber das Modell-Gateway.

Bis August 2026 lief das ueber `generativelanguage.googleapis.com` mit einem
AI-Studio-Schluessel, und jedes Bild kostete Geld. Seit dem 29.08.2026 laeuft es
ueber dasselbe Gateway, an dem auch die Gemini-Chatmodelle haengen, und damit
ueber die vorhandenen Google-Konten: kostenlos, ohne Schluessel in der App.

Moeglich ist das, weil CLIProxyAPI neben dem OpenAI-Pfad auch den echten
Gemini-Pfad `/v1beta/...:generateContent` bedient. Der nimmt exakt denselben
Request entgegen wie die kostenpflichtige Schnittstelle, deshalb bleibt hier
fast alles wie es war. Unterstuetzt weiterhin:

- Text-to-Image  (nur `prompt`)
- Image-to-Image (Editing: `prompt` + 1..n Referenz-Bilder als Inline-Data)
- Aspect-Ratio   (1:1, 16:9, 9:16, 4:3, 3:4 via `imageConfig.aspectRatio`)
- Aufloesung     (1K, 2K, 4K via `imageConfig.imageSize`)
- Mehrere Bilder (jetzt als mehrere Aufrufe, siehe unten)

Ein Unterschied bleibt: `candidateCount > 1` lehnt das Gateway ab
("Only one candidate can be specified in the current model"). Mehrere Varianten
entstehen deshalb durch mehrere Aufrufe nacheinander.

Die Modellwahl ist entfallen: welches Bildmodell es gibt, sagt das Gateway
(`gateways.image_target()`). Fehler werden als `ImageGenError` mit
aussagekraeftiger Message geworfen.
"""
from __future__ import annotations

import asyncio
import base64
import logging
from dataclasses import dataclass

import httpx

from pocket_claude import gateways

log = logging.getLogger(__name__)

# Die Modellwahl liegt beim Gateway, nicht mehr bei uns: es bietet genau die
# Bildmodelle an, fuer die ein Konto eingeloggt ist. Die Liste hier bliebe sonst
# dauerhaft hinter dem zurueck, was wirklich verfuegbar ist.
AVAILABLE_MODELS: list[dict] = []

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

# Obergrenze fuer Bilder pro Werkzeugaufruf. Weil das Gateway nur ein Bild pro
# Anfrage liefert, sind das ebenso viele Aufrufe nacheinander.
MAX_CANDIDATES = 4

# Wieviele Bild-Anfragen duerfen SERVERWEIT gleichzeitig laufen. Bewusst auf
# Modulebene und nicht je Aufruf: sonst waere die Grenze pro Chat-Turn gemeint,
# und zwei gleichzeitige Turns wuerden sie stillschweigend verdoppeln. Genau
# daran haengt aber das Kontingent des Google-Kontos.
_CONCURRENCY = 2
_gate: asyncio.Semaphore | None = None


def _concurrency_gate() -> asyncio.Semaphore:
    """Der gemeinsame Semaphore, beim ersten Bedarf angelegt.

    Nicht auf Modulebene erzeugt: ein Semaphore bindet sich an den Event-Loop,
    der beim Import laeuft, und das muss nicht derselbe sein wie der spaetere
    Betriebs-Loop.
    """
    global _gate
    if _gate is None:
        _gate = asyncio.Semaphore(_CONCURRENCY)
    return _gate


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
    prompt: str,
    model: str | None = None,
    aspect_ratio: str | None = None,
    image_size: str | None = None,
    count: int = 1,
    references: list[ReferenceImage] | None = None,
    timeout: float = 120.0,
) -> list[GeneratedImage]:
    """Erzeugt `count` Bilder aus `prompt`, optional mit `references` als Vorlage.

    Laeuft ueber das Modell-Gateway und damit ueber die dort eingeloggten
    Google-Konten. Wirft `ImageGenError`, wenn gar nichts zustande kommt; kommen
    einzelne der gewuenschten Varianten nicht durch, werden die uebrigen
    trotzdem geliefert.
    """
    if not prompt or not prompt.strip():
        raise ImageGenError("Prompt darf nicht leer sein.")

    target = await gateways.image_target(preferred=(model or "").strip())
    if target is None:
        raise ImageGenError(
            "Bilderzeugung ist auf diesem Server nicht eingerichtet: kein "
            "Gateway meldet ein Bildmodell. Laeuft das Gateway?"
        )
    gw, model_id = target
    count = max(1, min(int(count), MAX_CANDIDATES))

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
        # `candidateCount` bleibt bewusst bei 1: das Gateway lehnt alles andere
        # ab. Mehrere Varianten entstehen unten durch mehrere Aufrufe.
        "generationConfig": {"responseModalities": ["IMAGE"], "candidateCount": 1},
    }
    image_config: dict[str, str] = {}
    if aspect_ratio and aspect_ratio.strip():
        image_config["aspectRatio"] = aspect_ratio.strip()
    if image_size and image_size.strip():
        image_config["imageSize"] = image_size.strip()
    if image_config:
        body["generationConfig"]["imageConfig"] = image_config

    url = f"{gateways.native_base_url(gw)}/models/{model_id}:generateContent"
    headers = {"Content-Type": "application/json"}
    if gw.api_key:
        headers["Authorization"] = f"Bearer {gw.api_key}"

    log.info("image-gen: gateway=%s model=%s aspect=%s size=%s count=%d refs=%d prompt=%r",
             gw.id, model_id, aspect_ratio, image_size, count,
             len(references or []), prompt[:80])

    # Zwei Anfragen gleichzeitig, serverweit. Alle auf einmal provoziert bei
    # Google gern ein Kontingent-Limit, eine nach der anderen dauert unnoetig
    # lange.
    gate = _concurrency_gate()

    async def _one(idx: int) -> tuple[int, list[GeneratedImage] | Exception]:
        async with gate:
            try:
                return idx, await _generate_one(
                    url, headers, body, timeout, aspect_ratio, image_size,
                )
            except ImageGenError as exc:
                return idx, exc

    results = await asyncio.gather(*(_one(i) for i in range(count)))

    images: list[GeneratedImage] = []
    first_error: ImageGenError | None = None
    for idx, res in sorted(results, key=lambda r: r[0]):
        if isinstance(res, Exception):
            if first_error is None and isinstance(res, ImageGenError):
                first_error = res
            continue
        for img in res:
            images.append(GeneratedImage(index=len(images), mime_type=img.mime_type,
                                         data=img.data, text=img.text))

    if not images:
        raise first_error or ImageGenError("Es kam kein Bild zurueck.")
    if first_error is not None:
        log.info("image-gen: %d von %d Varianten erzeugt, Rest fehlgeschlagen: %s",
                 len(images), count, first_error)
    return images


async def _generate_one(
    url: str,
    headers: dict,
    body: dict,
    timeout: float,
    aspect_ratio: str | None,
    image_size: str | None,
) -> list[GeneratedImage]:
    """Ein einzelner Bild-Aufruf inklusive Wiederholung ohne `imageSize`."""

    async def _send(req_body: dict) -> httpx.Response:
        try:
            async with httpx.AsyncClient(timeout=timeout) as cli:
                return await cli.post(url, headers=headers, json=req_body)
        except httpx.TimeoutException as e:
            raise ImageGenError(
                f"Timeout nach {timeout:.0f}s: Bild zu komplex oder Gateway ueberlastet."
            ) from e
        except httpx.RequestError as e:
            raise ImageGenError(f"Netzwerk-Fehler: {e}") from e

    r = await _send(body)

    # Nicht jedes Bildmodell kennt `imageSize`. Dann einmal ohne wiederholen,
    # damit ein Bild in Standardgroesse besser ist als gar keins.
    if r.status_code == 400 and image_size:
        low = r.text.lower()
        if "imagesize" in low or "image_config" in low or "imageconfig" in low:
            log.info("image-gen: Modell kennt imageSize nicht, wiederhole ohne")
            retry = {
                "contents": body["contents"],
                "generationConfig": {
                    "responseModalities": body["generationConfig"]["responseModalities"],
                    "candidateCount": 1,
                },
            }
            if aspect_ratio and aspect_ratio.strip():
                retry["generationConfig"]["imageConfig"] = {
                    "aspectRatio": aspect_ratio.strip()}
            r = await _send(retry)

    if r.status_code >= 400:
        msg = r.text[:400]
        try:
            err = (r.json().get("error") or {})
            msg = err.get("message") or msg
            status = err.get("status") or ""
            if status:
                msg = f"[{status}] {msg}"
        except Exception:
            pass
        log.warning("image-gen HTTP %d: %s", r.status_code, msg)
        if r.status_code == 429:
            raise ImageGenError(
                "Das Bild-Kontingent des Kontos ist gerade erschoepft. "
                "Spaeter nochmal versuchen."
            )
        raise ImageGenError(f"Gateway-Fehler (HTTP {r.status_code}): {msg}")

    try:
        data = r.json()
    except Exception as e:
        raise ImageGenError(f"Antwort konnte nicht geparst werden: {e}") from e

    images = _extract_images(data)
    if not images:
        reasons = [c.get("finishReason") for c in data.get("candidates", [])
                   if c.get("finishReason")]
        raise ImageGenError(
            f"Kein Bild erhalten (Grund: {', '.join(reasons) or 'unbekannt'}). "
            "Haeufig wurde der Prompt blockiert oder das Modell hat nur Text geliefert."
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
    """Config-Info fuers Frontend.

    `models` ist seit dem Umstieg aufs Gateway leer und `default_model` ein
    leerer String: welches Bildmodell laeuft, entscheidet das Gateway. Beide
    Felder bleiben im Schema, damit aeltere App-Staende nicht stolpern.
    """
    return {
        "models": AVAILABLE_MODELS,
        "aspect_ratios": ASPECT_RATIOS,
        "image_sizes": IMAGE_SIZES,
        "max_candidates": MAX_CANDIDATES,
        "default_model": "",
        "default_aspect": "1:1",
        "default_image_size": DEFAULT_IMAGE_SIZE,
    }
