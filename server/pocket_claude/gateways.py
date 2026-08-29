"""Zusatz-Modelle: Gateway-Konfiguration, Discovery, Normalisierung, Effort.

PocketClaude spricht Claude ueber die Claude-Agent-SDK an (siehe
`claude_engine.py`). Zusaetzlich lassen sich Gemini- und GPT-Modelle nutzen,
die auf Paradies hinter OpenAI-kompatiblen Gateways haengen (CLIProxyAPI fuer
die Google-Konten, CodexLB fuer die ChatGPT-Konten). Beide sprechen
`GET /v1/models` und `POST /v1/chat/completions`.

Dieses Modul kennt nur die Modell-Landkarte:
  - welche Gateways konfiguriert sind (aus der .env),
  - welche Modelle sie aktuell anbieten (Discovery mit Cache),
  - wie eine Modell-ID plus Denktiefe auf einen konkreten Aufruf abgebildet wird.

Das eigentliche Streaming macht `openai_engine.py`.

Bewusst KEIN openai- oder google-SDK als Dependency: `httpx` ist ohnehin da.
"""
from __future__ import annotations

import asyncio
import fnmatch
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

log = logging.getLogger(__name__)


# Denktiefe-Skala der Zusatz-Modelle, aufsteigend. Der Claude-exklusive Wert
# "off" kommt hier bewusst nicht vor: die Gateways kennen kein Abschalten.
EFFORT_ORDER: list[str] = ["minimal", "low", "medium", "high", "xhigh", "max", "ultra"]

# Suffixe, die eine Modell-ID als Denktiefe-Variante ausweisen. Reihenfolge ist
# wichtig: das laengere `-extra-low` muss vor `-low` geprueft werden. Alles was
# hier NICHT steht (z.B. `-lite`, `-agent`, `-mini`, `-preview`) gehoert zum
# Modellnamen und wird nicht abgetrennt.
SUFFIX_TO_EFFORT: list[tuple[str, str]] = [
    ("-extra-low", "minimal"),
    ("-xhigh", "xhigh"),
    ("-ultra", "ultra"),
    ("-medium", "medium"),
    ("-high", "high"),
    ("-low", "low"),
    ("-max", "max"),
]

# Cache-Zeiten (Sekunden). Erfolgreiche Abfragen halten laenger als Fehler,
# damit ein kurz nicht erreichbares Gateway sich schnell wieder faengt.
CACHE_TTL_OK = 300.0
CACHE_TTL_ERROR = 60.0
DISCOVERY_TIMEOUT = 10.0


@dataclass(frozen=True)
class GatewayConfig:
    """Konfiguration eines einzelnen OpenAI-kompatiblen Gateways."""

    id: str
    label: str
    base_url: str          # ohne Slash am Ende, inklusive /v1
    api_key: str = ""
    timeout: float = 120.0


@dataclass
class ChatModel:
    """Ein in der UI waehlbares Zusatz-Modell (Varianten bereits gruppiert)."""

    key: str                              # "gw:<gateway_id>:<base_id>"
    gateway_id: str
    gateway_label: str
    family: str                           # "gemini" | "gpt" | "other"
    base_id: str
    label: str
    efforts: list[str] = field(default_factory=list)
    default_effort: str = ""
    effort_mode: str = "none"             # model_variant | reasoning_effort | none
    variant_ids: dict[str, str] = field(default_factory=dict)
    fallback_id: str = ""
    supports_vision: bool = False
    context_length: int | None = None


@dataclass
class _CacheEntry:
    models: list[ChatModel]
    error: str | None
    fetched_at: float
    checked_at: str


_cache: dict[str, _CacheEntry] = {}
_cache_lock = asyncio.Lock()


# ---------- Konfiguration ----------

def gateway_configs() -> list[GatewayConfig]:
    """Liest die Gateway-Liste aus den Settings.

    Vorrang hat `EXTRA_MODEL_GATEWAYS` (JSON-Liste). Ist das leer, werden die
    Kurzform-Variablen `GEMINI_GATEWAY_URL` / `GPT_GATEWAY_URL` genutzt; zeigen
    beide auf dieselbe URL, entsteht nur EIN Gateway.

    Ein kaputtes JSON darf den Serverstart nie kippen: dann WARNING und
    leere Liste, die App zeigt schlicht nur Claude.
    """
    from pocket_claude.config import settings

    raw = (settings.extra_model_gateways or "").strip()
    if raw:
        try:
            data = json.loads(raw)
        except (ValueError, TypeError) as exc:
            log.warning("PC_GW: EXTRA_MODEL_GATEWAYS ist kein gueltiges JSON: %s", exc)
            return []
        if not isinstance(data, list):
            log.warning("PC_GW: EXTRA_MODEL_GATEWAYS muss eine JSON-Liste sein.")
            return []
        out: list[GatewayConfig] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            gid = str(item.get("id") or "").strip()
            base = str(item.get("base_url") or "").strip().rstrip("/")
            if not gid or not base:
                # NIE das ganze Dict loggen: da steht der API-Key drin.
                log.warning("PC_GW: Gateway-Eintrag ohne id/base_url uebersprungen "
                            "(Felder: %s)", ", ".join(sorted(item.keys())))
                continue
            try:
                timeout = float(item.get("timeout") or 120.0)
            except (TypeError, ValueError):
                timeout = 120.0
            out.append(GatewayConfig(
                id=gid,
                label=str(item.get("label") or gid),
                base_url=base,
                api_key=str(item.get("api_key") or "").strip(),
                timeout=timeout,
            ))
        return out

    gem_url = (settings.gemini_gateway_url or "").strip().rstrip("/")
    gem_key = (settings.gemini_gateway_key or "").strip()
    gpt_url = (settings.gpt_gateway_url or "").strip().rstrip("/")
    gpt_key = (settings.gpt_gateway_key or "").strip()

    if gem_url and gem_url == gpt_url:
        return [GatewayConfig(
            id="pool", label="Modell-Pool", base_url=gem_url,
            api_key=gem_key or gpt_key,
        )]

    out = []
    if gem_url:
        out.append(GatewayConfig(id="gemini", label="Gemini-Pool",
                                 base_url=gem_url, api_key=gem_key))
    if gpt_url:
        out.append(GatewayConfig(id="gpt", label="GPT-Pool",
                                 base_url=gpt_url, api_key=gpt_key))
    return out


# ---------- Normalisierung ----------

def detect_family(model_id: str) -> str:
    """Ordnet eine Modell-ID einer Familie zu."""
    low = model_id.lower()
    if "gemini" in low:
        return "gemini"
    if low.startswith(("gpt", "codex", "o1", "o3", "o4")) or "gpt-" in low:
        return "gpt"
    return "other"


def split_effort_suffix(model_id: str) -> tuple[str, str | None]:
    """Trennt ein Denktiefe-Suffix ab. Gibt (base_id, effort_or_None) zurueck."""
    low = model_id.lower()
    for suffix, effort in SUFFIX_TO_EFFORT:
        if low.endswith(suffix):
            return model_id[: -len(suffix)], effort
    return model_id, None


def make_label(base_id: str) -> str:
    """Baut aus einer base_id ein lesbares Label, wenn das Gateway keins liefert."""
    parts = [p for p in base_id.split("-") if p]
    words: list[str] = []
    for p in parts:
        low = p.lower()
        if low == "gpt":
            words.append("GPT")
        elif low == "oss":
            words.append("OSS")
        elif re.fullmatch(r"\d+b", low):
            words.append(low.upper())
        else:
            words.append(p[:1].upper() + p[1:])
    # "GPT" und die Versionsnummer gehoeren zusammen: "GPT-5.6 Sol".
    if len(words) >= 2 and words[0] == "GPT" and words[1][:1].isdigit():
        words = [f"GPT-{words[1]}"] + words[2:]
    return " ".join(words)


def _meta(item: dict) -> dict:
    m = item.get("metadata")
    return m if isinstance(m, dict) else {}


def _caps(item: dict) -> dict:
    m = _meta(item)
    c = m.get("capabilities") or item.get("capabilities")
    return c if isinstance(c, dict) else {}


def _detect_vision(item: dict, family: str) -> bool:
    caps = _caps(item)
    for key in ("supports_vision", "supports_images", "supportsVision"):
        if key in caps:
            return bool(caps[key])
    mods = caps.get("input_modalities") or _meta(item).get("input_modalities")
    if isinstance(mods, list):
        return "image" in mods
    # Ohne Metadaten raten wir: aktuelle Gemini- und GPT-Chatmodelle koennen
    # alle Bilder lesen. Lieber ein Bild mitschicken und einen Gateway-Fehler
    # riskieren als dem Nutzer grundlos sagen, sein Bild sei unlesbar.
    return family in ("gemini", "gpt")


def _detect_context_length(item: dict) -> int | None:
    caps = _caps(item)
    meta = _meta(item)
    for src in (caps, meta, item):
        for key in ("context_length", "context_window", "input_context_window",
                    "max_context_tokens"):
            val = src.get(key)
            if isinstance(val, int) and val > 0:
                return val
    return None


def _is_text_output(item: dict) -> bool:
    caps = _caps(item)
    mods = caps.get("output_modalities")
    if isinstance(mods, list) and mods:
        return "text" in mods
    return True


def pick_default_effort(efforts: list[str], preferred: str | None = None) -> str:
    """Standard-Denktiefe: gewuenscht, sonst high, sonst die naechsthoehere darunter."""
    if not efforts:
        return ""
    if preferred and preferred in efforts:
        return preferred
    if "high" in efforts:
        return "high"
    high_idx = EFFORT_ORDER.index("high")
    for eff in reversed(EFFORT_ORDER[:high_idx]):
        if eff in efforts:
            return eff
    for eff in EFFORT_ORDER:
        if eff in efforts:
            return eff
    return efforts[0]


def clamp_effort(wanted: str, available: list[str]) -> str:
    """Klemmt eine nicht unterstuetzte Denktiefe: erst nach unten, dann nach oben."""
    if not available:
        return ""
    if wanted in available:
        return wanted
    idx = EFFORT_ORDER.index(wanted) if wanted in EFFORT_ORDER else EFFORT_ORDER.index("high")
    for i in range(idx - 1, -1, -1):
        if EFFORT_ORDER[i] in available:
            return EFFORT_ORDER[i]
    for i in range(idx + 1, len(EFFORT_ORDER)):
        if EFFORT_ORDER[i] in available:
            return EFFORT_ORDER[i]
    return available[0]


def allowlist_patterns() -> list[str]:
    """Die konfigurierten Kuratierungs-Muster. Leere Liste = keine Filterung."""
    from pocket_claude.config import settings

    raw = (settings.model_allowlist or "").strip()
    if not raw:
        return []
    return [p.strip().lower() for p in raw.split(",") if p.strip()]


def is_allowed(base_id: str, patterns: list[str]) -> bool:
    """Prueft eine Basis-ID gegen die Kuratierungs-Muster (Glob, case-insensitiv)."""
    if not patterns:
        return True
    low = base_id.lower()
    return any(fnmatch.fnmatchcase(low, p) for p in patterns)


def normalize(gw: GatewayConfig, payload: dict) -> list[ChatModel]:
    """Macht aus einer /v1/models-Antwort die gruppierte ChatModel-Liste."""
    raw_items = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(raw_items, list):
        return []

    groups: dict[str, list[dict]] = {}
    skipped: list[str] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        mid = str(item.get("id") or "").strip()
        if not mid:
            continue
        low = mid.lower()
        # Claude laeuft ueber den nativen Pfad. Ein zweiter Claude-Weg ueber
        # das Gateway wuerde nur verwirren (andere Sessions, andere Tools).
        if low.startswith("claude"):
            skipped.append(mid)
            continue
        # Reine Bild-Modelle gehoeren nicht in den Chat-Picker; die nutzt das
        # Bild-Werkzeug ueber image_engine.
        if "-image" in low or not _is_text_output(item):
            skipped.append(mid)
            continue

        base_id, effort = split_effort_suffix(mid)
        groups.setdefault(base_id, []).append({
            "raw_id": mid,
            "effort": effort,
            "item": item,
        })

    if skipped:
        log.debug("PC_GW: %s: %d Modelle ausgefiltert (%s)",
                  gw.id, len(skipped), ", ".join(skipped[:8]))

    models: list[ChatModel] = []
    for base_id, entries in groups.items():
        family = detect_family(base_id)
        label = ""
        for e in entries:
            name = _meta(e["item"]).get("display_name")
            if isinstance(name, str) and name.strip():
                label = name.strip()
                break
        if not label:
            label = make_label(base_id)

        # CodexLB meldet die Denktiefen als Metadata, dann steuern wir sie per
        # `reasoning_effort` im Request. CLIProxyAPI meldet nichts, dort steckt
        # die Denktiefe im Modellnamen.
        meta_levels: list[str] = []
        meta_default = ""
        for e in entries:
            lv = _meta(e["item"]).get("supported_reasoning_levels")
            if isinstance(lv, list) and lv:
                for one in lv:
                    if isinstance(one, dict) and one.get("effort"):
                        meta_levels.append(str(one["effort"]))
                    elif isinstance(one, str):
                        meta_levels.append(one)
                dflt = _meta(e["item"]).get("default_reasoning_level")
                if isinstance(dflt, str):
                    meta_default = dflt
                break

        supports_vision = any(_detect_vision(e["item"], family) for e in entries)
        ctx = next((c for c in (_detect_context_length(e["item"]) for e in entries)
                    if c is not None), None)

        common = dict(
            key=f"gw:{gw.id}:{base_id}",
            gateway_id=gw.id,
            gateway_label=gw.label,
            family=family,
            base_id=base_id,
            label=label,
            supports_vision=supports_vision,
            context_length=ctx,
        )

        if meta_levels:
            efforts = [e for e in EFFORT_ORDER if e in meta_levels]
            models.append(ChatModel(
                **common,
                efforts=efforts,
                # Produktentscheidung: "high" ist die Vorauswahl, wenn das
                # Modell sie kann. Der Gateway-Default (bei CodexLB "medium")
                # greift nur, wenn es kein high gibt.
                default_effort=pick_default_effort(
                    efforts, None if "high" in efforts else meta_default),
                effort_mode="reasoning_effort",
                variant_ids={},
                fallback_id=entries[0]["raw_id"],
            ))
        elif any(e["effort"] for e in entries):
            variant_ids = {e["effort"]: e["raw_id"] for e in entries if e["effort"]}
            efforts = [e for e in EFFORT_ORDER if e in variant_ids]
            plain = next((e["raw_id"] for e in entries if not e["effort"]), None)
            models.append(ChatModel(
                **common,
                efforts=efforts,
                default_effort=pick_default_effort(efforts),
                effort_mode="model_variant",
                variant_ids=variant_ids,
                fallback_id=plain or variant_ids.get("high") or next(iter(variant_ids.values())),
            ))
        else:
            models.append(ChatModel(
                **common,
                efforts=[],
                default_effort="",
                effort_mode="none",
                variant_ids={},
                fallback_id=entries[0]["raw_id"],
            ))

    models.sort(key=lambda m: (m.family, m.label.lower()))
    return models


# ---------- Discovery ----------

def _error_message(exc: Exception, gw: GatewayConfig) -> str:
    if isinstance(exc, httpx.ConnectError):
        return (f"Das Gateway '{gw.label}' ist nicht erreichbar ({gw.base_url}). "
                f"Laeuft der Dienst auf Paradies?")
    if isinstance(exc, httpx.TimeoutException):
        return f"Das Gateway '{gw.label}' hat nicht rechtzeitig geantwortet."
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code in (401, 403):
            return (f"Das Gateway '{gw.label}' hat den Zugriff abgelehnt. "
                    f"API-Key in der .env pruefen.")
        if code == 404:
            return (f"Unter {gw.base_url}/models antwortet nichts (HTTP 404). "
                    f"Stimmt die Basis-URL?")
        if code == 429:
            return ("Das Konto-Kontingent ist gerade erschoepft. Spaeter erneut "
                    "versuchen oder ein anderes Modell waehlen.")
        return f"Gateway-Fehler (HTTP {code}): {exc.response.text[:300]}"
    return f"Gateway-Fehler: {type(exc).__name__}: {exc}"


async def _fetch(gw: GatewayConfig) -> list[ChatModel]:
    headers = {"Authorization": f"Bearer {gw.api_key}"} if gw.api_key else {}
    timeout = httpx.Timeout(DISCOVERY_TIMEOUT, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as cli:
        r = await cli.get(f"{gw.base_url}/models", headers=headers)
        r.raise_for_status()
        return normalize(gw, r.json())


async def _refresh_one(gw: GatewayConfig, now: float, now_iso: str) -> _CacheEntry:
    try:
        models = await _fetch(gw)
        log.info("PC_GW: %s liefert %d Zusatz-Modelle", gw.id, len(models))
        return _CacheEntry(models=models, error=None, fetched_at=now, checked_at=now_iso)
    except Exception as exc:  # noqa: BLE001 - jeder Fehler wird zur UI-Meldung
        msg = _error_message(exc, gw)
        previous = _cache.get(gw.id)
        keep = previous.models if previous else []
        log.warning("PC_GW: %s nicht abrufbar (%d Modelle aus dem Cache bleiben): %s",
                    gw.id, len(keep), msg)
        return _CacheEntry(models=keep, error=msg, fetched_at=now, checked_at=now_iso)


async def list_models(force: bool = False, curated: bool = True) -> list[ChatModel]:
    """Alle aktuell verfuegbaren Zusatz-Modelle ueber alle Gateways hinweg.

    Faellt ein Gateway aus, liefern die anderen trotzdem, und die zuletzt
    bekannten Modelle des ausgefallenen bleiben stehen (stale-if-error). Ein
    kurzer Aussetzer der Modell-Liste soll keinen laufenden Chat abwuergen. Der
    Fehler bleibt im Cache und wird ueber `status()` sichtbar.

    `curated=True` liefert nur die Modelle der Allowlist, also das, was im Picker
    stehen soll. `curated=False` liefert alles, was die Gateways koennen.

    Die Unterscheidung ist wichtig: Kuratierung ist eine Frage der ANZEIGE, nicht
    der Gueltigkeit. Ein Chat, in dem ein inzwischen nicht mehr kuratiertes
    Modell gespeichert ist, muss weiterlaufen duerfen, statt beim naechsten Turn
    stillschweigend auf ein anderes Modell zu wechseln.
    """
    gws = gateway_configs()
    if not gws:
        return []

    now = time.time()
    now_iso = datetime.now(timezone.utc).isoformat()

    async with _cache_lock:
        stale: list[GatewayConfig] = []
        for gw in gws:
            entry = _cache.get(gw.id)
            if force or entry is None:
                stale.append(gw)
                continue
            ttl = CACHE_TTL_ERROR if entry.error else CACHE_TTL_OK
            if now - entry.fetched_at >= ttl:
                stale.append(gw)
        if not stale:
            return _collect(gws, curated)

    # Die HTTP-Abfragen laufen bewusst OHNE die Sperre: sonst wartet bei einem
    # haengenden Gateway jeder andere Aufruf mit. Parallel, damit sich zwei
    # nicht erreichbare Gateways nicht auf die doppelte Wartezeit summieren.
    results = await asyncio.gather(
        *(_refresh_one(gw, now, now_iso) for gw in stale),
        return_exceptions=True,
    )

    async with _cache_lock:
        for gw, entry in zip(stale, results):
            if isinstance(entry, _CacheEntry):
                _cache[gw.id] = entry
            else:
                log.warning("PC_GW: Discovery fuer %s abgebrochen: %s", gw.id, entry)
        return _collect(gws, curated)


def _collect(gws: list[GatewayConfig], curated: bool = True) -> list[ChatModel]:
    """Sammelt die zuletzt bekannten Modelle aller Gateways aus dem Cache."""
    out: list[ChatModel] = []
    for gw in gws:
        entry = _cache.get(gw.id)
        if entry and entry.models:
            out.extend(entry.models)
    if not curated:
        return out
    patterns = allowlist_patterns()
    if not patterns:
        return out
    kept = [m for m in out if is_allowed(m.base_id, patterns)]
    dropped = len(out) - len(kept)
    if dropped:
        log.debug("PC_GW: %d Modelle nicht kuratiert, im Picker ausgeblendet", dropped)
    return kept


def resolve(model_key: str, effort: str,
            models: list[ChatModel]) -> tuple[ChatModel, str, str | None]:
    """Loest Modell-Key plus Wunsch-Denktiefe auf.

    Gibt (ChatModel, konkrete Modell-ID fuers Gateway, reasoning_effort) zurueck.
    `reasoning_effort` ist nur bei effort_mode="reasoning_effort" gesetzt.
    Wirft KeyError, wenn das Modell nicht mehr angeboten wird.
    """
    model = next((m for m in models if m.key == model_key), None)
    if model is None:
        raise KeyError(model_key)

    if model.effort_mode == "none":
        return model, model.fallback_id, None

    resolved = clamp_effort(effort, model.efforts)
    if resolved != effort:
        log.info("PC_GW: Denktiefe %r fuer %s nicht verfuegbar, benutze %r",
                 effort, model.key, resolved)

    if model.effort_mode == "model_variant":
        return model, model.variant_ids.get(resolved, model.fallback_id), None
    return model, model.fallback_id, resolved


def gateway_by_id(gateway_id: str) -> GatewayConfig | None:
    return next((g for g in gateway_configs() if g.id == gateway_id), None)


async def status() -> list[dict]:
    """Zustand je Gateway fuer den /chat/models-Endpoint. Der API-Key bleibt drin."""
    gws = gateway_configs()
    if not gws:
        return []
    await list_models(force=False)
    out: list[dict] = []
    for gw in gws:
        entry = _cache.get(gw.id)
        out.append({
            "id": gw.id,
            "label": gw.label,
            "base_url": gw.base_url,
            "reachable": bool(entry and entry.error is None),
            "model_count": len(entry.models) if entry and not entry.error else 0,
            "last_error": entry.error if entry else None,
            "checked_at": entry.checked_at if entry else None,
        })
    return out


def clear_cache() -> None:
    """Cache leeren (Tests, manuelles Neuladen)."""
    _cache.clear()
