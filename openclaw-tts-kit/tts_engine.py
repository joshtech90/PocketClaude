"""OpenClaw TTS Engine — Standalone, abgeleitet aus PocketClaude (Mai 2026).

Drei wählbare Modelle über EINEN Pfad (Google Cloud Text-to-Speech mit
Service-Account-JSON):

    MODEL_CHIRP            = "chirp3hd-Algenib"           # KOSTENLOS bis 1M Zeichen/Monat
    MODEL_GEMINI_25_FLASH  = "gemini-2.5-flash-tts"       # kostenpflichtig
    MODEL_GEMINI_31_FLASH  = "gemini-3.1-flash-tts-preview"  # kostenpflichtig (neueste Gen)

Alle drei kommen aus Cloud-TTS und werden auf das $10/Monat-Cloud-Credit des
AI-Pro-Abos abgerechnet (Chirp im Free-Tier, Gemini-Voices darüber). Default ist
Chirp, weil das die User-präferierte „kostenlos genug für Alltag"-Variante ist.

Dynamisches Chunking ist 1:1 aus PocketClaude übernommen (Balanced-DP +
Fast-Start-Chunk für minimale Time-to-First-Audio). Funktioniert für alle drei
Modelle — der Sprecher („Algenib") bleibt zwischen Modellen konsistent.

Streaming-API:
    async for mp3_bytes in synthesize_chunked(text, model_id="chirp3hd-Algenib"):
        await bot.send_voice(chat_id, mp3_bytes)

Single-Shot (für kurze Texte / Datei-Output):
    audio = synthesize(text, model_id="chirp3hd-Algenib")
    Path("out.mp3").write_bytes(audio)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Optional

log = logging.getLogger(__name__)


# ============================================================================
# MODELS — die drei wählbaren Optionen für OpenClaws Telegram-Buttons
# ============================================================================

MODEL_CHIRP = "chirp3hd-Algenib"
MODEL_GEMINI_25_FLASH = "gemini-2.5-flash-tts"
MODEL_GEMINI_31_FLASH = "gemini-3.1-flash-tts-preview"

DEFAULT_MODEL = MODEL_CHIRP


@dataclass(frozen=True)
class ModelChoice:
    id: str
    label: str          # so wie's in den Telegram-Buttons steht
    short: str          # Kurzform fürs Confirm-Display
    is_free: bool
    price_hint: str     # falls kostenpflichtig
    voice_api_id: str   # Voice-Name + Routing-Info


# Reihenfolge entspricht den Telegram-Buttons (links → rechts).
AVAILABLE_MODELS: list[ModelChoice] = [
    ModelChoice(
        id=MODEL_CHIRP,
        label="Chirp (kostenlos)",
        short="Chirp 3 HD",
        is_free=True,
        price_hint="1 Mio Zeichen/Monat gratis, danach $30/M",
        voice_api_id="chirp3hd-Algenib",
    ),
    ModelChoice(
        id=MODEL_GEMINI_25_FLASH,
        label="Gemini 2.5 Flash (kostenpflichtig)",
        short="Gemini 2.5 Flash",
        is_free=False,
        price_hint="$0.50/M Input + $10/M Audio-Output",
        voice_api_id="gemini-Algenib",
    ),
    ModelChoice(
        id=MODEL_GEMINI_31_FLASH,
        label="Gemini 3.1 Flash (kostenpflichtig)",
        short="Gemini 3.1 Flash",
        is_free=False,
        price_hint="$1/M Input + $20/M Audio-Output (neueste Generation)",
        voice_api_id="gemini-Algenib",
    ),
]


def model_by_id(model_id: str | None) -> ModelChoice:
    """Returnt das ModelChoice-Objekt zur ID. Unbekannte IDs → Default."""
    for m in AVAILABLE_MODELS:
        if m.id == model_id:
            return m
    return AVAILABLE_MODELS[0]


# ============================================================================
# CREDENTIALS — wo das Service-Account-JSON erwartet wird
# ============================================================================

DEFAULT_CREDENTIALS_PATH = Path(
    os.environ.get(
        "OPENCLAW_TTS_CREDENTIALS",
        str(Path(__file__).parent / "credentials" / "google_tts_credentials.json"),
    )
)


def credentials_path() -> Path:
    return DEFAULT_CREDENTIALS_PATH


def is_configured() -> bool:
    return credentials_path().exists()


_client = None


def _client_lazy():
    """Lazy-Init des Google-TTS-Clients (damit der Bot ohne Creds bootet)."""
    global _client
    if _client is not None:
        return _client
    path = credentials_path()
    if not path.exists():
        raise RuntimeError(
            f"Google-TTS-Credentials nicht gefunden unter {path}. "
            "Lade dein Service-Account-JSON dort ab oder setze "
            "OPENCLAW_TTS_CREDENTIALS=/pfad/zur/creds.json."
        )
    from google.cloud import texttospeech  # type: ignore
    from google.oauth2 import service_account  # type: ignore

    creds = service_account.Credentials.from_service_account_file(str(path))
    _client = texttospeech.TextToSpeechClient(credentials=creds)
    return _client


# ============================================================================
# TEXT-CLEANUP (Markdown, Emojis, URLs raus — sonst werden sie vorgelesen)
# ============================================================================

_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F1E0-\U0001F1FF"
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002600-\U000026FF"
    "\U00002700-\U000027BF"
    "\U0001F004-\U0001F0CF"
    "\U0000FE0E-\U0000FE0F"
    "\U0001F018-\U0001F270"
    "\U0000200D"
    "\U000020E3"
    "]",
    flags=re.UNICODE,
)


def strip_for_tts(text: str) -> str:
    """Bereitet Markdown-haltigen Text für TTS auf."""
    if not text:
        return ""
    text = re.sub(r"```[\s\S]*?```", " ", text)              # Code-Blöcke
    text = re.sub(r"`([^`]+)`", r"\1", text)                 # Inline-Code
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)           # Bold
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"\*([^*\n]+)\*", r"\1", text)             # Italic
    text = re.sub(r"(?<!\w)_([^_\n]+)_(?!\w)", r"\1", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)  # Header
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)  # Listen
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)     # Markdown-Links
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)        # Bilder
    text = re.sub(r"https?://\S+", " ", text)                # bare URLs
    text = _EMOJI_PATTERN.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


# ============================================================================
# CORE SYNTHESIS — single-shot
# ============================================================================

# Cloud-TTS-Modell-Mapping. Gemini-TTS-Voices routen über das Modell, das
# in `VoiceSelectionParams.model_name` angegeben ist. Chirp-Voices brauchen
# kein model_name, sondern einen besonderen API-Voice-Namen.
_CLOUD_TTS_MODEL_ALIAS: dict[str, str] = {
    "gemini-2.5-flash-tts": "gemini-2.5-flash-tts",
    "gemini-2.5-flash-preview-tts": "gemini-2.5-flash-tts",
    "gemini-2.5-pro-tts": "gemini-2.5-pro-tts",
    "gemini-3.1-flash-tts-preview": "gemini-3.1-flash-tts-preview",
}

MIN_SPEED = 0.25
MAX_SPEED = 2.0
DEFAULT_SPEED = 1.0


def _clamp_speed(speed: float | None) -> float:
    if speed is None:
        return DEFAULT_SPEED
    try:
        s = float(speed)
    except (TypeError, ValueError):
        return DEFAULT_SPEED
    return max(MIN_SPEED, min(MAX_SPEED, s))


def synthesize(
    text: str,
    model_id: str = DEFAULT_MODEL,
    speaking_rate: float = DEFAULT_SPEED,
    language_code: str = "de-DE",
) -> bytes:
    """Single-Call-Synthese. Returnt MP3-Bytes.

    `model_id` ist einer aus AVAILABLE_MODELS — wir mappen dann auf die richtigen
    Cloud-TTS-Parameter:
      - chirp3hd-Algenib       → name=`de-DE-Chirp3-HD-Algenib`, kein model_name
      - gemini-2.5-flash-tts   → name=`Algenib`, model_name=`gemini-2.5-flash-tts`
      - gemini-3.1-flash-tts-preview → name=`Algenib`, model_name=`gemini-3.1-flash-tts-preview`
    """
    from google.cloud import texttospeech as gtts  # type: ignore

    cleaned = strip_for_tts(text)
    if not cleaned:
        raise ValueError("Leerer Text nach Aufräumen — nichts zum Vorlesen.")
    rate = _clamp_speed(speaking_rate)

    choice = model_by_id(model_id)
    client = _client_lazy()

    synthesis_input = gtts.SynthesisInput(text=cleaned)

    if choice.id == MODEL_CHIRP:
        # Chirp 3 HD: Standard-Cloud-TTS-Pfad, kein Modell-Inferencing.
        voice_params = gtts.VoiceSelectionParams(
            language_code=language_code,
            name=f"{language_code}-Chirp3-HD-Algenib",
        )
    else:
        # Gemini-TTS-Modelle: Voice-Name ist kurz ("Algenib"), Modell wird
        # über model_name an Cloud-TTS gegeben.
        gemini_model = _CLOUD_TTS_MODEL_ALIAS.get(choice.id, choice.id)
        voice_params = gtts.VoiceSelectionParams(
            language_code=language_code,
            name="Algenib",
            model_name=gemini_model,
        )

    audio_config = gtts.AudioConfig(
        audio_encoding=gtts.AudioEncoding.MP3,
        speaking_rate=rate,
    )
    log.info(
        "tts: synthesizing %d chars model=%s lang=%s rate=%.2f",
        len(cleaned), choice.id, language_code, rate,
    )
    try:
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice_params,
            audio_config=audio_config,
        )
        return response.audio_content
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).splitlines()[0][:240]
        if "BILLING_DISABLED" in str(exc):
            raise RuntimeError(
                "Cloud-TTS: Billing für das Cloud-Projekt aktivieren "
                "(Cloud Console → Billing → My Projects → Projekt verknüpfen)."
            ) from exc
        if "aiplatform.googleapis.com" in str(exc) or "Agent Platform API" in str(exc):
            raise RuntimeError(
                "Cloud-TTS: Gemini-Voices brauchen aktive Vertex AI / Agent "
                "Platform API (aiplatform.googleapis.com)."
            ) from exc
        if "PERMISSION_DENIED" in str(exc):
            raise RuntimeError(
                "Cloud-TTS: Permission denied. Service-Account braucht Rolle "
                "'Cloud Text-to-Speech User' am Projekt."
            ) from exc
        raise RuntimeError(f"Cloud-TTS-Fehler: {msg}") from exc


# ============================================================================
# DYNAMISCHES CHUNKING — Balanced-DP + Fast-Start (1:1 aus PocketClaude)
# ============================================================================

PREFERRED_CHUNK_CHARS = 200
HARD_MAX_CHUNK_CHARS = 500
MAX_CHUNK_BYTES = 3800
MAX_CONCURRENT_TTS_REQUESTS = 50
BALANCED_MIN_RATIO = 0.5
FIRST_CHUNK_FAST_START_CHARS = 80
CHUNKING_MIN_TOTAL_CHARS = 200

_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?:])\s+|\n{2,}|\n(?=[A-ZÄÖÜ])")
_CLAUSE_BOUNDARY_RE = re.compile(r"(?<=[,;])\s+")


def _utf8_len(t: str) -> int:
    return len(t.encode("utf-8"))


def _within_limit(t: str, max_chars: int, max_bytes: int) -> bool:
    return len(t) <= max_chars and _utf8_len(t) <= max_bytes


def _split_oversize_token(token: str, max_chars: int, max_bytes: int) -> list[str]:
    parts, buf = [], []
    for ch in token:
        candidate = "".join(buf) + ch
        if buf and not _within_limit(candidate, max_chars, max_bytes):
            parts.append("".join(buf))
            buf = [ch]
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf))
    return parts


def _split_by_words(text: str, max_chars: int, max_bytes: int) -> list[str]:
    parts, buf = [], ""
    for word in text.split():
        candidate = f"{buf} {word}" if buf else word
        if _within_limit(candidate, max_chars, max_bytes):
            buf = candidate
            continue
        if buf:
            parts.append(buf)
            buf = ""
        if _within_limit(word, max_chars, max_bytes):
            buf = word
        else:
            parts.extend(_split_oversize_token(word, max_chars, max_bytes))
    if buf:
        parts.append(buf)
    return parts


def _tts_units(text: str, max_chars: int, max_bytes: int) -> list[str]:
    units: list[str] = []
    for sentence in _SENTENCE_BOUNDARY_RE.split(text):
        sentence = sentence.strip()
        if not sentence:
            continue
        if _within_limit(sentence, max_chars, max_bytes):
            units.append(sentence)
            continue
        for clause in _CLAUSE_BOUNDARY_RE.split(sentence):
            clause = clause.strip()
            if not clause:
                continue
            if _within_limit(clause, max_chars, max_bytes):
                units.append(clause)
            else:
                units.extend(_split_by_words(clause, max_chars, max_bytes))
    return units


def _prefix_lengths(units: list[str], *, in_bytes: bool = False) -> list[int]:
    out, total = [0], 0
    for u in units:
        total += _utf8_len(u) if in_bytes else len(u)
        out.append(total)
    return out


def _span_len(prefix: list[int], start: int, end: int) -> int:
    if end <= start:
        return 0
    return prefix[end] - prefix[start] + (end - start - 1)


def _candidate_caps(preferred: int, hard_max: int, rounds: int = 5) -> list[int]:
    low, high = max(1, min(preferred, hard_max)), max(preferred, hard_max)
    caps = {low, high}
    intervals = [(low, high)]
    for _ in range(rounds):
        nxt = []
        for s, e in intervals:
            if e - s <= 1:
                continue
            m = (s + e) // 2
            caps.add(m)
            nxt.append((s, m))
            nxt.append((m, e))
        intervals = nxt
        if not intervals:
            break
    return sorted(caps)


def _balanced_partition(
    units: list[str],
    chars_prefix: list[int],
    bytes_prefix: list[int],
    cap_chars: int,
    min_chars: int,
    max_bytes: int,
):
    n = len(units)
    best = [None] * (n + 1)
    prev = [-1] * (n + 1)
    best[0] = (0, 0, 0, 0, 0)
    for end in range(1, n + 1):
        for start in range(end - 1, -1, -1):
            chars = _span_len(chars_prefix, start, end)
            if chars > cap_chars:
                break
            if _span_len(bytes_prefix, start, end) > max_bytes:
                break
            prior = best[start]
            if prior is None:
                continue
            deficit = max(0, min_chars - chars)
            small = 1 if deficit else 0
            cand = (
                prior[0] + 1,
                prior[1] + small,
                prior[2] + deficit,
                max(prior[3], chars),
                prior[4] + (cap_chars - chars) ** 2,
            )
            if best[end] is None or cand < best[end]:
                best[end] = cand
                prev[end] = start
    if best[n] is None:
        return None
    ranges = []
    e = n
    while e > 0:
        s = prev[e]
        if s < 0:
            return None
        ranges.append((s, e))
        e = s
    ranges.reverse()
    score = best[n]
    return ranges, score[3], score[1], score[2]


def _wave_score(cap, chunk_count, max_chunk_len, small_chunks, small_deficit, preferred, concurrency):
    waves = (chunk_count + concurrency - 1) // concurrency
    startup_weight = max(100, preferred)
    wallclock = waves * (startup_weight + max_chunk_len)
    return (wallclock, waves, max_chunk_len, small_deficit, small_chunks, chunk_count, cap)


def _balanced_dp_chunks(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    min_chars = max(1, round(PREFERRED_CHUNK_CHARS * BALANCED_MIN_RATIO))
    best_choice = None
    for cap in _candidate_caps(PREFERRED_CHUNK_CHARS, HARD_MAX_CHUNK_CHARS):
        units = _tts_units(text, HARD_MAX_CHUNK_CHARS, MAX_CHUNK_BYTES)
        if not units:
            continue
        chars_prefix = _prefix_lengths(units)
        bytes_prefix = _prefix_lengths(units, in_bytes=True)
        result = _balanced_partition(
            units, chars_prefix, bytes_prefix, cap, min_chars, MAX_CHUNK_BYTES,
        )
        if result is None:
            continue
        ranges, max_chunk_len, small_chunks, small_deficit = result
        score = _wave_score(
            cap, len(ranges), max_chunk_len, small_chunks, small_deficit,
            PREFERRED_CHUNK_CHARS, MAX_CONCURRENT_TTS_REQUESTS,
        )
        if best_choice is None or score < best_choice[3]:
            best_choice = (ranges, units, cap, score)
    if best_choice is None:
        return _tts_units(text, HARD_MAX_CHUNK_CHARS, MAX_CHUNK_BYTES) or [text]
    ranges, units, _cap, _score = best_choice
    return [" ".join(units[s:e]) for s, e in ranges]


def split_into_chunks(text: str, fast_start: bool = True) -> list[str]:
    """Splittet langen Text in TTS-Chunks. Fast-Start = erster Chunk klein
    halten (≤80 Zeichen), damit der User sofort Audio hört."""
    text = text.strip()
    if not text:
        return []

    first_chunk: str | None = None
    remainder = text

    if fast_start and len(text) >= CHUNKING_MIN_TOTAL_CHARS:
        units_for_first = _tts_units(text, HARD_MAX_CHUNK_CHARS, MAX_CHUNK_BYTES)
        if units_for_first:
            first_atom = units_for_first[0]
            if len(first_atom) <= FIRST_CHUNK_FAST_START_CHARS:
                first_chunk = first_atom
                remainder = text[len(first_atom):].lstrip()
            else:
                subs = _CLAUSE_BOUNDARY_RE.split(first_atom)
                sub_buf = ""
                for sub in subs:
                    sub = sub.strip()
                    if not sub:
                        continue
                    candidate = f"{sub_buf} {sub}".strip() if sub_buf else sub
                    if len(candidate) <= FIRST_CHUNK_FAST_START_CHARS:
                        sub_buf = candidate
                    else:
                        break
                if sub_buf and len(sub_buf) >= 20:
                    first_chunk = sub_buf
                    remainder = text[len(sub_buf):].lstrip()

    rest_chunks = _balanced_dp_chunks(remainder) if remainder else []
    all_chunks = ([first_chunk] if first_chunk else []) + rest_chunks
    log.info(
        "tts chunking: %d chunks (fast_start=%s, sizes=%s, total=%d chars)",
        len(all_chunks), first_chunk is not None,
        [len(c) for c in all_chunks][:10], len(text),
    )
    return all_chunks


# ============================================================================
# STREAMING API — parallel-chunked synthesis
# ============================================================================

MAX_TOTAL_CHARS = 100_000


async def synthesize_chunked(
    text: str,
    model_id: str = DEFAULT_MODEL,
    speaking_rate: float = DEFAULT_SPEED,
    language_code: str = "de-DE",
    chunking_enabled: bool = True,
) -> AsyncIterator[bytes]:
    """Streamt Audio-Chunks (MP3) in Reihenfolge.

    Chunks werden parallel synthetisiert (bis MAX_CONCURRENT_TTS_REQUESTS),
    aber in der Reihenfolge der Eingabe geyielded — heißt: TTS-Wartezeit hinter
    dem schon-fertig-Chunk wird überlappt, der User hört Audio nahezu sofort.

    Concatenierte MP3-Frames sind direkt abspielbar (Telegram akzeptiert sie
    als Voice Note / Audio).
    """
    cleaned = strip_for_tts(text)
    if not cleaned:
        raise ValueError("Leerer Text — nichts zum Vorlesen.")
    if len(cleaned) > MAX_TOTAL_CHARS:
        cleaned = cleaned[:MAX_TOTAL_CHARS] + " … Rest gekürzt."
        log.warning("TTS-Stream: Text auf %d chars gekappt", MAX_TOTAL_CHARS)

    if not chunking_enabled or len(cleaned) < CHUNKING_MIN_TOTAL_CHARS:
        # Single-Call-Pfad
        audio = await asyncio.to_thread(
            synthesize, cleaned, model_id, speaking_rate, language_code,
        )
        yield audio
        return

    chunks = split_into_chunks(cleaned)
    if len(chunks) <= 1:
        audio = await asyncio.to_thread(
            synthesize, cleaned, model_id, speaking_rate, language_code,
        )
        yield audio
        return

    log.info(
        "TTS-Stream: model=%s chunks=%d concurrency=%d total_chars=%d",
        model_id, len(chunks), MAX_CONCURRENT_TTS_REQUESTS, len(cleaned),
    )

    sem = asyncio.Semaphore(MAX_CONCURRENT_TTS_REQUESTS)

    async def _synth_one(chunk_text: str) -> bytes:
        async with sem:
            return await asyncio.to_thread(
                synthesize, chunk_text, model_id, speaking_rate, language_code,
            )

    tasks = [asyncio.create_task(_synth_one(c)) for c in chunks]

    try:
        for i, task in enumerate(tasks):
            audio_bytes = await task
            log.info("TTS-Stream: chunk %d/%d ready (%d bytes)",
                     i + 1, len(tasks), len(audio_bytes))
            yield audio_bytes
    except BaseException:
        for t in tasks:
            if not t.done():
                t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise


async def synthesize_to_file(
    text: str,
    output_path: str | Path,
    model_id: str = DEFAULT_MODEL,
    speaking_rate: float = DEFAULT_SPEED,
    language_code: str = "de-DE",
    chunking_enabled: bool = True,
) -> Path:
    """Convenience: streamt alle Chunks und schreibt sie in eine einzige MP3."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as f:
        async for chunk in synthesize_chunked(
            text, model_id, speaking_rate, language_code, chunking_enabled,
        ):
            f.write(chunk)
    return output_path
