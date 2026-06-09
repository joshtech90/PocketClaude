"""FastAPI-Server: HTTP-Endpoints für Pocket Claude."""
from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import time as _time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncIterator

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Path as PathParam,
    Query,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from pocket_claude import (
    __version__, auth_modes, backup, billing, claude_engine, db, image_engine,
    system_prompts, tts, tts_cache, usage, voice,
)
from pocket_claude.auth import (
    require_admin,
    require_token,
    require_token_header_or_query,
    require_user,
    require_user_header_or_query,
)
from pocket_claude.config import settings
from pocket_claude.models import (
    AttachmentOut,
    AttachmentRef,
    BillingStatusDto,
    ClaudeAuthDto,
    ClaudeAuthUpdateRequest,
    ConversationCreate,
    ConversationDetail,
    ConversationOut,
    ConversationPatch,
    ConversationSkillsRequest,
    ConversationSkillsResponse,
    HealthOut,
    MessageOut,
    SearchHitOut,
    SearchResponseOut,
    SendMessageRequest,
    SettingsExportDto,
    SettingsImportRequest,
    SettingsImportResponse,
    SkillsDefaultsRequest,
    SkillsDto,
    TtsApiKeyAddRequest,
    TtsApiKeyEntryDto,
    TtsApiKeysDto,
    TtsCredentialsRequest,
    TtsModelDto,
    TtsChunkingRequest,
    TtsModelRequest,
    TtsProviderRequest,
    TtsStatusDto,
    TtsVoiceDto,
    UsageStatsDto,
)

log = logging.getLogger("pocket_claude")
logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    await db.init_db()
    await usage.ensure_schema()
    log.info("Pocket Claude Server v%s gestartet — DB: %s", __version__, settings.db_path)
    # TTS-Pre-Warm: Service-Account-JSON laden, OAuth-Token holen, gRPC-Channel
    # zu Google öffnen — spart 200-500ms beim ersten echten TTS-Tap.
    import asyncio as _asyncio
    _asyncio.create_task(_tts_prewarm())
    yield


async def _tts_prewarm() -> None:
    """Wärmt die Cloud-TTS-Connection vor (lazy-loads Client, hält gRPC-
    Channel offen). Fehler werden weggeschluckt — falls Cloud-TTS nicht
    konfiguriert ist, läuft alles andere ja trotzdem (auch der Gemini-API-
    Pfad, der keinen Pre-Warm braucht — httpx hat eh keinen persistenten
    Channel)."""
    import asyncio as _asyncio
    try:
        if not tts.is_configured():
            log.info("TTS-PreWarm übersprungen — Cloud-TTS-Credentials nicht gesetzt.")
            return
        # Init Client (lazy) + 1-Wort-Test-Synthese mit Cloud-TTS-Default-Voice
        # (nicht-Gemini, damit der billige Standard-Pfad durchläuft).
        await _asyncio.to_thread(
            tts.synthesize, ".", "de-DE-Standard-A", 1.0,
            tts.PROVIDER_CLOUD_TTS, None,
        )
        log.info("TTS-PreWarm OK (Connection zu Google Cloud-TTS warm)")
    except Exception as exc:  # noqa: BLE001
        # Google-API-Exceptions können RIESIGE Proto-Dumps mitbringen
        # (BILLING_DISABLED-Fall: ~30 Zeilen Metadata). Wir kürzen auf die
        # echte Kernaussage, der ganze Rest landet nur im DEBUG-Level.
        full = str(exc)
        short = full.splitlines()[0][:240]
        hint = ""
        if "BILLING_DISABLED" in full:
            hint = (
                " — Tipp: das Cloud-Projekt des hochgeladenen Service-Account-JSON "
                "ist nicht mit einem Billing-Account verknüpft. Cloud Console → "
                "Billing → My Projects → Projekt mit dem Billing-Account verknüpfen. "
                "(NICHT auf Gemini-API ausweichen — das $10-AI-Pro-Kontingent läuft "
                "nur über Cloud-TTS.)"
            )
        log.warning("TTS-PreWarm fehlgeschlagen (nicht kritisch): %s%s", short, hint)
        log.debug("TTS-PreWarm Full-Exception: %s", full)


app = FastAPI(
    title="Pocket Claude",
    version=__version__,
    description="Persönlicher Claude-Chat-Server für die Pocket Claude Android-App.",
    lifespan=lifespan,
)

# Für lokale Entwicklung (App spricht später eh via Tunnel — CORS ist da egal,
# aber für browser-basierte Tests praktisch).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Helpers ----------

def _row_to_conv_out(row: dict) -> ConversationOut:
    return ConversationOut(
        id=row["id"],
        title=row["title"],
        created_at=datetime.fromisoformat(row["created_at"]),
        last_message_at=(
            datetime.fromisoformat(row["last_message_at"]) if row["last_message_at"] else None
        ),
        message_count=row["msg_count"],
        total_tokens=row["total_tokens"],
        pinned=bool(row.get("pinned", 0)),
    )


async def _attachment_refs(ids: list[str]) -> list[AttachmentRef]:
    atts = await db.get_attachments(ids)
    return [
        AttachmentRef(
            id=a["id"],
            filename=a["filename"],
            mime_type=a["mime_type"],
            size_bytes=a["size_bytes"],
        )
        for a in atts
    ]


async def _row_to_message_out(row: dict) -> MessageOut:
    return MessageOut(
        id=row["id"],
        conversation_id=row["conversation_id"],
        role=row["role"],
        content=row["content"],
        created_at=datetime.fromisoformat(row["created_at"]),
        tokens=row["tokens"],
        attachments=await _attachment_refs(row["attachment_ids"]),
    )


# ---------- Health ----------

@app.get("/health", response_model=HealthOut)
async def health() -> HealthOut:
    db_ok = settings.db_path.exists()
    model = settings.claude_model or "Claude (Default via claude CLI)"
    return HealthOut(
        status="ok",
        version=__version__,
        model=model,
        db_ok=db_ok,
    )


# ---------- Conversations ----------

@app.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(user=Depends(require_user)) -> list[ConversationOut]:
    rows = await db.list_conversations(user_id=user["id"])
    return [_row_to_conv_out(r) for r in rows]


@app.post(
    "/conversations",
    response_model=ConversationOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(body: ConversationCreate, user=Depends(require_user)) -> ConversationOut:
    cid = await db.create_conversation(body.title, user_id=user["id"])
    conv = await db.get_conversation(cid, user_id=user["id"])
    assert conv is not None
    return ConversationOut(
        id=conv["id"],
        title=conv["title"],
        created_at=datetime.fromisoformat(conv["created_at"]),
        last_message_at=None,
        message_count=0,
        total_tokens=0,
    )


@app.get("/conversations/{cid}", response_model=ConversationDetail)
async def get_conversation(cid: str = PathParam(...), user=Depends(require_user)) -> ConversationDetail:
    conv = await db.get_conversation(cid, user_id=user["id"])
    if not conv:
        raise HTTPException(404, "Konversation nicht gefunden.")
    msg_rows = await db.list_messages(cid)
    messages = [await _row_to_message_out(m) for m in msg_rows]
    return ConversationDetail(
        id=conv["id"],
        title=conv["title"],
        created_at=datetime.fromisoformat(conv["created_at"]),
        last_message_at=(
            datetime.fromisoformat(conv["last_message_at"]) if conv["last_message_at"] else None
        ),
        message_count=len(messages),
        total_tokens=conv["total_tokens"],
        pinned=bool(conv.get("pinned", 0)),
        messages=messages,
    )


@app.patch("/conversations/{cid}", response_model=ConversationOut)
async def patch_conversation(cid: str, body: ConversationPatch, user=Depends(require_user)) -> ConversationOut:
    conv = await db.get_conversation(cid, user_id=user["id"])
    if not conv:
        raise HTTPException(404, "Konversation nicht gefunden.")
    if body.title is not None:
        await db.update_conversation_title(cid, body.title, user_id=user["id"])
    if body.pinned is not None:
        await db.set_pinned(cid, body.pinned, user_id=user["id"])
    rows = await db.list_conversations(user_id=user["id"])
    for r in rows:
        if r["id"] == cid:
            return _row_to_conv_out(r)
    # list_conversations only returns chats that already have at least one
    # message. A freshly created (still empty) chat that gets patched
    # (renamed/pinned) is therefore absent from that list — re-fetch it
    # directly and build the response, instead of falsely 404-ing a write
    # that actually succeeded.
    updated = await db.get_conversation(cid, user_id=user["id"])
    if updated is None:
        raise HTTPException(404, "Konversation verschwunden.")
    return ConversationOut(
        id=updated["id"],
        title=updated["title"],
        created_at=datetime.fromisoformat(updated["created_at"]),
        last_message_at=(
            datetime.fromisoformat(updated["last_message_at"])
            if updated["last_message_at"] else None
        ),
        message_count=0,
        total_tokens=updated["total_tokens"],
        pinned=bool(updated.get("pinned", 0)),
    )


@app.delete(
    "/conversations/{cid}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=JSONResponse,
)
async def delete_conversation(cid: str, user=Depends(require_user)):
    ok = await db.delete_conversation(cid, user_id=user["id"])
    if not ok:
        raise HTTPException(404, "Konversation nicht gefunden.")
    return JSONResponse(status_code=204, content=None)


# ---------- Messages ----------

@app.post("/conversations/{cid}/messages")
async def send_message(cid: str, body: SendMessageRequest, user=Depends(require_user)) -> EventSourceResponse:
    """Sendet eine User-Message und streamt die Assistant-Antwort via SSE."""
    conv = await db.get_conversation(cid, user_id=user["id"])
    if not conv:
        raise HTTPException(404, "Konversation nicht gefunden.")

    # Anhänge validieren — müssen demselben User gehören
    if body.attachment_ids:
        existing = await db.get_attachments(body.attachment_ids)
        if len(existing) != len(body.attachment_ids):
            raise HTTPException(400, "One or more attachment IDs are invalid.")
        for a in existing:
            if a.get("user_id") != user["id"]:
                raise HTTPException(403, "Attachment belongs to a different user.")

    # User-Message speichern (Token-Schätzung machen wir grob über Zeichenlänge ÷ 4,
    # die genauen Werte trägt das message_start-Event später nach)
    estimated_tokens = max(1, len(body.content) // 4)
    user_msg_id = await db.add_message(
        cid,
        role="user",
        content=body.content,
        tokens=estimated_tokens,
        attachment_ids=body.attachment_ids,
    )

    new_title = await db.auto_rename_if_needed(cid, body.content, user_id=user["id"])

    effort = (body.effort or "high").lower().strip()
    # Wenn der Client einen Mode mitschickt (Web-UI), löst der Server hier auf.
    # Sonst nimmt der raw String (App-Pfad). Sonst Server-Default.
    if body.system_prompt_mode:
        system_prompt = system_prompts.resolve_system_prompt(
            body.system_prompt_mode, body.system_prompt,
        )
    else:
        system_prompt = body.system_prompt

    # Skills auflösen: Per-Chat-Override hat Vorrang, sonst User-Default,
    # sonst Server-Default. `conv` ist oben schon geladen.
    effective_skills, _is_override = await _resolve_effective_skills(
        user["id"], conv.get("skills_override"),
    )
    skills_dict = effective_skills.model_dump()

    async def event_gen() -> AsyncIterator[dict]:
        # PC_SSE diagnostic logging — see PocketClaude "denkt"-bug investigation.
        # Temporary, remove after root cause is fixed.
        delta_count = 0
        last_event = None
        assistant_msg_id: int | None = None
        log.info("PC_SSE: event_gen START cid=%s user=%s", cid, user["id"])
        try:
            if new_title:
                yield {"event": "title", "data": json.dumps({"title": new_title})}
                log.info("PC_SSE: yield title cid=%s", cid)
            yield {"event": "user_saved", "data": json.dumps({"user_message_id": user_msg_id})}
            log.info("PC_SSE: yield user_saved cid=%s user_msg_id=%s", cid, user_msg_id)

            async for ev in claude_engine.stream_reply(
                cid, user_msg_id,
                effort=effort,
                system_prompt=system_prompt,
                skills=skills_dict,
                user_id=user["id"],
            ):
                etype = ev.pop("type")
                last_event = etype
                if etype == "delta":
                    delta_count += 1
                    if delta_count <= 3 or delta_count % 25 == 0:
                        log.info("PC_SSE: yield delta #%d cid=%s len=%d",
                                 delta_count, cid, len(ev.get("text", "")))
                else:
                    log.info("PC_SSE: yield event=%s cid=%s payload_keys=%s",
                             etype, cid, list(ev.keys()))
                if etype == "done":
                    assistant_msg_id = ev.get("assistant_message_id") or ev.get("message_id")
                yield {"event": etype, "data": json.dumps(ev)}

            log.info(
                "PC_SSE: event_gen FOR-LOOP-EXIT cid=%s deltas=%d last=%s assistant_msg_id=%s",
                cid, delta_count, last_event, assistant_msg_id,
            )
        except BaseException as _sse_exc:  # noqa: BLE001 — catches GeneratorExit + cancels
            import traceback as _tb
            log.error(
                "PC_SSE: event_gen EXCEPTION cid=%s deltas=%d last=%s exc=%s\n%s",
                cid, delta_count, last_event, _sse_exc, _tb.format_exc(),
            )
            # Try to surface an error to the client if connection is still open
            try:
                yield {"event": "error", "data": json.dumps({
                    "message": f"Stream interrupted: {type(_sse_exc).__name__}: {_sse_exc}",
                })}
            except BaseException:  # noqa: BLE001
                pass
            raise
        finally:
            log.info(
                "PC_SSE: event_gen END cid=%s deltas=%d last=%s assistant_msg_id=%s",
                cid, delta_count, last_event, assistant_msg_id,
            )

        # Pre-Generation: wenn der Client TTS-Voice + Rate beim Senden
        # mitgeschickt hat, synthetisieren wir die Antwort jetzt im
        # Hintergrund — der nächste Vorlesen-Tap ist dann Cache-Hit.
        if assistant_msg_id and body.tts_voice:
            # Provider + Key des Users ermitteln. Nur pre-generieren wenn
            # der gewählte Provider auch wirklich einsatzbereit ist.
            provider, api_key, model_id, chunking_enabled = (
                await _resolve_tts_provider_model_and_key(user["id"])
            )
            # Wenn Cloud-TTS gerade als „nicht nutzbar" markiert ist (jüngster
            # BILLING_DISABLED o.ä.), nicht pre-generieren — würde nur Logs
            # spammen und ist eh garantiert Cache-Miss beim Tap.
            cloud_tts_blocked = (
                provider == tts.PROVIDER_CLOUD_TTS and
                _time.monotonic() < _CLOUD_TTS_UNAVAILABLE_UNTIL
            )
            ready = (not cloud_tts_blocked) and (
                (provider == tts.PROVIDER_CLOUD_TTS and tts.is_configured()) or
                (provider == tts.PROVIDER_GEMINI_API and bool(api_key)) or
                (provider == tts.PROVIDER_EDGE_TTS)
            )
            if ready:
                import asyncio as _asyncio
                _asyncio.create_task(_pregen_tts(
                    int(assistant_msg_id),
                    body.tts_voice,
                    body.tts_rate or tts.DEFAULT_SPEED,
                    provider,
                    api_key,
                    user_id=user["id"],
                    model_id=model_id,
                    chunking_enabled=chunking_enabled,
                ))

    return EventSourceResponse(event_gen())


async def _pregen_tts(
    message_id: int,
    voice: str,
    rate: float,
    provider: str,
    api_key: str | None,
    user_id: str | None = None,
    model_id: str | None = None,
    chunking_enabled: bool = True,
) -> None:
    """Generiert die Audio für eine fertige Assistant-Message im Hintergrund
    und legt sie in den TTS-Cache. Fehler werden geloggt, nicht propagiert
    (der User merkt nichts — er bekommt höchstens Cache-Miss beim Tap).

    Wenn `user_id` und Provider=gemini_api: lädt den Multi-Key-Pool und
    nutzt Round-Robin + Rate-Limiter über alle Keys.
    """
    try:
        from pocket_claude.db import get_db
        async with get_db() as conn:
            cur = await conn.execute(
                "SELECT content FROM messages WHERE id = ?", (message_id,),
            )
            row = await cur.fetchone()
        if not row or not row["content"]:
            return
        # Multi-Key-Pool für Gemini-API + Pool-aware max_chunks
        picker = None
        max_chunks: int | None = None
        if provider == tts.PROVIDER_GEMINI_API and user_id:
            pool = await _load_tts_api_keys(user_id)
            pool_size = len(pool)
            if pool_size > 1:
                pool_keys = [e["key"] for e in pool]
                async def picker() -> str | None:  # type: ignore[no-redef]
                    return await acquire_tts_key_for_call(pool_keys)
            effective_pool = max(1, pool_size)
            max_chunks = effective_pool * MAX_REQUESTS_PER_KEY_PER_MINUTE
        import io as _io
        buf = _io.BytesIO()
        async for chunk_bytes in tts.synthesize_chunked(
            row["content"], voice, rate, provider, api_key,
            key_picker=picker,
            max_chunks=max_chunks,
            user_id=user_id,
            model_id=model_id,
            chunking_enabled=chunking_enabled,
        ):
            buf.write(chunk_bytes)
        audio = buf.getvalue()
        # Für gemini_api: WAV-Header von fake-length auf echte Länge fixen,
        # damit das gecachte File eine korrekte Dauer anzeigt.
        if provider == tts.PROVIDER_GEMINI_API:
            audio = tts.fix_wav_header_length(audio)
        media_type = tts.media_type_for(provider)
        await tts_cache.put(message_id, voice, rate, provider, audio, media_type)
        log.info(
            "TTS pre-gen OK msg=%d voice=%s rate=%.2f provider=%s (%d KB)",
            message_id, voice, rate, provider, len(audio) // 1024,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "TTS pre-gen für msg=%d (provider=%s) fehlgeschlagen: %s",
            message_id, provider, exc,
        )


# ---------- Attachments ----------

@app.post("/attachments", response_model=AttachmentOut)
async def upload_attachment(file: UploadFile = File(...), user=Depends(require_user)) -> AttachmentOut:
    contents = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(413, f"File too large (max {settings.max_upload_mb} MB).")

    filename = file.filename or "upload"
    mime = file.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"

    # Auf Disk speichern — über asyncio.to_thread, damit ein 20-MB-Upload
    # nicht den Event-Loop blockiert (sonst hängen parallele Requests).
    import secrets as _secrets
    import asyncio as _asyncio
    suffix = (filename.rsplit(".", 1)[-1] if "." in filename else "bin")[:10]
    disk_name = f"{_secrets.token_urlsafe(12)}.{suffix}"
    target = settings.uploads_dir / disk_name
    await _asyncio.to_thread(target.write_bytes, contents)

    aid = await db.add_attachment(filename, mime, len(contents), target, user_id=user["id"])
    att = await db.get_attachment(aid)
    assert att
    return AttachmentOut(
        id=att["id"],
        filename=att["filename"],
        mime_type=att["mime_type"],
        size_bytes=att["size_bytes"],
        uploaded_at=datetime.fromisoformat(att["uploaded_at"]),
    )


@app.get("/attachments/{aid}")
async def download_attachment(
    aid: str,
    token: str | None = None,  # noqa: ARG001 — wird von der Dep konsumiert
    user=Depends(require_user_header_or_query),
):
    """Token kann via Bearer-Header ODER ?token=... kommen — letzteres,
    damit das Web-UI Bilder direkt per <img src> einbetten kann."""
    from fastapi.responses import FileResponse
    att = await db.get_attachment(aid, user_id=user["id"])
    if not att:
        raise HTTPException(404, "Attachment nicht gefunden.")
    return FileResponse(
        att["path"],
        media_type=att["mime_type"],
        filename=att["filename"],
    )


# ---------- Search ----------

@app.get("/search", response_model=SearchResponseOut)
async def search(q: str, limit: int = Query(30, ge=1, le=100), user=Depends(require_user)) -> SearchResponseOut:
    if not q or len(q.strip()) < 2:
        return SearchResponseOut(query=q, hits=[])
    rows = await db.search_messages(q, limit=limit, user_id=user["id"])
    hits = [
        SearchHitOut(
            conversation_id=r["conversation_id"],
            conversation_title=r["conversation_title"] or "(ohne Titel)",
            message_id=r["message_id"],
            role=r["role"],
            created_at=datetime.fromisoformat(r["created_at"]),
            snippet=r["snippet"] or "",
        )
        for r in rows
    ]
    return SearchResponseOut(query=q, hits=hits)


# ---------- Markdown-Export ----------

@app.get("/conversations/{cid}/export.md")
async def export_markdown(cid: str, user=Depends(require_user)):
    conv = await db.get_conversation(cid, user_id=user["id"])
    if not conv:
        raise HTTPException(404, "Konversation nicht gefunden.")
    messages = await db.list_messages(cid)

    from fastapi.responses import PlainTextResponse
    from datetime import timezone as _tz

    def fmt_date(iso: str) -> str:
        try:
            dt = datetime.fromisoformat(iso)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=_tz.utc)
            return dt.astimezone().strftime("%Y-%m-%d %H:%M")
        except Exception:
            return iso

    title = conv["title"] or "Pocket-Claude-Chat"
    created = fmt_date(conv["created_at"])
    lines: list[str] = [
        f"# {title}",
        "",
        f"_Pocket Claude export · started {created} · {len(messages)} messages_",
        "",
        "---",
        "",
    ]
    for m in messages:
        role = m["role"]
        when = fmt_date(m["created_at"])
        speaker = {"user": "**You**", "assistant": "**Claude**", "system": "_System_"}.get(
            role, f"**{role}**"
        )
        lines.append(f"### {speaker} · {when}")
        lines.append("")
        lines.append(m["content"] or "")
        if m.get("attachment_ids"):
            atts = await db.get_attachments(m["attachment_ids"])
            for a in atts:
                lines.append(f"\n> 📎 Attachment: `{a['filename']}` ({a['mime_type']}, {a['size_bytes']} bytes)")
        lines.append("")
        lines.append("---")
        lines.append("")
    body = "\n".join(lines)

    safe_title = "".join(c if c.isalnum() or c in " -_." else "_" for c in title)[:60].strip() or "chat"
    headers = {
        "Content-Disposition": f'attachment; filename="{safe_title}.md"',
    }
    return PlainTextResponse(content=body, media_type="text/markdown; charset=utf-8", headers=headers)


# ---------- TTS (Dual-Provider: Cloud TTS + Gemini API) ----------

# Per-User-Settings (in DB-KV abgelegt, scope=user_id):
_KV_TTS_PROVIDER = "tts_provider"   # "cloud_tts" | "gemini_api" | "edge_tts"
# Per-User Chunking-Override: "1" = an, "0" = aus, leer/unset = Provider-Default
# (cloud_tts → an, gemini_api/edge_tts → aus). User mit Multi-Key-Pool kann das
# Setting manuell wieder aktivieren wenn sein Pool die RPD-Last verträgt.
_KV_TTS_CHUNKING_ENABLED = "tts_chunking_enabled"
# Welches TTS-Modell verwendet wird (für gemini-Voices). Erlaubte Werte stehen
# in `tts.AVAILABLE_GEMINI_TTS_MODELS`. Wenn unset/invalid → Server-Default
# (gemini-2.5-flash-preview-tts).
_KV_TTS_MODEL = "tts_model"
# Multi-Key-Pool für TTS via Gemini API. JSON-encoded list of entries, jeder
# Eintrag hat {id, label, key}. Mehrere Free-Tier-Keys parallel = umgehung
# der per-project-Rate-Limits (10 RPD bei 3.1-flash-tts, 3 RPM bei 2.5).
_KV_TTS_API_KEYS = "tts_api_keys"
# Legacy-Slot (vor Multi-Key): einzelner Key. Wenn vorhanden + tts_api_keys
# leer, migrieren wir on-read.
_KV_TTS_API_KEY = "tts_api_key"
_KV_IMAGE_API_KEY_LEGACY_FALLBACK = "image_api_key"
# Alias für Backward-Compat — alter Name (`_KV_GEMINI_API_KEY`) wird woanders
# noch referenziert. Zeigt auf den Single-Key-Legacy-Slot.
_KV_GEMINI_API_KEY = _KV_TTS_API_KEY


def _gen_key_id() -> str:
    import secrets as _secrets
    return "k_" + _secrets.token_hex(4)


async def _load_tts_api_keys(user_id: str) -> list[dict]:
    """Liest die Multi-Key-Liste eines Users. Auto-Migration: wenn `tts_api_keys`
    leer ist, aber `tts_api_key` (legacy single-slot) oder `image_api_key`
    (vor-Trennung) gesetzt sind, übernehmen wir die in den Pool.

    Returnt eine Liste von dicts: [{"id", "label", "key", "tier_hint",
    "success_count"}, ...]
    """
    kv = await db.kv_get_all(scope=user_id)
    raw = kv.get(_KV_TTS_API_KEYS) or ""
    if raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [
                    {
                        "id": e.get("id") or _gen_key_id(),
                        "label": e.get("label", ""),
                        "key": e.get("key", ""),
                        # Tier-Detection-Felder (backward-compat: Default-Werte)
                        "tier_hint": e.get("tier_hint", "unknown"),
                        "success_count": int(e.get("success_count", 0)),
                    }
                    for e in parsed if isinstance(e, dict) and e.get("key")
                ]
        except (json.JSONDecodeError, TypeError):
            log.warning("Multi-Key-JSON kaputt, fallback auf leer.")
            return []
    # Migration: legacy single-slot in Pool übernehmen
    migrated: list[dict] = []
    legacy = (kv.get(_KV_TTS_API_KEY) or "").strip()
    if legacy:
        migrated.append({
            "id": _gen_key_id(), "label": "(migriert)", "key": legacy,
            "tier_hint": "unknown", "success_count": 0,
        })
    # Hinweis: ein reiner Image-Gen-Key wird NICHT in den Pool migriert.
    # Single-Key-Aufrufer holen ihn über _resolve_user_tts_api_key's eigenen
    # Image-Fallback (source="image").
    return migrated


async def _save_tts_api_keys(user_id: str, entries: list[dict]) -> None:
    """Speichert die Multi-Key-Liste persistent (JSON in KV)."""
    payload = json.dumps(
        [
            {
                "id": e["id"], "label": e.get("label", ""), "key": e["key"],
                "tier_hint": e.get("tier_hint", "unknown"),
                "success_count": int(e.get("success_count", 0)),
            }
            for e in entries
        ],
        separators=(",", ":"),
    )
    await db.kv_set_many({_KV_TTS_API_KEYS: payload}, scope=user_id)


async def _resolve_user_tts_api_key(user_id: str) -> tuple[str | None, str]:
    """Liefert (api_key, source) für TTS — Legacy-Helper, wird noch von
    Single-Key-Aufrufern genutzt. Bei Multi-Key gibt er den ERSTEN Key zurück.

       - source = "tts"   → mind. 1 Key im Pool (oder Legacy-Single-Slot)
       - source = "image" → Fallback: Image-Gen-Key wird mitgenutzt
       - source = "none"  → kein Key vorhanden
    """
    keys = await _load_tts_api_keys(user_id)
    if keys:
        return keys[0]["key"], "tts"
    kv = await db.kv_get_all(scope=user_id)
    fallback = (kv.get(_KV_IMAGE_API_KEY_LEGACY_FALLBACK) or "").strip() or None
    if fallback:
        return fallback, "image"
    return None, "none"


# === Rate-Limiter für Multi-Key-Pool ===========================================
# Pro Key tracken wir die Timestamps der letzten Calls in einem rollenden
# 60-Sekunden-Fenster.
#
# Live-getestet Mai 2026 (drei separate Free-Tier-Keys aus drei Projekten):
#   - gemini-2.5-flash-preview-tts: **3 RPM** rolling pro Projekt (per-Key)
#   - gemini-3.1-flash-tts-preview: 10 RPD pro Projekt — unbrauchbar, nutzen wir nicht
# Quota-Metric vom Server: GenerateRequestsPerMinutePerProjectPerModel-FreeTier
#
# Wir setzen das Limit auf 3 (das echte Limit), nicht konservativ niedriger —
# bei Multi-Key-Pool mit Round-Robin verteilt sich der Burst sauber, und
# der Limiter wartet defensiv wenn ein Key zu voll wird.
import collections as _collections
import threading as _threading

MAX_REQUESTS_PER_KEY_PER_MINUTE = 3
_RL_WINDOW_SEC = 60.0
# Pro API-Key: Deque von Timestamps. Cross-Request shared in-process.
# Lock weil asyncio-tasks parallel zugreifen können.
_rl_timestamps: dict[str, "_collections.deque[float]"] = {}
# Pro API-Key: Zeitpunkt bis zu dem der Key „burned" ist (Google hat 429
# zurückgegeben). Solange der Key burned ist, skippt der Picker ihn.
# Für RPD-Limit setzen wir typischerweise 24h-Burn, für RPM 60s.
_rl_burned_until: dict[str, float] = {}
_rl_lock = _threading.Lock()

# Cloud-TTS-Setup ist GLOBAL (ein Service-Account-JSON für den ganzen Server),
# also ist die „nicht nutzbar"-Markierung auch global. Vorher per-User → bei
# einem User-Burn haben andere User weiter 25 parallele Chunks gefeuert und
# alle in denselben BILLING_DISABLED reingelaufen.
# Wert ist der monotonic()-Zeitpunkt bis zu dem Cloud-TTS gesperrt bleibt.
# 0.0 = nicht gesperrt.
_CLOUD_TTS_UNAVAILABLE_UNTIL: float = 0.0


def _seconds_until_utc_midnight() -> float:
    """Sekunden bis zur nächsten 00:00 UTC. Google RPD-Quotas reseten dann."""
    from datetime import datetime, timezone, timedelta
    now_utc = datetime.now(timezone.utc)
    tomorrow_midnight = (now_utc + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )
    delta = (tomorrow_midnight - now_utc).total_seconds()
    return max(60.0, delta)  # min 60s defensive


def mark_key_burned(api_key: str, retry_delay_sec: float, quota_id: str = "") -> None:
    """Markiert einen API-Key als „burned" bis das Limit reseted.

    Sonderbehandlung:
    - RPD-Quota (PerDay/RequestsPerDay im quota_id): bis nächste UTC-Mitternacht.
      Google reseted Daily-Quotas dann, NICHT 24h nach dem Burn — die alte
      Fixed-24h-Logik hätte den Key bis zu 16h unnötig länger gesperrt.
    - Andere Quotas (RPM): Server-suggested retryDelay (mind. 60s).
    - Unbekannte/leere quota_id OHNE retryDelay-Hint: defensiv als RPD
      behandeln (bis UTC-Mitternacht). Sonst würde ein RPD-erschöpfter Key
      mit 60s viel zu früh wieder probiert und feuert sofort wieder 429.
    """
    if not api_key:
        return
    if "PerDay" in quota_id or "RequestsPerDay" in quota_id:
        burn_sec = _seconds_until_utc_midnight()
    elif not quota_id and retry_delay_sec <= 0:
        # Kein Hinweis welcher Quota-Typ — vorsichtshalber bis Mitternacht.
        burn_sec = _seconds_until_utc_midnight()
    else:
        burn_sec = max(60.0, retry_delay_sec)
    with _rl_lock:
        _rl_burned_until[api_key] = _time.monotonic() + burn_sec
    # Mensch-lesbare Dauer im Log
    if burn_sec >= 3600:
        dur = f"{burn_sec / 3600:.1f}h"
    elif burn_sec >= 60:
        dur = f"{burn_sec / 60:.0f}min"
    else:
        dur = f"{burn_sec:.0f}s"
    log.warning(
        "API-Key …%s burned für %s (quota=%s).",
        api_key[-6:], dur, quota_id or "?",
    )


def _is_burned(api_key: str, now: float) -> bool:
    with _rl_lock:
        until = _rl_burned_until.get(api_key)
        if until is None:
            return False
        if now >= until:
            # Expired → cleanup
            del _rl_burned_until[api_key]
            return False
        return True


def _rl_can_use(api_key: str, now: float) -> tuple[bool, float]:
    """Prüft ob `api_key` JETZT verwendet werden darf. Wenn ja, registriert
    den Call und gibt (True, 0.0) zurück. Wenn nein, returnt (False, wait_sec)
    — Caller soll wait_sec warten ODER einen anderen Key versuchen."""
    with _rl_lock:
        dq = _rl_timestamps.setdefault(api_key, _collections.deque())
        # Alte Einträge aus dem Fenster werfen
        while dq and (now - dq[0]) > _RL_WINDOW_SEC:
            dq.popleft()
        if len(dq) < MAX_REQUESTS_PER_KEY_PER_MINUTE:
            dq.append(now)
            return True, 0.0
        # Wann wird der älteste Eintrag aus dem Fenster fallen?
        wait = _RL_WINDOW_SEC - (now - dq[0])
        return False, max(0.0, wait)


def _rl_remaining(api_key: str, now: float) -> int:
    """Wieviele Slots im aktuellen 60s-Fenster für `api_key` frei."""
    with _rl_lock:
        dq = _rl_timestamps.get(api_key)
        if not dq:
            return MAX_REQUESTS_PER_KEY_PER_MINUTE
        while dq and (now - dq[0]) > _RL_WINDOW_SEC:
            dq.popleft()
        if not dq:
            # Leere Deque (alle Timestamps gefallen) → Eintrag aufräumen,
            # damit _rl_timestamps nicht unbegrenzt pro je gesehenem Key wächst.
            del _rl_timestamps[api_key]
            return MAX_REQUESTS_PER_KEY_PER_MINUTE
        return max(0, MAX_REQUESTS_PER_KEY_PER_MINUTE - len(dq))


def _rl_peek_wait(api_key: str, now: float) -> float:
    """Wie lange bis dieser Key wieder einen Slot hat. 0.0 wenn frei.
    Reserviert KEINEN Slot (anders als _rl_can_use)."""
    with _rl_lock:
        dq = _rl_timestamps.get(api_key)
        if not dq:
            return 0.0
        while dq and (now - dq[0]) > _RL_WINDOW_SEC:
            dq.popleft()
        if not dq:
            # Leere Deque aufräumen (siehe _rl_remaining).
            del _rl_timestamps[api_key]
            return 0.0
        if len(dq) < MAX_REQUESTS_PER_KEY_PER_MINUTE:
            return 0.0
        return max(0.0, _RL_WINDOW_SEC - (now - dq[0]))


async def acquire_tts_key_for_call(api_keys: list[str], timeout_sec: float = 30.0) -> str | None:
    """Wählt den besten Key aus dem Pool für einen TTS-Call.

    Logik:
      1. Burned Keys (kürzlich 429-Response) komplett skippen
      2. Picke den Key mit den meisten freien Slots im 60-s-Fenster
      3. Reserviere einen Slot für ihn → return key
      4. Wenn KEIN Key Slots übrig hat: warte bis irgendwo einer freiwird

    Returnt den gewählten Key, oder None bei Timeout / alle burned.

    Log-Verhalten: bei „alle burned" wird DEBUG geloggt, nicht WARNING — sonst
    spammt jeder einzelne Chunk-Pick die gleiche Zeile. Der Caller (im Stream-
    Wrapper) loggt einmal WARNING wenn er Pool-erschöpft erkennt.
    """
    import asyncio as _asyncio
    if not api_keys:
        return None
    deadline = _time.monotonic() + timeout_sec
    while True:
        now = _time.monotonic()
        available = [k for k in api_keys if not _is_burned(k, now)]
        if not available:
            log.debug("acquire_tts_key: ALLE %d Keys burned — gebe auf.", len(api_keys))
            return None
        scored = sorted(available, key=lambda k: -_rl_remaining(k, now))
        best = scored[0]
        ok, _ = _rl_can_use(best, now)
        if ok:
            return best
        # Niemand frei → kürzeste Wartezeit über alle nicht-burnten Keys
        min_wait = min((_rl_peek_wait(k, now) for k in available), default=_RL_WINDOW_SEC)
        if _time.monotonic() + min_wait > deadline:
            log.debug("acquire_tts_key: Timeout (%.1fs) — %d/%d Keys verfügbar, alle voll",
                      timeout_sec, len(available), len(api_keys))
            return None
        sleep_for = max(0.1, min(min_wait, 5.0))
        log.debug("acquire_tts_key: alle %d non-burned Keys voll, sleep %.2fs",
                  len(available), sleep_for)
        await _asyncio.sleep(sleep_for)


async def _resolve_user_tts_provider(user_id: str) -> tuple[str, str | None]:
    """Liest per-User: welcher Provider ist aktiv + sein API-Key (für gemini_api).

    Returnt (provider, api_key). `api_key` ist None falls cloud_tts.
    Defaults: provider = cloud_tts (1M Zeichen/Monat Free via Studio-Voices).
    """
    kv = await db.kv_get_all(scope=user_id)
    return await _resolve_provider_with_kv(kv, user_id)


async def _resolve_provider_with_kv(kv: dict, user_id: str) -> tuple[str, str | None]:
    """Wie _resolve_user_tts_provider, aber wiederverwendet ein bereits
    geladenes KV-Dict (spart einen DB-Roundtrip wenn der Aufrufer das
    KV eh schon hat).

    Smart-Default-Logik wenn der User noch keinen Provider gesetzt hat:
      1. Service-Account vorhanden → cloud_tts (beste Voice-Quality + Free-Tier)
      2. Gemini-API-Key vorhanden → gemini_api (Multi-Key-Pool nutzbar)
      3. Sonst                    → edge_tts (Zero-Setup, immer verfügbar)

    Bei explizit gesetztem KV-Wert wird der respektiert (egal ob das Setup
    dazu passt — der User soll merken wenn er was Falsches gewählt hat).
    """
    raw = (kv.get(_KV_TTS_PROVIDER) or "").strip()
    if raw and raw in tts.VALID_PROVIDERS:
        provider = raw
    else:
        if raw:
            log.warning("Ungültiger TTS-Provider %r in user-settings, fallback auf Smart-Default",
                        raw)
        # Smart-Default basierend auf vorhandenem Setup
        cloud_ok = tts.get_config() is not None
        if cloud_ok:
            provider = tts.PROVIDER_CLOUD_TTS
        else:
            test_key, _src = await _resolve_user_tts_api_key(user_id)
            if test_key:
                provider = tts.PROVIDER_GEMINI_API
            else:
                provider = tts.PROVIDER_EDGE_TTS
    api_key = None
    if provider == tts.PROVIDER_GEMINI_API:
        api_key, _src = await _resolve_user_tts_api_key(user_id)
    return provider, api_key


async def _resolve_user_tts_model(user_id: str) -> str:
    """Liest per-User das gewählte TTS-Modell (für gemini-Voices). Fallback
    auf Server-Default falls unset/invalid."""
    kv = await db.kv_get_all(scope=user_id)
    return _resolve_model_from_kv(kv)


def _resolve_model_from_kv(kv: dict) -> str:
    """Pure-Function-Variante — kein DB-Zugriff, nutzt bereits geladenes KV."""
    raw = (kv.get(_KV_TTS_MODEL) or "").strip()
    if raw and tts.is_valid_gemini_model(raw):
        return raw
    return tts.default_gemini_model_id()


def _resolve_chunking_from_kv(kv: dict, provider: str) -> bool:
    """Liest die Chunking-Einstellung des Users aus dem KV-Dict.

    Drei Werte möglich:
      - "1" → User hat Chunking explizit AN
      - "0" → User hat Chunking explizit AUS
      - leer/None → Provider-Default greift (`tts.chunking_default_for`)
    """
    raw = (kv.get(_KV_TTS_CHUNKING_ENABLED) or "").strip()
    if raw == "1":
        return True
    if raw == "0":
        return False
    return tts.chunking_default_for(provider)


async def _resolve_tts_provider_model_and_key(
    user_id: str,
) -> tuple[str, str | None, str, bool]:
    """Kombi-Resolver: lädt KV einmal, returnt (provider, api_key, model_id, chunking_enabled).
    Spart DB-Roundtrips im Audio-Stream-Endpoint."""
    kv = await db.kv_get_all(scope=user_id)
    provider, api_key = await _resolve_provider_with_kv(kv, user_id)
    model_id = _resolve_model_from_kv(kv)
    chunking_enabled = _resolve_chunking_from_kv(kv, provider)
    return provider, api_key, model_id, chunking_enabled


async def _build_tts_status(user_id: str) -> TtsStatusDto:
    """Baut den per-User TtsStatusDto inkl. Provider-Konfigurations-Stati."""
    cfg = tts.get_config()
    cloud_ok = cfg is not None
    kv = await db.kv_get_all(scope=user_id)
    provider, api_key = await _resolve_provider_with_kv(kv, user_id)
    gemini_ok = bool(api_key)
    if provider == tts.PROVIDER_GEMINI_API:
        configured = gemini_ok
    elif provider == tts.PROVIDER_EDGE_TTS:
        configured = True  # Edge-TTS braucht keine Credentials
    else:
        configured = cloud_ok
    # Chunking-Setting (explicit vs. provider-default)
    chunking_raw = (kv.get(_KV_TTS_CHUNKING_ENABLED) or "").strip()
    chunking_explicit = chunking_raw in ("0", "1")
    chunking_enabled = _resolve_chunking_from_kv(kv, provider)
    # Welcher Key liegt aktuell im TTS-Slot + wie viele insgesamt?
    pool = await _load_tts_api_keys(user_id)
    if pool:
        first_key = pool[0]["key"]
        source = "tts"
    else:
        first_key, source = await _resolve_user_tts_api_key(user_id)
    chars_this_month = await _read_cloud_tts_chars(user_id)
    current_model = await _resolve_user_tts_model(user_id)
    available_models = [
        TtsModelDto(
            id=m["id"],
            label=m["label"],
            tier=m.get("tier", ""),
            price_hint=m.get("price_hint", ""),
            default=bool(m.get("default", False)),
        )
        for m in tts.AVAILABLE_GEMINI_TTS_MODELS
    ]
    return TtsStatusDto(
        configured=configured,
        provider=provider,
        cloud_tts_configured=cloud_ok,
        gemini_api_configured=gemini_ok,
        gemini_api_key_masked=_mask_key(first_key) if first_key else None,
        gemini_api_key_source=source,
        gemini_api_key_count=len(pool),
        project_id=cfg.project_id if cfg else None,
        client_email=cfg.client_email if cfg else None,
        cloud_tts_chars_this_month=chars_this_month,
        default_voice=tts.default_voice_for(provider),
        voices=[TtsVoiceDto(**v) for v in tts.CURATED_VOICES],
        tts_model=current_model,
        available_models=available_models,
        chunking_enabled=chunking_enabled,
        chunking_explicit=chunking_explicit,
    )


@app.get("/tts/status", response_model=TtsStatusDto)
async def tts_status(user=Depends(require_user)) -> TtsStatusDto:
    return await _build_tts_status(user["id"])


@app.put("/tts/provider", response_model=TtsStatusDto)
async def tts_set_provider(body: TtsProviderRequest, user=Depends(require_user)) -> TtsStatusDto:
    """Setzt den TTS-Provider des aktuellen Users.

    `provider`: "gemini_api" (sicherer Pfad, AI-Studio-Cap greift) oder
    "cloud_tts" (Service-Account-JSON, kein direkter Hard-Cap)."""
    prov = (body.provider or "").strip()
    if prov not in tts.VALID_PROVIDERS:
        raise HTTPException(400, f"Invalid provider {prov!r}. "
                                  f"Allowed: {sorted(tts.VALID_PROVIDERS)}")
    await db.kv_set_many({_KV_TTS_PROVIDER: prov}, scope=user["id"])
    log.info("TTS-Provider von user=%s auf %s gesetzt", user["id"], prov)
    # Provider-Wechsel ist user-spezifisch und sagt nichts über den globalen
    # Cloud-TTS-Setup-Status aus → nicht den Cache leeren.
    return await _build_tts_status(user["id"])


@app.put("/tts/chunking", response_model=TtsStatusDto)
async def tts_set_chunking(body: TtsChunkingRequest, user=Depends(require_user)) -> TtsStatusDto:
    """Setzt die Chunking-Option des Users.

    `enabled=True/False` setzt den expliziten Wert. `enabled=None` löscht das
    KV-Override und fällt auf den Provider-Default zurück."""
    if body.enabled is None:
        # Reset auf Provider-Default → KV-Eintrag löschen
        await db.kv_set_many({_KV_TTS_CHUNKING_ENABLED: ""}, scope=user["id"])
        log.info("TTS-Chunking von user=%s auf Provider-Default zurückgesetzt", user["id"])
    else:
        val = "1" if body.enabled else "0"
        await db.kv_set_many({_KV_TTS_CHUNKING_ENABLED: val}, scope=user["id"])
        log.info("TTS-Chunking von user=%s auf %s gesetzt", user["id"], val)
    return await _build_tts_status(user["id"])


@app.put("/tts/model", response_model=TtsStatusDto)
async def tts_set_model(body: TtsModelRequest, user=Depends(require_user)) -> TtsStatusDto:
    """Setzt das aktive TTS-Modell für gemini-Voices (Provider=gemini_api ODER
    Cloud-TTS mit gemini-Voice). Erlaubt nur Werte aus
    `tts.AVAILABLE_GEMINI_TTS_MODELS`."""
    mid = (body.model_id or "").strip()
    if not tts.is_valid_gemini_model(mid):
        allowed = [m["id"] for m in tts.AVAILABLE_GEMINI_TTS_MODELS]
        raise HTTPException(400, f"Invalid TTS model {mid!r}. "
                                  f"Allowed: {allowed}")
    await db.kv_set_many({_KV_TTS_MODEL: mid}, scope=user["id"])
    log.info("TTS-Modell von user=%s auf %s gesetzt", user["id"], mid)
    return await _build_tts_status(user["id"])


@app.put("/tts/api-key", response_model=TtsStatusDto)
async def tts_set_api_key(body: dict, user=Depends(require_user)) -> TtsStatusDto:
    """Setzt den **TTS-spezifischen** Gemini-API-Key des Users (per User-scoped).

    Bewusst getrennt vom Image-Gen-Key, damit User Image-Gen über ein Paid-
    Konto laufen lassen können (z.B. mit $10-AI-Pro-Credit für Nano Banana Pro)
    und TTS über einen Free-Tier-Key (anderer Account oder Projekt ohne
    Billing). Beide Keys leben pro User parallel.
    """
    key = (body.get("api_key") or "").strip()
    if not key:
        raise HTTPException(400, "Leerer API-Key.")
    if not key.startswith("AIza"):
        raise HTTPException(
            400, "Sieht nicht aus wie ein Google-API-Key (sollte mit 'AIza' beginnen).",
        )
    await db.kv_set_many({_KV_TTS_API_KEY: key}, scope=user["id"])
    log.info("TTS-API-Key von user=%s gespeichert (masked: %s)",
             user["id"], _mask_key(key))
    return await _build_tts_status(user["id"])


@app.delete("/tts/api-key", response_model=TtsStatusDto)
async def tts_delete_api_key(user=Depends(require_user)) -> TtsStatusDto:
    """Entfernt den TTS-API-Key des Users. Fallback auf den Image-Key (falls
    vorhanden) greift dann automatisch wieder."""
    await db.kv_set_many({_KV_TTS_API_KEY: ""}, scope=user["id"])
    log.info("TTS-API-Key von user=%s entfernt", user["id"])
    return await _build_tts_status(user["id"])


# ---------- Multi-Key-Pool (für Free-Tier-Throughput) -----------------------

def _entries_to_dto(entries: list[dict]) -> list[TtsApiKeyEntryDto]:
    return [
        TtsApiKeyEntryDto(
            id=e["id"],
            label=e.get("label", ""),
            masked=_mask_key(e.get("key", "")),
            tier_hint=e.get("tier_hint", "unknown"),
            success_count=int(e.get("success_count", 0)),
        )
        for e in entries
    ]


# Schwellenwert: wenn ein Key SUCCESS_COUNT_PAID_THRESHOLD erfolgreiche Calls
# hatte ohne ein FreeTier-429 → wird als "likely_paid" markiert (ein Free-Tier
# wäre bei dieser Menge schon ins 10-RPD-Limit gerannt).
SUCCESS_COUNT_PAID_THRESHOLD = 15


# Pro User ein asyncio-Lock um KV-Schreibungen für den Pool zu serialisieren.
# Ohne den würden parallele 429/Success-Updates aus 22 Chunks sich gegenseitig
# überschreiben (load → modify → save Race).
#
# WICHTIG: das Lazy-Erzeugen der Per-User-Locks war früher eine Race: zwei
# parallele Coroutinen sahen beide `user_id not in dict`, beide haben einen
# eigenen Lock erzeugt, eine davon hat überschrieben — und damit haben sich
# kurz zwei separate Locks parallel verwendet, also kein gegenseitiger
# Ausschluss mehr. `dict.setdefault` ist atomar (GIL) und behebt das.
_tier_update_locks: dict[str, "asyncio.Lock"] = {}  # type: ignore[name-defined]


def _get_tier_lock(user_id: str):
    import asyncio as _asyncio
    existing = _tier_update_locks.get(user_id)
    if existing is not None:
        return existing
    # setdefault liefert immer denselben Lock, auch wenn ein paralleler Caller
    # gerade dieselbe Zeile ausgeführt hat — die parallele Allokation wird
    # einfach verworfen.
    return _tier_update_locks.setdefault(user_id, _asyncio.Lock())


async def _update_key_tier_on_429(user_id: str, api_key: str, quota_id: str) -> None:
    """Wird vom 429-Handler aufgerufen wenn ein Key 429t. Wenn das ein
    FreeTier-Quota war → tier_hint = 'free' setzen."""
    if "FreeTier" not in quota_id:
        return
    async with _get_tier_lock(user_id):
        entries = await _load_tts_api_keys(user_id)
        changed = False
        for e in entries:
            if e["key"] == api_key and e.get("tier_hint") != "free":
                e["tier_hint"] = "free"
                changed = True
        if changed:
            await _save_tts_api_keys(user_id, entries)


async def _update_key_tier_on_success(user_id: str, api_key: str) -> None:
    """Wird nach jedem erfolgreichen TTS-Call aufgerufen. Inkrementiert
    success_count + setzt tier_hint=likely_paid sobald Schwelle erreicht."""
    async with _get_tier_lock(user_id):
        entries = await _load_tts_api_keys(user_id)
        changed = False
        for e in entries:
            if e["key"] == api_key:
                old = int(e.get("success_count", 0))
                e["success_count"] = old + 1
                if (
                    e.get("tier_hint") == "unknown"
                    and e["success_count"] >= SUCCESS_COUNT_PAID_THRESHOLD
                ):
                    e["tier_hint"] = "likely_paid"
                changed = True
        if changed:
            await _save_tts_api_keys(user_id, entries)


# Pro Monat ein eigener KV-Counter für Cloud-TTS-Zeichen pro User. Damit kann
# die UI live anzeigen wieviel vom 1-Mio-Free-Contingent verbraucht ist.
def _current_month_key() -> str:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    return f"cloud_tts_chars_{now.year:04d}-{now.month:02d}"


async def _add_cloud_tts_chars(user_id: str, n: int) -> None:
    """Erhöht den Monats-Zähler für Cloud-TTS-Zeichen-Verbrauch."""
    if n <= 0:
        return
    key = _current_month_key()
    async with _get_tier_lock(user_id):
        kv = await db.kv_get_all(scope=user_id)
        try:
            current = int(kv.get(key) or "0")
        except (TypeError, ValueError):
            current = 0
        await db.kv_set_many({key: str(current + n)}, scope=user_id)


async def _read_cloud_tts_chars(user_id: str) -> int:
    """Liest den Monats-Zähler. 0 wenn noch nichts verbraucht."""
    key = _current_month_key()
    kv = await db.kv_get_all(scope=user_id)
    try:
        return int(kv.get(key) or "0")
    except (TypeError, ValueError):
        return 0


async def _validate_key(api_key: str, timeout_sec: float = 10.0) -> tuple[bool, str]:
    """Macht einen einfachen Text-Call (gemini-2.5-flash, KEIN TTS — spart
    TTS-Tageskontingent). Returnt (ok, error_message).

    Bei 200 OK: Key funktioniert. Tier bleibt 'unknown' bis erste TTS-Calls.
    Bei 4xx/Netzwerk-Fehler: Key wird abgelehnt mit klarer Message.
    """
    import httpx as _httpx
    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        "models/gemini-2.5-flash:generateContent"
    )
    try:
        async with _httpx.AsyncClient(timeout=timeout_sec) as cli:
            r = await cli.post(
                url, params={"key": api_key},
                headers={"Content-Type": "application/json"},
                json={"contents": [{"parts": [{"text": "Hi"}]}]},
            )
    except _httpx.TimeoutException:
        return False, "Timeout beim Test-Call (Netzwerk-Problem?)."
    except _httpx.RequestError as e:
        return False, f"Netzwerk-Fehler: {type(e).__name__}"
    if r.status_code == 200:
        return True, ""
    # Fehlermessage extrahieren
    msg = r.text[:200]
    try:
        err = (r.json() or {}).get("error") or {}
        msg = err.get("message") or msg
    except Exception:
        pass
    if r.status_code == 400 and "API key not valid" in msg:
        return False, "Key ungültig (Google sagt 'API key not valid')."
    if r.status_code == 403:
        return False, "Key gesperrt oder API nicht aktiviert (403)."
    return False, f"HTTP {r.status_code}: {msg[:160]}"


@app.get("/tts/api-keys", response_model=TtsApiKeysDto)
async def tts_list_api_keys(user=Depends(require_user)) -> TtsApiKeysDto:
    """Liste aller Gemini-API-Keys im Multi-Key-Pool dieses Users.
    Server verteilt TTS-Calls per Round-Robin + Rate-Limiter auf die Keys."""
    entries = await _load_tts_api_keys(user["id"])
    return TtsApiKeysDto(keys=_entries_to_dto(entries))


@app.post("/tts/api-keys", response_model=TtsApiKeysDto)
async def tts_add_api_key(body: TtsApiKeyAddRequest,
                          user=Depends(require_user)) -> TtsApiKeysDto:
    """Fügt einen neuen Key in den Multi-Key-Pool. Doppelte Keys (gleicher
    String) werden mit 409 abgelehnt. Beim Hinzufügen wird ein günstiger
    Test-Call gegen `gemini-2.5-flash` (text-only, KEIN TTS-Quota) gemacht
    um sicherzustellen dass der Key überhaupt funktioniert."""
    key = body.api_key.strip()
    if not key:
        raise HTTPException(400, "Leerer API-Key.")
    if not key.startswith("AIza"):
        raise HTTPException(
            400, "Sieht nicht aus wie ein Google-API-Key (sollte mit 'AIza' beginnen).",
        )
    entries = await _load_tts_api_keys(user["id"])
    if any(e["key"] == key for e in entries):
        raise HTTPException(409, "Dieser Key ist bereits im Pool.")
    # Validation-Call (text-only, billig, kein TTS-Quota-Verbrauch)
    ok, err_msg = await _validate_key(key)
    if not ok:
        raise HTTPException(400, f"Key-Test fehlgeschlagen: {err_msg}")
    entries.append({
        "id": _gen_key_id(),
        "label": (body.label or "").strip(),
        "key": key,
        "tier_hint": "unknown",
        "success_count": 0,
    })
    await _save_tts_api_keys(user["id"], entries)
    log.info("TTS-Key zu Pool für user=%s hinzugefügt (jetzt %d Keys).",
             user["id"], len(entries))
    return TtsApiKeysDto(keys=_entries_to_dto(entries))


@app.delete("/tts/api-keys/{key_id}", response_model=TtsApiKeysDto)
async def tts_remove_api_key(key_id: str,
                              user=Depends(require_user)) -> TtsApiKeysDto:
    """Entfernt einen einzelnen Key aus dem Pool."""
    entries = await _load_tts_api_keys(user["id"])
    new_entries = [e for e in entries if e["id"] != key_id]
    if len(new_entries) == len(entries):
        raise HTTPException(404, "Key nicht im Pool gefunden.")
    await _save_tts_api_keys(user["id"], new_entries)
    log.info("TTS-Key %s aus Pool von user=%s entfernt (jetzt %d Keys).",
             key_id, user["id"], len(new_entries))
    return TtsApiKeysDto(keys=_entries_to_dto(new_entries))


@app.patch("/tts/api-keys/{key_id}", response_model=TtsApiKeysDto)
async def tts_relabel_api_key(key_id: str, body: dict,
                               user=Depends(require_user)) -> TtsApiKeysDto:
    """Setzt das Label eines Keys neu (Body: `{label: "..."}`)."""
    label = (body.get("label") or "").strip()
    entries = await _load_tts_api_keys(user["id"])
    found = False
    for e in entries:
        if e["id"] == key_id:
            e["label"] = label
            found = True
            break
    if not found:
        raise HTTPException(404, "Key nicht im Pool gefunden.")
    await _save_tts_api_keys(user["id"], entries)
    return TtsApiKeysDto(keys=_entries_to_dto(entries))


@app.put("/tts/credentials", response_model=TtsStatusDto)
async def tts_set_credentials(body: TtsCredentialsRequest, user=Depends(require_admin)) -> TtsStatusDto:
    try:
        tts.save_credentials(body.credentials_json)
        tts.reset_client()
    except ValueError as e:
        raise HTTPException(400, str(e))
    # Cloud-TTS-„nicht-nutzbar"-Marker zurücksetzen: das frische JSON kann
    # plötzlich funktionieren, auch wenn die alten Credentials BILLING_DISABLED
    # geliefert hatten. Sonst antwortet der audio-Endpoint für 5 min trotz
    # gültigem Setup weiter mit 503.
    global _CLOUD_TTS_UNAVAILABLE_UNTIL
    _CLOUD_TTS_UNAVAILABLE_UNTIL = 0.0
    # Billing-Status-Cache leeren — frische Credentials = potenziell anderes
    # Projekt/Service-Account, alte Spend-Daten irrelevant.
    billing.invalidate_cache()
    return await _build_tts_status(user["id"])


@app.delete("/tts/credentials", status_code=status.HTTP_204_NO_CONTENT)
async def tts_delete_credentials(user=Depends(require_admin)):  # noqa: ARG001
    tts.delete_credentials()
    tts.reset_client()
    global _CLOUD_TTS_UNAVAILABLE_UNTIL
    _CLOUD_TTS_UNAVAILABLE_UNTIL = 0.0
    return JSONResponse(status_code=204, content=None)


@app.get("/messages/{message_id}/audio")
async def tts_message_audio(
    message_id: int,
    voice: str | None = None,
    rate: float | None = None,
    token: str | None = None,  # noqa: ARG001 — von Dep konsumiert
    user=Depends(require_user_header_or_query),
):
    """Synthetisiert den Inhalt einer Message und streamt das Audio.

    Provider richtet sich nach den per-User-Settings (default: gemini_api).
    Cloud-TTS = audio/mpeg-Stream, Gemini-API = audio/wav-Stream.
    `rate` wird auf [0.25, 2.0] geclamped; Default 1.0.
    """
    # Per-User Provider + API-Key + Modell ermitteln (eine DB-Query statt zwei)
    provider, api_key, chosen_model, chunking_enabled = await _resolve_tts_provider_model_and_key(user["id"])
    if provider == tts.PROVIDER_CLOUD_TTS and not tts.is_configured():
        raise HTTPException(
            503,
            "Cloud-TTS ist nicht konfiguriert. Lade ein Service-Account-JSON aus "
            "der Google Cloud Console (Projekt mit aktivem Billing-Account) in "
            "den Einstellungen hoch."
        )
    if provider == tts.PROVIDER_GEMINI_API and not api_key:
        raise HTTPException(
            503,
            "Provider 'Gemini API' aktiv aber kein API-Key gesetzt. "
            "Trage deinen AI-Studio-API-Key in den Bilder-Einstellungen ein "
            "— der wird für TTS mitgenutzt."
        )

    # Pre-Flight: Cloud-TTS server-weit als „nicht nutzbar" markiert
    # (BILLING_DISABLED o.ä.) → direkt 503, statt 25 Chunks parallel zu feuern
    # und alle in einem Stream-Crash zu enden.
    # Hinweis: KEIN Vorschlag „auf Gemini API umschalten" — das $10-AI-Pro-
    # Kontingent läuft NUR über Cloud-TTS, der korrekte Fix ist Billing
    # aktivieren / Projekt mit Billing-Account verknüpfen.
    if provider == tts.PROVIDER_CLOUD_TTS:
        if _time.monotonic() < _CLOUD_TTS_UNAVAILABLE_UNTIL:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Cloud TTS API ist für dein Google-Cloud-Projekt aktuell nicht "
                    "nutzbar (zuletzt: Billing disabled, API nicht aktiviert oder "
                    "Permission denied). Geh in Cloud Console → Billing und "
                    "verknüpfe das Projekt mit deinem Billing-Account."
                ),
            )

    # Message aus DB holen UND prüfen, dass die zugehörige Conversation dem
    # aktuellen User gehört. Sonst könnte ein User mit gültigem Token jede
    # beliebige Message vorlesen lassen.
    from pocket_claude.db import get_db
    async with get_db() as conn:
        cur = await conn.execute(
            """
            SELECT m.content, m.role
            FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            WHERE m.id = ? AND c.user_id = ?
            """,
            (message_id, user["id"]),
        )
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Message nicht gefunden.")
    content = row["content"]
    if not content or not content.strip():
        raise HTTPException(400, "Message hat keinen Text.")

    chosen_voice = (voice or tts.default_voice_for(provider)).strip()
    chosen_rate = rate if rate is not None else tts.DEFAULT_SPEED
    stream_media_type = tts.media_type_for(provider)

    # Pre-Generation-Cache (provider ist Teil des Keys, damit MP3- und WAV-
    # Cache nicht kollidieren wenn der User mid-Session umschaltet).
    cached = await tts_cache.get(message_id, chosen_voice, chosen_rate, provider)
    if cached is not None:
        log.info(
            "TTS-Cache HIT msg=%d voice=%s rate=%.2f provider=%s (%d KB, %s)",
            message_id, chosen_voice, chosen_rate, provider,
            len(cached.audio) // 1024, cached.media_type,
        )
        from fastapi.responses import Response
        return Response(
            content=cached.audio,
            media_type=cached.media_type,
            headers={
                "Cache-Control": "no-store",
                "Content-Length": str(len(cached.audio)),
                "X-Pocket-Claude-Cache": "hit",
                "X-Pocket-Claude-Provider": provider,
            },
        )

    # Multi-Key-Picker (nur wenn Pool >1 Keys; sonst Single-Key-Pfad).
    # `max_chunks` ist abhängig von Pool-Größe + Provider:
    #  - Cloud TTS: keine Per-Minute-Limits → unbeschränkt (= None)
    #  - Gemini API mit Pool: N Keys × 3 RPM = 3N parallele Slots verfügbar.
    #    Limit setzen wir bei `pool_size * 3` (= komplettes Burst-Budget eines
    #    rolling 60s-Fensters), damit Streaming-Latenz minimiert wird ohne
    #    aufs Quota-Limit zu prallen.
    #  - Gemini API Single-Key: max 3 Chunks (1× RPM des 2.5er-Models).
    picker = None
    max_chunks: int | None = None
    if provider == tts.PROVIDER_GEMINI_API:
        pool = await _load_tts_api_keys(user["id"])
        pool_size = len(pool)
        if pool_size > 1:
            pool_keys = [e["key"] for e in pool]
            # Frühe Prüfung: alle Pool-Keys burned? → klarer 503 statt halb-
            # leerer Stream der dann gracefully endet.
            now = _time.monotonic()
            non_burned = [k for k in pool_keys if not _is_burned(k, now)]
            if not non_burned:
                raise HTTPException(
                    status_code=503,
                    detail=(
                        f"Alle {pool_size} TTS-API-Keys haben heute das "
                        "Free-Tier-Tageskontingent (10 Calls/Tag/Key) erreicht. "
                        "Reset bei Mitternacht UTC. Falls Du jetzt unbedingt "
                        "weiter Audio brauchst: füge in den TTS-Einstellungen "
                        "weitere AI-Studio-API-Keys hinzu (aus separaten "
                        "Projekten/Accounts) oder switche temporär auf Cloud-TTS."
                    ),
                )
            log.info("TTS-Audio: Multi-Key-Pool mit %d Keys aktiv (%d non-burned)",
                     pool_size, len(non_burned))
            async def picker() -> str | None:  # type: ignore[no-redef]
                return await acquire_tts_key_for_call(pool_keys)
        # max_chunks ist 3 × pool_size, mind. 3 wenn Single-Key
        effective_pool = max(1, pool_size)
        max_chunks = effective_pool * MAX_REQUESTS_PER_KEY_PER_MINUTE

    # `chosen_model` ist bereits oben mit-resolved aus dem KV-Dict (gemeinsam
    # mit Provider + Key), spart einen DB-Roundtrip vs. separate Resolver.

    # Streaming-Response: Input-Chunking läuft parallel über die TTS-API,
    # Audio-Bytes werden in Reihenfolge gestreamt. Format-Details:
    #  - cloud_tts: MP3-Frames (concatenieren natürlich)
    #  - gemini_api: erst WAV-Header (fake-length), dann rohe PCM-Chunks
    async def audio_stream():
        try:
            async for audio_chunk in tts.synthesize_chunked(
                content, chosen_voice, chosen_rate, provider, api_key,
                key_picker=picker,
                max_chunks=max_chunks,
                user_id=user["id"],
                model_id=chosen_model,
                chunking_enabled=chunking_enabled,
            ):
                yield audio_chunk
        except tts.TtsPoolExhaustedError as e:
            # Alle Keys im Pool burned/erschöpft. Stream sauber beenden statt
            # crashen — Client bekommt bereits gestreamte Bytes + EOF.
            log.warning(
                "TTS-Stream beendet: Pool erschöpft (%s). Tipp: morgen wieder "
                "verfügbar (RPD-Reset bei Mitternacht UTC), oder mehr Keys "
                "hinzufügen.", e,
            )
            return
        except tts.TtsCloudTtsUnavailableError as e:
            # Billing disabled / TTS-API nicht aktiviert / Permission denied.
            # Deterministischer Cloud-TTS-Dauerfehler — Stream graceful beenden,
            # gleichzeitig ein paar Minuten cachen, damit nächste App-Requests
            # nicht wieder 25 Chunks parallel feuern bevor's auffällt.
            # Server-weit (nicht per-User), weil Cloud-TTS-Setup global ist.
            global _CLOUD_TTS_UNAVAILABLE_UNTIL
            _CLOUD_TTS_UNAVAILABLE_UNTIL = _time.monotonic() + 300
            log.warning(
                "TTS-Stream beendet: Cloud-TTS nicht nutzbar (%s). Cache 5min, "
                "bitte Cloud-Projekt-Setup prüfen (Billing-Verknüpfung + "
                "benötigte APIs aktiviert).", str(e)[:160],
            )
            return
        except RuntimeError as e:
            log.warning("TTS-Stream RuntimeError (provider=%s): %s", provider, e)
            return  # statt raise: Stream gracefully beenden, sonst crasht ASGI
        except asyncio.CancelledError:
            # Client hat die Verbindung geschlossen → propagieren, damit der
            # asyncio-Task korrekt aufräumt + die in tts.synthesize_chunked
            # registrierten cleanup-Handler greifen.
            raise
        except Exception:
            log.exception("TTS-Stream-Fehler (provider=%s)", provider)
            return

    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        audio_stream(),
        media_type=stream_media_type,
        headers={
            "Cache-Control": "no-store",
            "X-Pocket-Claude-Provider": provider,
            # KEIN Content-Length — wir wissen die Länge erst am Ende.
        },
    )


# ---------- Cloud Billing Status (Spend + Credit) ----------

# Brutto-Preise pro Mio. Zeichen für die Cloud-TTS-Voice-Tiers, Stand 2026-05.
# Quelle: https://cloud.google.com/text-to-speech/pricing
# Werte sind das pure US-$-Listenpreis-Niveau pro 1M Zeichen — die
# Wechselkurs-Anpassung zur Console-EUR-Anzeige rundet Google selbst (wir
# zeigen die Schätzung in der Account-Currency).
_TTS_PRICE_PER_MILLION_CHARS_EUR = {
    "standard": 4.0,    # de-DE-Standard-*
    "wavenet": 4.0,     # de-DE-Wavenet-*  (Quelle 2026-05: $4/M, vorher 16€ war falsch)
    "neural2": 16.0,    # de-DE-Neural2-*
    "studio": 160.0,    # de-DE-Studio-*
    "chirp3hd": 30.0,   # chirp3hd-* (Chirp 3: HD-Voices via Standard-Cloud-TTS-Pfad)
    "gemini": 30.0,     # gemini-* (Routing via Cloud-TTS-Gemini-Modell, Mischpreis)
}
# Free-Tier-Cap pro Monat (Zeichen) — Cloud-TTS billed erst NACH Überschreiten.
# Quelle: https://cloud.google.com/text-to-speech/pricing
_TTS_FREE_CHARS_PER_MONTH = {
    "standard": 4_000_000,
    "wavenet": 4_000_000,    # offiziell 4M, vorher 1M war falsch
    "neural2": 1_000_000,
    "studio": 1_000_000,     # offiziell 1M, vorher 100k war falsch
    "chirp3hd": 1_000_000,   # 1M Zeichen/Monat kostenlos — derselbe Free-Tier wie Studio
    "gemini": 0,             # kein Free-Tier
}


def _estimate_tts_brutto_cost_eur(chars_this_month: int, voice: str | None) -> float:
    """Sehr grobe Brutto-Kostenschätzung für die Cloud-Console-Spend-Anzeige.

    Annahme: alle Zeichen dieses Monats wurden mit der aktuellen `voice`
    synthetisiert (in der Praxis kann das pro Message variieren, aber für
    eine UI-Schätzung reicht's). Free-Tier wird abgezogen.
    """
    if chars_this_month <= 0 or not voice:
        return 0.0
    tier = _voice_tier_for(voice)
    free_chars = _TTS_FREE_CHARS_PER_MONTH.get(tier, 0)
    billable = max(0, chars_this_month - free_chars)
    price_per_million = _TTS_PRICE_PER_MILLION_CHARS_EUR.get(tier, 16.0)
    return billable / 1_000_000.0 * price_per_million


def _voice_tier_for(voice: str) -> str:
    """Heuristik: aus Voice-ID den Preis-Tier ableiten."""
    if voice.startswith("gemini-"):
        return "gemini"
    if voice.startswith("chirp3hd-"):
        return "chirp3hd"
    if "Studio" in voice:
        return "studio"
    if "Neural2" in voice:
        return "neural2"
    if "Wavenet" in voice:
        return "wavenet"
    return "standard"


@app.get("/billing/status", response_model=BillingStatusDto)
async def get_billing_status(user=Depends(require_user)) -> BillingStatusDto:
    """Aktueller Cloud-Billing-Status für die App-Anzeige.

    Liest Brutto-Spend (geschätzt aus dem Cloud-TTS-Counter, da Google's
    Public-Billing-API den Echt-Spend nicht liefert) + Budget + Credit.
    Cached intern für 5 Minuten."""
    from datetime import datetime, timezone as _tz
    payload = await billing.fetch_billing_status()

    # Wenn nicht verfügbar — direkt zurück, App zeigt „nicht verbunden".
    if not payload.get("available"):
        return BillingStatusDto(
            available=False,
            error=payload.get("error"),
            billing_account_id=payload.get("billing_account_id"),
            project_id=payload.get("project_id"),
            last_updated_at=datetime.now(_tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )

    # Spend estimate: monthly Cloud TTS character counter × voice price.
    # Multi-user aware: estimate per user (with that user's own voice tier
    # and its own free-tier allowance) and sum the EUR results — pricing the
    # global char SUM with a single user's voice would be wildly off across
    # mixed tiers.
    from pocket_claude.db import get_db
    spend = 0.0
    try:
        async with get_db() as conn:
            month_key = _current_month_key()
            cur = await conn.execute(
                """
                SELECT c.value AS chars, v.value AS voice
                FROM kv_settings c
                LEFT JOIN kv_settings v
                  ON v.scope = c.scope AND v.key = 'ui_tts_voice'
                WHERE c.key = ?
                """,
                (month_key,),
            )
            rows = await cur.fetchall()
        for row in rows:
            try:
                chars = int(row[0]) if row[0] else 0
            except (TypeError, ValueError):
                chars = 0
            voice = row[1] or tts.DEFAULT_VOICE
            spend += _estimate_tts_brutto_cost_eur(chars, voice)
    except Exception as exc:  # noqa: BLE001
        log.warning("Spend-Schätzung fehlgeschlagen: %s", exc)

    # Verbleibender Credit = max(0, original − spend) (Brutto, nicht Echt-Kosten)
    credit_left = max(0.0, (payload.get("credit_original") or 0.0) - spend)
    estimated_real = max(0.0, spend - (payload.get("credit_original") or 0.0))

    return BillingStatusDto(
        available=True,
        warning=payload.get("warning"),
        billing_account_id=payload.get("billing_account_id"),
        project_id=payload.get("project_id"),
        currency_code=payload.get("currency_code") or "EUR",
        spend_this_month=round(spend, 4),
        budget_amount=payload.get("budget_amount"),
        budget_name=payload.get("budget_name"),
        credit_remaining=round(credit_left, 4),
        credit_original=payload.get("credit_original"),
        credit_name=payload.get("credit_name"),
        estimated_real_cost=round(estimated_real, 4),
        last_updated_at=datetime.now(_tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


# ---------- Image Generation (Google Gemini / Nano Banana) ----------

_KV_IMAGE_API_KEY = "image_api_key"


def _mask_key(k: str) -> str:
    """Maskiert einen API-Key fürs UI: 'AIzaSy…pPWk'."""
    if not k:
        return ""
    if len(k) <= 10:
        return "•" * len(k)
    return f"{k[:6]}…{k[-4:]}"


@app.get("/images/config")
async def images_config(user=Depends(require_user)):
    """Statische Config + ob der aktuelle User einen API-Key hinterlegt hat."""
    cfg = image_engine.get_config()
    kv = await db.kv_get_all(scope=user["id"])
    api_key = (kv.get(_KV_IMAGE_API_KEY) or "").strip()
    cfg["configured"] = bool(api_key)
    cfg["api_key_masked"] = _mask_key(api_key) if api_key else None
    return cfg


@app.put("/images/credentials")
async def images_set_credentials(body: dict, user=Depends(require_user)):
    """Speichert den Gemini-API-Key des Users (per-User, nicht global)."""
    key = (body.get("api_key") or "").strip()
    if not key:
        raise HTTPException(400, "Leerer API-Key.")
    if not key.startswith("AIza"):
        raise HTTPException(400, "Sieht nicht aus wie ein Google-API-Key (sollte mit 'AIza' beginnen).")
    await db.kv_set_many({_KV_IMAGE_API_KEY: key}, scope=user["id"])
    return {"ok": True, "api_key_masked": _mask_key(key)}


@app.delete("/images/credentials", status_code=status.HTTP_204_NO_CONTENT)
async def images_delete_credentials(user=Depends(require_user)):
    # KV-Setting auf leeren String setzen — kein extra delete-Path nötig
    await db.kv_set_many({_KV_IMAGE_API_KEY: ""}, scope=user["id"])
    return JSONResponse(status_code=204, content=None)


# ---------- Voice-Input (Groq Whisper Large v3 Turbo) ----------

_KV_VOICE_GROQ_API_KEY = voice.KV_GROQ_API_KEY


def _voice_status_payload(kv: dict) -> dict:
    """Baut den vollen Voice-Status — Key-Status + Lang-Settings + aktueller
    effektiver Bias-Prompt. Geteilt zwischen GET /voice/config und allen PUT/
    POST-Endpoints, damit der Client immer eine konsistente Snapshot bekommt."""
    api_key = (kv.get(_KV_VOICE_GROQ_API_KEY) or "").strip()
    mode = (kv.get(voice.KV_LANG_MODE) or "auto").strip().lower()
    if mode not in ("auto", "override"):
        mode = "auto"
    override = (kv.get(voice.KV_LANG_OVERRIDE) or "").strip()
    cache = voice.get_prompt_cache(kv)
    # Für die Preview ohne explizite Request-Locale: nehmen wir den Override
    # bzw. „en" als sinnvolle Default-Anzeige.
    preview_lang = voice._to_whisper_code(override or "en")
    prompt_text, prompt_source = voice.resolve_prompt(kv=kv, lang=preview_lang)
    return {
        "configured": bool(api_key),
        "api_key_masked": _mask_key(api_key) if api_key else None,
        "model": voice.GROQ_DEFAULT_MODEL,
        "lang_mode": mode,
        "lang_override": override or None,
        "current_lang": preview_lang,
        "current_prompt": prompt_text,
        "current_prompt_source": prompt_source,
        "bundled_languages": sorted(voice.BUNDLED_PROMPTS.keys()),
        "language_names": voice.LANG_DISPLAY_NAMES,
        "cached_languages": sorted(cache.keys()),
    }


@app.get("/voice/config")
async def voice_config(user=Depends(require_user)):
    """Per-User Voice-Setup: API-Key-Status, Sprach-Override, aktueller
    Bias-Prompt. Wird vom App- + WebUI-Settings-Screen + vom Mic-Button-Check
    benutzt."""
    kv = await db.kv_get_all(scope=user["id"])
    return _voice_status_payload(kv)


@app.put("/voice/credentials")
async def voice_set_credentials(body: dict, user=Depends(require_user)):
    """Speichert den Groq-API-Key des Users (per-User, nicht global).

    Body: `{api_key: str}`. Format-Check: Groq-Keys beginnen mit `gsk_`.
    """
    key = (body.get("api_key") or "").strip()
    if not key:
        raise HTTPException(400, "Leerer API-Key.")
    if not key.startswith("gsk_"):
        raise HTTPException(
            400,
            "Sieht nicht aus wie ein Groq-API-Key (sollte mit 'gsk_' beginnen).")
    await db.kv_set_many({_KV_VOICE_GROQ_API_KEY: key}, scope=user["id"])
    return {"ok": True, "api_key_masked": _mask_key(key)}


@app.delete("/voice/credentials", status_code=status.HTTP_204_NO_CONTENT)
async def voice_delete_credentials(user=Depends(require_user)):
    await db.kv_set_many({_KV_VOICE_GROQ_API_KEY: ""}, scope=user["id"])
    return JSONResponse(status_code=204, content=None)


@app.put("/voice/lang-config")
async def voice_set_lang_config(body: dict, user=Depends(require_user)):
    """Setzt die per-User-Sprache für Voice-Input.

    Body: `{mode: "auto"|"override", locale?: str}`. Bei `auto` folgt
    Whisper der UI-Sprache des Requests; bei `override` wird die angegebene
    Locale verwendet (egal welche Sprache die App grade hat). Locale-Codes
    sind 2-stellig ISO 639-1 (`en`, `de`, `sv`, `ko`, …).
    """
    mode = (body.get("mode") or "").strip().lower()
    if mode not in ("auto", "override"):
        raise HTTPException(400, "mode muss 'auto' oder 'override' sein.")
    locale = (body.get("locale") or "").strip().lower()
    if mode == "override" and not locale:
        raise HTTPException(400, "override braucht eine 'locale'.")
    if locale and not locale.replace("-", "").isalpha():
        raise HTTPException(400, "Ungültiger locale-Code.")
    await db.kv_set_many(
        {
            voice.KV_LANG_MODE: mode,
            voice.KV_LANG_OVERRIDE: locale if mode == "override" else "",
        },
        scope=user["id"],
    )
    kv = await db.kv_get_all(scope=user["id"])
    return _voice_status_payload(kv)


@app.post("/voice/prompt/translate")
async def voice_translate_prompt(body: dict, user=Depends(require_user)):
    """Übersetzt den englischen Default-Bias-Prompt in die angegebene Sprache
    via Anthropic Claude (oneshot, kein Conversation-State).

    Body: `{locale: str, force?: bool}`. `force=true` ignoriert den Cache
    und triggert eine frische Übersetzung. Das Ergebnis landet im Cache
    (KV `voice_prompt_cache`) und kann sofort von /voice/transcribe genutzt
    werden.
    """
    locale = (body.get("locale") or "").strip().lower()
    force = bool(body.get("force"))
    if not locale:
        raise HTTPException(400, "Locale fehlt.")
    if not locale.replace("-", "").isalpha():
        raise HTTPException(400, "Ungültiger locale-Code.")
    lang = voice._to_whisper_code(locale)

    kv = await db.kv_get_all(scope=user["id"])
    if not force:
        cache = voice.get_prompt_cache(kv)
        if lang in cache and cache[lang].strip():
            return {
                "locale": lang,
                "prompt": cache[lang],
                "source": "cache",
            }

    # Bundled? Dann bleibt der Default — kein Claude-Roundtrip nötig.
    if lang in voice.BUNDLED_PROMPTS and not force:
        return {
            "locale": lang,
            "prompt": voice.BUNDLED_PROMPTS[lang],
            "source": "bundled",
        }

    try:
        translated = await voice.translate_bias_prompt(
            target_lang=lang,
            user_id=user["id"],
        )
    except Exception as e:  # noqa: BLE001 — Claude-Fehler werden direkt durchgereicht
        log.warning("Voice-Prompt-Translate user=%s lang=%s failed: %s",
                    user["id"], lang, e)
        raise HTTPException(
            502, f"Übersetzung fehlgeschlagen: {e}"
        ) from e

    # In den per-User-Cache schreiben (merge, nicht überschreiben)
    cache = voice.get_prompt_cache(kv)
    cache[lang] = translated
    import json as _json
    await db.kv_set_many(
        {voice.KV_PROMPT_CACHE: _json.dumps(cache, ensure_ascii=False)},
        scope=user["id"],
    )
    log.info("Voice-Prompt für user=%s lang=%s frisch übersetzt (%d chars)",
             user["id"], lang, len(translated))
    return {
        "locale": lang,
        "prompt": translated,
        "source": "translated",
    }


@app.delete("/voice/prompt/cache/{locale}",
            status_code=status.HTTP_204_NO_CONTENT)
async def voice_delete_cached_prompt(locale: str, user=Depends(require_user)):
    """Löscht einen einzelnen Cache-Eintrag — danach greift wieder der
    Bundled-Default (oder eine frische Übersetzung beim nächsten Translate-
    Call)."""
    kv = await db.kv_get_all(scope=user["id"])
    cache = voice.get_prompt_cache(kv)
    lang = voice._to_whisper_code(locale)
    if lang in cache:
        cache.pop(lang)
        import json as _json
        await db.kv_set_many(
            {voice.KV_PROMPT_CACHE: _json.dumps(cache, ensure_ascii=False)
                                    if cache else ""},
            scope=user["id"],
        )
    return JSONResponse(status_code=204, content=None)


@app.post("/voice/transcribe")
async def voice_transcribe_endpoint(
    file: UploadFile = File(...),
    language: str = Form(default="en"),
    user=Depends(require_user),
):
    """Audio → Transkript via Groq Whisper Large v3 Turbo.

    `language`: UI-Locale aus dem Client (`en`, `de`, `pt-BR`, …). Server
    resolved daraus + dem User-Setting (auto vs. override) die effektive
    Whisper-Sprache + den passenden Bias-Prompt (bundled oder aus dem
    Translation-Cache).
    """
    kv = await db.kv_get_all(scope=user["id"])
    api_key = (kv.get(_KV_VOICE_GROQ_API_KEY) or "").strip()
    if not api_key:
        raise HTTPException(
            400,
            "Kein Groq-API-Key gesetzt. In den Einstellungen unter "
            "'Spracheingabe' eintragen.")

    raw = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(raw) > max_bytes:
        raise HTTPException(
            413,
            f"Audio zu groß (max {settings.max_upload_mb} MB).")
    if not raw:
        raise HTTPException(400, "Audio-Daten leer.")

    effective_lang = voice.resolve_effective_lang(
        kv=kv, request_locale=language,
    )
    bias_prompt, _src = voice.resolve_prompt(kv=kv, lang=effective_lang)

    try:
        text = await voice.transcribe(
            audio_bytes=raw,
            filename=file.filename or "audio.m4a",
            content_type=file.content_type or "audio/mp4",
            api_key=api_key,
            whisper_lang=effective_lang,
            bias_prompt=bias_prompt,
        )
    except voice.VoiceTranscribeError as e:
        log.warning("Voice-Transcribe für user=%s fehlgeschlagen: %s",
                    user["id"], e)
        raise HTTPException(400, str(e)) from e

    log.info("Voice-Transcribe ok user=%s req-lang=%s effective=%s chars=%d",
             user["id"], language, effective_lang, len(text))
    return {"text": text}


@app.post("/images/generate")
async def images_generate(body: dict, user=Depends(require_user)):
    """Generiert ein Bild (oder mehrere Varianten) und speichert die Outputs
    als Attachments. Returnt die neuen Attachment-IDs + Metadaten.

    Body:
      prompt:        str (required)
      conversation_id: str (optional — wenn gesetzt, wird die Generation als
                       Assistant-Message im Chat-Stream gespeichert)
      model:         str (optional, default = neuestes Nano-Banana)
      aspect_ratio:  str (optional, '1:1' | '16:9' | '9:16' | '4:3' | '3:4')
      count:         int (optional, default 1, max 4)
      reference_attachment_ids: list[str] (optional, für Image-Editing)
    """
    if not isinstance(body, dict):
        raise HTTPException(400, "JSON-Objekt erwartet.")
    prompt = (body.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(400, "prompt fehlt.")

    # API-Key des Users laden
    kv = await db.kv_get_all(scope=user["id"])
    api_key = (kv.get(_KV_IMAGE_API_KEY) or "").strip()
    if not api_key:
        raise HTTPException(
            400,
            "Kein Gemini-API-Key gesetzt. Bitte in den Einstellungen unter "
            "'Bilder' eintragen.",
        )

    # Referenz-Bilder laden (für Image-Editing) — read_bytes in to_thread,
    # damit ein 10-MB-Bild nicht den Event-Loop blockiert.
    import asyncio as _asyncio_for_imgs
    ref_ids = body.get("reference_attachment_ids") or []
    references: list[image_engine.ReferenceImage] = []
    for aid in ref_ids:
        att = await db.get_attachment(aid, user_id=user["id"])
        if not att:
            raise HTTPException(400, f"Referenz-Attachment {aid} nicht gefunden / nicht Deins.")
        try:
            from pathlib import Path as _P
            raw = await _asyncio_for_imgs.to_thread(_P(att["path"]).read_bytes)
            references.append(image_engine.ReferenceImage(
                mime_type=att["mime_type"],
                data=raw,
            ))
        except OSError:
            raise HTTPException(500, f"Referenz-Datei {aid} konnte nicht gelesen werden.")

    # Generieren — `count` defensiv parsen, sonst crasht der Endpoint mit
    # 500 wenn der Client versehentlich `count="2"` als String schickt (gültig
    # in JSON, aber die Pydantic-Loose-Validation greift hier nicht weil body=dict).
    try:
        raw_count = body.get("count")
        count_val = int(raw_count) if raw_count not in (None, "") else 1
    except (TypeError, ValueError):
        raise HTTPException(400, f"Invalid count value: {raw_count!r}")
    try:
        images = await image_engine.generate(
            api_key=api_key,
            prompt=prompt,
            model=body.get("model"),
            aspect_ratio=body.get("aspect_ratio"),
            count=count_val,
            references=references or None,
        )
    except image_engine.ImageGenError as e:
        raise HTTPException(502, str(e))

    # Outputs als Attachments speichern — write_bytes in to_thread, da Bilder
    # bis zu mehrere MB groß sein können.
    import secrets as _secrets
    out_atts: list[dict] = []
    for img in images:
        ext = "png" if "png" in img.mime_type else (img.mime_type.split("/")[-1] or "bin")
        disk_name = f"img_{_secrets.token_urlsafe(10)}.{ext}"
        target = settings.uploads_dir / disk_name
        await _asyncio_for_imgs.to_thread(target.write_bytes, img.data)
        aid = await db.add_attachment(
            filename=f"gemini-image-{img.index + 1}.{ext}",
            mime_type=img.mime_type,
            size_bytes=len(img.data),
            path=target,
            user_id=user["id"],
        )
        out_atts.append({
            "id": aid,
            "filename": f"gemini-image-{img.index + 1}.{ext}",
            "mime_type": img.mime_type,
            "size_bytes": len(img.data),
            "text": img.text,
        })

    # Optional: Als Assistant-Message in eine Konversation einhängen, damit es
    # im Chat-Stream auftaucht.
    cid = (body.get("conversation_id") or "").strip()
    saved_message = None
    if cid:
        conv = await db.get_conversation(cid, user_id=user["id"])
        if not conv:
            raise HTTPException(404, "Konversation nicht gefunden.")
        # User-Prompt als 'user'-Message, dann die Bilder als 'assistant'-Message
        await db.add_message(
            cid, role="user",
            content=_format_image_user_prompt(prompt, body),
            attachment_ids=ref_ids,
            tokens=max(1, len(prompt) // 4),
        )
        assistant_text = _format_image_assistant_text(prompt, body, images)
        msg_id = await db.add_message(
            cid, role="assistant",
            content=assistant_text,
            attachment_ids=[a["id"] for a in out_atts],
            tokens=0,
        )
        await db.auto_rename_if_needed(cid, prompt, user_id=user["id"])
        saved_message = {"id": msg_id, "conversation_id": cid}

    return {
        "ok": True,
        "model": body.get("model") or image_engine.get_config()["default_model"],
        "aspect_ratio": body.get("aspect_ratio") or "1:1",
        "count": len(out_atts),
        "attachments": out_atts,
        "message": saved_message,
    }


def _format_image_user_prompt(prompt: str, body: dict) -> str:
    """Lesbarer Eintrag im Chat-Verlauf für die User-Seite einer Bild-Generation."""
    bits = [f"🎨 **Bild generieren:** {prompt}"]
    if body.get("aspect_ratio"):
        bits.append(f"_Format: {body['aspect_ratio']}_")
    # `count` kann String oder Int sein; defensiv parsen statt int()-crash.
    try:
        c = int(body.get("count") or 1)
    except (TypeError, ValueError):
        c = 1
    if c > 1:
        bits.append(f"_Varianten: {c}_")
    return " · ".join(bits)


def _format_image_assistant_text(prompt: str, body: dict,
                                  images: list[image_engine.GeneratedImage]) -> str:
    """Kurzer Text-Begleiter zur Assistant-Message mit den Bildern."""
    model = body.get("model") or image_engine.get_config()["default_model"]
    extra = next((img.text for img in images if img.text), None)
    parts = [f"_{len(images)}× Bild generiert mit {model}_"]
    if extra:
        parts.append(extra)
    return "\n\n".join(parts)


# ---------- UI-Settings ----------

@app.get("/ui-settings")
async def get_ui_settings(user=Depends(require_user)):
    """UI-Settings pro User — Theme, Effort, TTS-Voice etc."""
    values = await db.kv_get_all(scope=user["id"])
    return {"settings": values}


@app.put("/ui-settings")
async def put_ui_settings(body: dict, user=Depends(require_user)):
    """Merged UI-Settings (partial update). Pro User scoped."""
    if not isinstance(body, dict):
        raise HTTPException(400, "JSON-Objekt erwartet.")
    flat = {str(k): str(v) for k, v in body.items() if v is not None}
    if flat:
        await db.kv_set_many(flat, scope=user["id"])
    return {"ok": True, "count": len(flat)}


# ---------- Skills (per-User-Default + per-Chat-Override) ----------
#
# Welche Tools darf Claude pro Konversation aufrufen? Aktuell drei:
#   - web_search    → "WebSearch"
#   - web_fetch     → "WebFetch"
#   - code_execution → "Bash"
#
# Persistenz:
#   - User-Default: KV-Tabelle (scope=user_id), Key = _KV_SKILLS_DEFAULTS,
#     Wert = JSON-Dump von SkillsDto.
#   - Chat-Override: conversations.skills_override (JSON oder NULL).
#     NULL = User-Default greift.

_KV_SKILLS_DEFAULTS = "skills_defaults"

# Server-weiter Hardcoded-Default (greift, wenn der User noch nichts gesetzt
# hat). Kein per-User-Setup nötig → out-of-the-box funktioniert WebSearch.
_SERVER_DEFAULT_SKILLS = SkillsDto(
    web_search=True,
    web_fetch=True,
    code_execution=False,
)


def _skills_to_json(s: SkillsDto) -> str:
    return json.dumps(s.model_dump(), separators=(",", ":"))


def _skills_from_json(raw: str | None) -> SkillsDto | None:
    """Parsed einen JSON-Skills-String. None bei NULL/leer/kaputt."""
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        return SkillsDto(**data)
    except (json.JSONDecodeError, TypeError, ValueError):
        log.warning("Skills-JSON nicht parsebar: %r", raw[:200])
        return None


async def _resolve_user_default_skills(user_id: str) -> SkillsDto:
    """User-Default-Skills lesen (Fallback: Server-Default)."""
    kv = await db.kv_get_all(scope=user_id)
    return _skills_from_json(kv.get(_KV_SKILLS_DEFAULTS)) or _SERVER_DEFAULT_SKILLS


async def _resolve_effective_skills(
    user_id: str, conv_skills_override: str | None,
) -> tuple[SkillsDto, bool]:
    """Effektive Skills für eine bestimmte Conversation.

    Returnt `(skills, is_override)`. `is_override=True` heißt: der Chat hat
    eine eigene Einstellung, die von User-Default abweicht (oder der User-
    Default existiert nicht und der Chat-Override greift trotzdem).
    """
    override = _skills_from_json(conv_skills_override)
    if override is not None:
        return override, True
    return await _resolve_user_default_skills(user_id), False


@app.get("/skills/defaults", response_model=SkillsDto)
async def get_skills_defaults(user=Depends(require_user)) -> SkillsDto:
    """User-Default-Skills (gelten für alle neuen + nicht-überschriebenen Chats)."""
    return await _resolve_user_default_skills(user["id"])


@app.put("/skills/defaults", response_model=SkillsDto)
async def set_skills_defaults(
    body: SkillsDefaultsRequest, user=Depends(require_user),
) -> SkillsDto:
    await db.kv_set_many(
        {_KV_SKILLS_DEFAULTS: _skills_to_json(body.skills)},
        scope=user["id"],
    )
    return body.skills


@app.get("/conversations/{cid}/skills", response_model=ConversationSkillsResponse)
async def get_conversation_skills(
    cid: str, user=Depends(require_user),
) -> ConversationSkillsResponse:
    conv = await db.get_conversation(cid, user_id=user["id"])
    if not conv:
        raise HTTPException(404, "Konversation nicht gefunden.")
    skills, is_override = await _resolve_effective_skills(
        user["id"], conv.get("skills_override"),
    )
    return ConversationSkillsResponse(skills=skills, is_override=is_override)


@app.put("/conversations/{cid}/skills", response_model=ConversationSkillsResponse)
async def set_conversation_skills(
    cid: str, body: ConversationSkillsRequest, user=Depends(require_user),
) -> ConversationSkillsResponse:
    """Setzt oder löscht (skills=null) den Per-Chat-Override."""
    conv = await db.get_conversation(cid, user_id=user["id"])
    if not conv:
        raise HTTPException(404, "Konversation nicht gefunden.")
    override_json = _skills_to_json(body.skills) if body.skills is not None else None
    ok = await db.set_conversation_skills_override(
        cid, override_json, user_id=user["id"],
    )
    if not ok:
        raise HTTPException(404, "Konversation nicht gefunden.")
    skills, is_override = await _resolve_effective_skills(
        user["id"], override_json,
    )
    return ConversationSkillsResponse(skills=skills, is_override=is_override)


# ---------- /me + User-Verwaltung (Admin) ----------

def _user_public(u: dict) -> dict:
    """Reduziert ein User-Dict auf API-safe Felder (kein password_hash, kein
    bearer)."""
    return {
        "id": u["id"],
        "name": u["name"],
        "is_admin": bool(u.get("is_admin")),
        "must_change_password": bool(u.get("must_change_password")),
        "has_password": bool(u.get("password_hash")),
        "created_at": u.get("created_at"),
    }


@app.get("/me")
async def get_me(user=Depends(require_user)):
    """Aktueller User-Info — App und Web-UI fragen das nach Login, um zu
    wissen, ob Admin-Features sichtbar gemacht werden sollen."""
    return _user_public(user)


# ---------- Auth (Login/Logout/Password) ----------

@app.post("/auth/login")
async def auth_login(body: dict, user_agent: str | None = Header(default=None, alias="User-Agent")):
    """Login mit Username + Passwort. Erstellt eine neue Session und liefert
    `{token, user}` zurück. Bei Migration aus der Token-Only-Zeit akzeptiert
    der `password`-Wert auch das alte Bearer-Token (einmalig, bis ein echtes
    Passwort gesetzt wurde — `must_change_password=true` im Response signalisiert
    das dem Client)."""
    if not isinstance(body, dict):
        raise HTTPException(400, "JSON-Objekt erwartet.")
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    if not username or not password:
        raise HTTPException(400, "Username und Passwort erforderlich.")

    target = await db.get_user_by_name(username)
    if target is None:
        # Generische Fehlermeldung — kein Username-Enumeration-Leak
        raise HTTPException(401, "Username oder Passwort falsch.")

    pw_ok = False
    if target.get("password_hash"):
        # Normaler Pfad: scrypt-Verify (verify_password nutzt intern compare_digest).
        pw_ok = db.verify_password(password, target["password_hash"])
    else:
        # Legacy-User ohne Passwort: das alte API-Token gilt einmalig als „Passwort".
        # Nach Login MUSS er ein echtes Passwort setzen (must_change_password=1 wird
        # gleich gesetzt). compare_digest gegen Timing-Leaks.
        import hmac as _hmac
        legacy_token = target.get("token") or ""
        if legacy_token and _hmac.compare_digest(password, legacy_token):
            pw_ok = True
            # must_change_password=1 setzen, damit der Client den Forced-Change-
            # Dialog zeigt. Wird beim ersten POST /auth/change-password wieder
            # auf 0 gestellt.
            if not target.get("must_change_password"):
                await db.set_must_change_password(target["id"], True)
                target["must_change_password"] = 1

    if not pw_ok:
        raise HTTPException(401, "Username oder Passwort falsch.")

    token = await db.create_session(target["id"], user_agent=user_agent)
    return {
        "token": token,
        "user": _user_public(target),
    }


@app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def auth_logout(user=Depends(require_user)):
    """Beendet die aktuelle Session (nur die, nicht alle Geräte des Users)."""
    bearer = user.get("__bearer__")
    if bearer:
        await db.delete_session(bearer)
    return JSONResponse(status_code=204, content=None)


@app.post("/auth/change-password")
async def auth_change_password(body: dict, user=Depends(require_user)):
    """Passwort ändern. Wenn der User `must_change_password=1` hat (Forced
    Change nach Reset oder Migration), darf das alte Passwort weggelassen
    werden — wir vertrauen der bestehenden Session.

    Body: `{old_password?: str, new_password: str, logout_other_sessions?: bool}`.
    Erfolg: 200 mit `{ok: true}` und der aktuellen Session bleibt gültig;
    andere Sessions werden auf Wunsch invalidiert.
    """
    if not isinstance(body, dict):
        raise HTTPException(400, "JSON-Objekt erwartet.")
    new_pw = body.get("new_password") or ""
    if len(new_pw) < 8:
        raise HTTPException(400, "Passwort muss mind. 8 Zeichen lang sein.")

    must_change = bool(user.get("must_change_password"))
    old_pw = body.get("old_password") or ""

    if not must_change:
        # Normaler Path: altes Passwort muss verifiziert werden
        if not old_pw:
            raise HTTPException(400, "Altes Passwort erforderlich.")
        if not db.verify_password(old_pw, user.get("password_hash")):
            raise HTTPException(401, "Altes Passwort falsch.")
    # else: Forced-Change — kein old_pw nötig, Session reicht als Beweis

    await db.set_user_password(user["id"], new_pw, must_change=False)

    if body.get("logout_other_sessions"):
        bearer = user.get("__bearer__")
        await db.delete_sessions_for_user(user["id"], except_token=bearer)

    return {"ok": True}


@app.get("/auth/sessions")
async def auth_list_sessions(user=Depends(require_user)):
    """Aktive Sessions des aktuellen Users — fürs Settings-„aktive Geräte"-UI."""
    sessions = await db.list_sessions_for_user(user["id"])
    bearer = user.get("__bearer__")
    return {"sessions": [
        {
            "id": s["token"][:12] + "…",  # nicht den vollen Token leaken
            "is_current": s["token"] == bearer,
            "created_at": s["created_at"],
            "last_seen_at": s["last_seen_at"],
            "user_agent": s["user_agent"] or "",
        }
        for s in sessions
    ]}


@app.post("/auth/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def auth_logout_all(user=Depends(require_user)):
    """Aus allen Sessions ausloggen (inkl. der aktuellen)."""
    await db.delete_sessions_for_user(user["id"])
    return JSONResponse(status_code=204, content=None)


# ---------- Claude auth mode (Pro/Max | direct API | Bedrock) ----------

@app.get("/me/claude-auth", response_model=ClaudeAuthDto)
async def get_claude_auth(user=Depends(require_user)):
    """Return the current user's Claude provider config (secrets masked)."""
    kv = await db.kv_get_all(scope=user["id"])
    return ClaudeAuthDto(
        mode=kv.get(auth_modes.KV_MODE) or auth_modes.MODE_PRO_MAX,
        api_key_masked=auth_modes.mask_secret(kv.get(auth_modes.KV_API_KEY)),
        aws_region=kv.get(auth_modes.KV_AWS_REGION) or "",
        aws_access_key_id_masked=auth_modes.mask_secret(kv.get(auth_modes.KV_AWS_ACCESS_KEY_ID)),
        aws_secret_access_key_masked=auth_modes.mask_secret(kv.get(auth_modes.KV_AWS_SECRET_ACCESS_KEY)),
        aws_session_token_masked=auth_modes.mask_secret(kv.get(auth_modes.KV_AWS_SESSION_TOKEN)),
        bedrock_opus_model=kv.get(auth_modes.KV_BEDROCK_OPUS) or auth_modes.DEFAULT_BEDROCK_OPUS,
        bedrock_sonnet_model=kv.get(auth_modes.KV_BEDROCK_SONNET) or auth_modes.DEFAULT_BEDROCK_SONNET,
        bedrock_haiku_model=kv.get(auth_modes.KV_BEDROCK_HAIKU) or auth_modes.DEFAULT_BEDROCK_HAIKU,
        bedrock_model_alias=kv.get(auth_modes.KV_BEDROCK_ALIAS) or auth_modes.DEFAULT_BEDROCK_ALIAS,
        api_key_set=bool(kv.get(auth_modes.KV_API_KEY)),
        aws_access_key_set=bool(kv.get(auth_modes.KV_AWS_ACCESS_KEY_ID)),
        aws_secret_set=bool(kv.get(auth_modes.KV_AWS_SECRET_ACCESS_KEY)),
    )


@app.put("/me/claude-auth", response_model=ClaudeAuthDto)
async def update_claude_auth(body: ClaudeAuthUpdateRequest, user=Depends(require_user)):
    """Partial update. Setting a credential field to empty clears it."""
    updates: dict[str, str] = {}
    mode_changed = False

    if body.mode is not None:
        if body.mode not in auth_modes.VALID_MODES:
            raise HTTPException(
                400,
                f"Invalid mode {body.mode!r}. Allowed: {sorted(auth_modes.VALID_MODES)}",
            )
        # Detect whether this is a real switch — if so, we need to drop the
        # cached CLI session IDs of existing conversations so they don't try
        # to resume a session that belonged to the previous provider.
        prior_mode = await auth_modes.get_mode(user["id"])
        if body.mode != prior_mode:
            mode_changed = True
        updates[auth_modes.KV_MODE] = body.mode

    if body.bedrock_model_alias is not None:
        v = body.bedrock_model_alias.strip().lower()
        if v and v not in ("opus", "sonnet", "haiku"):
            raise HTTPException(
                400,
                f"Invalid bedrock_model_alias {body.bedrock_model_alias!r}. "
                f"Allowed: opus, sonnet, haiku",
            )

    # Pre-flight: switching to bedrock without AWS credentials is a recipe
    # for opaque downstream errors. Reject it eagerly with a clear message.
    if body.mode == "bedrock":
        kv = await db.kv_get_all(scope=user["id"])
        has_akid = bool(
            (body.aws_access_key_id and body.aws_access_key_id.strip())
            or kv.get(auth_modes.KV_AWS_ACCESS_KEY_ID)
        )
        has_secret = bool(
            (body.aws_secret_access_key and body.aws_secret_access_key.strip())
            or kv.get(auth_modes.KV_AWS_SECRET_ACCESS_KEY)
        )
        if not (has_akid and has_secret):
            raise HTTPException(
                400,
                "Bedrock mode requires AWS credentials. Set aws_access_key_id + "
                "aws_secret_access_key first (or include them in this request).",
            )

    # Map of (incoming-field, kv-key). String fields: empty string clears.
    field_map = (
        ("api_key", auth_modes.KV_API_KEY),
        ("aws_region", auth_modes.KV_AWS_REGION),
        ("aws_access_key_id", auth_modes.KV_AWS_ACCESS_KEY_ID),
        ("aws_secret_access_key", auth_modes.KV_AWS_SECRET_ACCESS_KEY),
        ("aws_session_token", auth_modes.KV_AWS_SESSION_TOKEN),
        ("bedrock_opus_model", auth_modes.KV_BEDROCK_OPUS),
        ("bedrock_sonnet_model", auth_modes.KV_BEDROCK_SONNET),
        ("bedrock_haiku_model", auth_modes.KV_BEDROCK_HAIKU),
        ("bedrock_model_alias", auth_modes.KV_BEDROCK_ALIAS),
    )
    for attr, kv_key in field_map:
        val = getattr(body, attr)
        if val is None:
            continue
        # Empty string = clear. Strip whitespace to avoid leading/trailing
        # spaces on copied credentials.
        val = val.strip()
        # The alias was validated lowercased above; persist it lowercased too,
        # otherwise a stored "Sonnet" misses the lowercase lookup downstream
        # and silently falls back to opus.
        if attr == "bedrock_model_alias":
            val = val.lower()
        updates[kv_key] = val

    if updates:
        await db.kv_set_many(updates, scope=user["id"])

    # When the user actually switches modes, invalidate cached CLI session
    # IDs across their conversations — resuming a previous mode's session
    # will reliably fail and the user would have to send their next message
    # twice. Better to start fresh sessions automatically.
    if mode_changed:
        await db.clear_user_session_ids(user["id"])

    return await get_claude_auth(user=user)


# ---------- Token usage ----------

@app.get("/me/usage", response_model=UsageStatsDto)
async def get_my_usage(period: str = "month", user=Depends(require_user)):
    """Aggregated per-user token usage. `period` = 'month' (default) or 'all'."""
    if period not in ("month", "all"):
        raise HTTPException(400, "period must be 'month' or 'all'")
    stats = await usage.stats_for(user["id"], period=period)
    return UsageStatsDto(**stats)


# ---------- Admin: User-CRUD ----------

@app.get("/users")
async def list_users_endpoint(user=Depends(require_admin)):  # noqa: ARG001
    rows = await db.list_users()
    return {"users": [_user_public(r) for r in rows]}


@app.post("/users")
async def create_user_endpoint(body: dict, user=Depends(require_admin)):  # noqa: ARG001
    """Admin legt neuen User an. Body: `{name, password?, is_admin?}`.

    Wenn `password` weggelassen wird, generiert der Server ein temporäres
    Passwort und gibt es einmalig im Response zurück. Der User MUSS es beim
    ersten Login ändern (`must_change_password=true`).
    """
    name = (body.get("name") or "").strip()
    is_admin = bool(body.get("is_admin"))
    password = body.get("password") or ""
    if not name:
        raise HTTPException(400, "Name erforderlich.")
    if len(name) > 60:
        raise HTTPException(400, "Name zu lang (max 60).")
    # Username muss unique sein (case-insensitive)
    existing = await db.get_user_by_name(name)
    if existing:
        raise HTTPException(409, f"Username '{name}' ist bereits vergeben.")

    initial_temp = False
    if not password:
        password = db.generate_temp_password()
        initial_temp = True
    elif len(password) < 8:
        raise HTTPException(400, "Passwort muss mind. 8 Zeichen lang sein.")

    new_user = await db.create_user(
        name=name, password=password, is_admin=is_admin,
        must_change_password=True,  # bei Admin-Create immer
    )
    out = _user_public(new_user)
    # Klartext-PW einmalig mitgeben, damit Admin es dem User mitteilen kann
    out["initial_password"] = password
    out["initial_password_temp"] = initial_temp
    return out


@app.post("/users/{user_id}/reset-password")
async def reset_user_password_endpoint(user_id: str, body: dict | None = None,
                                       user=Depends(require_admin)):  # noqa: ARG001
    """Admin setzt das Passwort eines Users zurück. Body optional:
    `{password: str}` → exakt dieses Passwort verwenden. Sonst Server-
    generiertes temporäres Passwort. In jedem Fall `must_change_password=1`
    und ALLE aktiven Sessions des Users werden gekickt."""
    target = await db.get_user_by_id(user_id)
    if not target:
        raise HTTPException(404, "User nicht gefunden.")
    body = body or {}
    new_pw = (body.get("password") or "").strip()
    if new_pw and len(new_pw) < 8:
        raise HTTPException(400, "Passwort muss mind. 8 Zeichen lang sein.")
    if not new_pw:
        new_pw = db.generate_temp_password()
    await db.set_user_password(user_id, new_pw, must_change=True)
    await db.delete_sessions_for_user(user_id)
    return {
        "id": user_id,
        "name": target["name"],
        "new_password": new_pw,
        "sessions_revoked": True,
    }


@app.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_endpoint(user_id: str, user=Depends(require_admin)):
    if user_id == user["id"]:
        raise HTTPException(400, "You cannot delete your own account.")
    target = await db.get_user_by_id(user_id)
    if target is None:
        raise HTTPException(404, "User nicht gefunden.")
    if target["is_admin"] and await db.count_admins() <= 1:
        raise HTTPException(400, "Cannot delete the last admin user.")
    await db.delete_user(user_id)
    return JSONResponse(status_code=204, content=None)


# ---------- Settings Export / Import (Per-User) ----------
#
# Exportiert alle User-scoped KV-Werte (TTS-Provider, API-Keys inkl. Pool,
# Image-API-Key, Skills-Defaults, sonstige UI-Settings) als JSON-Payload.
# Bewusst KEIN Profil-Export (Username/Passwort/Token bleiben raus) — das
# Bundle wird IN den Account des aktuellen Users importiert, in dessen
# Namen man eingeloggt ist.
#
# Achtung: Export enthält API-Keys im KLARTEXT. App muss den User warnen
# und sollte die Datei sicher behandeln.

"""
Was wird exportiert?

  • Explizite Felder im DTO (`tts_provider`, `tts_model`, `tts_chunking_enabled`,
    `tts_api_keys`, `image_api_key`, `skills_defaults`) — alles was eindeutig
    typisiert ist und/oder validiert werden muss.
  • Alles andere im KV-Store geht in `extra_kv` — Catch-all. Dazu gehören vor
    allem die Web-UI-Settings (theme, effort, ttsVoice, ttsSpeed, spMode,
    spCustom, sidebar etc.), die das Web-UI ohne Prefix in den KV-Store legt.

Ausgeschlossen werden:
  • Die expliziten Keys oben (sind schon im DTO).
  • Verbrauchs-Counter (`cloud_tts_chars_YYYY-MM`) — gerätelokaler Spend-Track,
    macht nach Migration auf ein anderes Cloud-Projekt eh keinen Sinn.
"""

# Keys, die im DTO ein eigenes Feld haben → NICHT zusätzlich in extra_kv.
_EXPORT_EXPLICIT_KEYS = {
    _KV_TTS_PROVIDER,
    _KV_TTS_MODEL,
    _KV_TTS_CHUNKING_ENABLED,
    _KV_TTS_API_KEY,
    _KV_TTS_API_KEYS,
    _KV_IMAGE_API_KEY_LEGACY_FALLBACK,  # = "image_api_key"
    _KV_SKILLS_DEFAULTS,
}

# Keys, die ausdrücklich NIE exportiert werden (auch nicht in extra_kv).
# Verbrauchs-Counter sind gerätelokal — beim Import auf ein anderes Cloud-
# Projekt sinnlos und kontraproduktiv.
def _is_export_excluded(key: str) -> bool:
    # Monats-Counter wie cloud_tts_chars_2026-05
    if key.startswith("cloud_tts_chars_"):
        return True
    return False


@app.get("/settings/export", response_model=SettingsExportDto)
async def settings_export(user=Depends(require_user)) -> SettingsExportDto:
    """Bündelt alle Server-seitigen Settings des aktuellen Users in ein
    JSON-Payload. Enthält API-Keys im KLARTEXT — Caller (App) muss die
    Datei entsprechend behandeln."""
    user_id = user["id"]
    kv = await db.kv_get_all(scope=user_id)

    # TTS-API-Key-Pool (komplette Liste mit Klartext-Keys, inkl. legacy-Migration)
    pool_entries = await _load_tts_api_keys(user_id)

    skills = _skills_from_json(kv.get(_KV_SKILLS_DEFAULTS))

    # extra_kv: alles aus KV-Store EXCEPT
    #  - die DTO-Explicit-Keys (sind oben im Bundle bereits typisiert)
    #  - die expliziten Excludes (Verbrauchs-Counter etc.)
    # Damit landen auch die Web-UI-Settings ohne ui_-Prefix (theme, effort, …)
    # sauber im Backup — vorher gingen die verloren weil der Prefix-Filter
    # zu eng war.
    extra: dict[str, str] = {}
    for k, v in kv.items():
        if k in _EXPORT_EXPLICIT_KEYS:
            continue
        if _is_export_excluded(k):
            continue
        extra[k] = v

    from datetime import timezone as _tz
    return SettingsExportDto(
        schema_version=1,
        # `datetime.utcnow()` ist deprecated in Py 3.12+ — explizite UTC-Zone.
        # WICHTIG: timezone.utc (Instanz), nicht timezone (Klasse).
        exported_at=datetime.now(_tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        server_version=__version__,
        tts_provider=(kv.get(_KV_TTS_PROVIDER) or None),
        tts_model=(kv.get(_KV_TTS_MODEL) or None),
        tts_chunking_enabled=(kv.get(_KV_TTS_CHUNKING_ENABLED) or None),
        tts_api_keys=pool_entries,
        image_api_key=(kv.get(_KV_IMAGE_API_KEY_LEGACY_FALLBACK) or None),
        skills_defaults=skills,
        extra_kv=extra,
    )


@app.post("/settings/import", response_model=SettingsImportResponse)
async def settings_import(body: SettingsImportRequest,
                          user=Depends(require_user)) -> SettingsImportResponse:
    """Wendet ein zuvor exportiertes Settings-Bundle auf den aktuellen User
    an. None-Felder bleiben unverändert (partial update).

    `tts_api_keys` (wenn gegeben): ERSETZT den bestehenden Pool 1:1.
    """
    user_id = user["id"]
    updates: dict[str, str] = {}

    if body.tts_provider is not None:
        prov = body.tts_provider.strip()
        if prov and prov not in tts.VALID_PROVIDERS:
            raise HTTPException(400, f"Invalid tts_provider: {prov!r}")
        updates[_KV_TTS_PROVIDER] = prov

    if body.tts_model is not None:
        mid = body.tts_model.strip()
        if mid and not tts.is_valid_gemini_model(mid):
            allowed = [m["id"] for m in tts.AVAILABLE_GEMINI_TTS_MODELS]
            raise HTTPException(400, f"Invalid tts_model {mid!r}. Allowed: {allowed}")
        updates[_KV_TTS_MODEL] = mid

    if body.tts_chunking_enabled is not None:
        v = (body.tts_chunking_enabled or "").strip()
        if v not in ("", "0", "1"):
            raise HTTPException(400, f"Invalid tts_chunking_enabled: {v!r} (allowed: '', '0', '1')")
        updates[_KV_TTS_CHUNKING_ENABLED] = v

    if body.image_api_key is not None:
        updates[_KV_IMAGE_API_KEY_LEGACY_FALLBACK] = body.image_api_key.strip()

    if body.skills_defaults is not None:
        updates[_KV_SKILLS_DEFAULTS] = _skills_to_json(body.skills_defaults)

    tts_keys_imported = 0
    if body.tts_api_keys is not None:
        clean: list[dict] = []
        for entry in body.tts_api_keys:
            if not isinstance(entry, dict):
                continue
            k = (entry.get("key") or "").strip()
            if not k:
                continue
            clean.append({
                "id": entry.get("id") or _gen_key_id(),
                "label": (entry.get("label") or "").strip(),
                "key": k,
            })
        await _save_tts_api_keys(user_id, clean)
        tts_keys_imported = len(clean)

    if body.extra_kv:
        for k, v in body.extra_kv.items():
            if k in _EXPORT_EXPLICIT_KEYS:
                continue
            if _is_export_excluded(k):
                continue
            updates[k] = str(v)

    if updates:
        await db.kv_set_many(updates, scope=user_id)

    log.info(
        "Settings-Import von user=%s: %d KV-Updates, %d TTS-Keys",
        user_id, len(updates), tts_keys_imported,
    )
    return SettingsImportResponse(
        ok=True,
        applied_keys=len(updates),
        tts_keys_imported=tts_keys_imported,
    )


# ---------- Backup / Restore ----------

@app.get("/backup")
async def export_backup(password: str | None = None, user=Depends(require_user)):
    """Backup-Export. Admin → global (alle User). Normaler User → nur eigene
    Daten. `?password=` verschlüsselt das ZIP AES-256."""
    scope_user_id = None if user.get("is_admin") else user["id"]
    scope_user_name = None if user.get("is_admin") else user["name"]
    try:
        data = await backup.create_backup_zip(
            password=password or None,
            user_id=scope_user_id,
            user_name=scope_user_name,
        )
    except Exception as e:  # noqa: BLE001
        log.exception("Backup-Export-Fehler")
        raise HTTPException(500, f"Backup-Export-Fehler: {type(e).__name__}: {e}")

    suffix = ".enc.zip" if password else ".zip"
    base = backup.suggested_filename().replace(".zip", suffix)
    # Per-User: User-Name im Filename
    if scope_user_id:
        safe = "".join(c for c in user["name"] if c.isalnum() or c in "-_")[:20]
        base = base.replace("pocket-claude-backup", f"pocket-claude-{safe}")
    from fastapi.responses import Response
    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{base}"',
            "Cache-Control": "no-store",
        },
    )


@app.post("/backup/import")
async def import_backup_endpoint(
    file: UploadFile = File(...),
    mode: str = "replace",
    password: str | None = None,
    user=Depends(require_admin),  # noqa: ARG001 — Import ist Admin-only
):
    """Importiert ein zuvor exportiertes Backup-ZIP. `mode` = "replace" oder
    "merge". Bei verschlüsselten Backups: `?password=...` mitgeben.

    Vor dem Import wird der aktuelle Zustand intern gesichert
    (data/backup-before-import-*.zip), damit Du im Notfall zurück kannst.
    Nach erfolgreichem Replace ist ein Server-Restart sinnvoll.
    """
    if mode not in ("replace", "merge"):
        raise HTTPException(400, f"Unbekannter Modus: {mode}. Erlaubt: replace, merge.")
    data = await file.read()
    if not data:
        raise HTTPException(400, "Leere Datei.")

    try:
        # Import läuft sync; wir lagern es in einen Thread aus.
        import asyncio
        result = await asyncio.to_thread(
            backup.import_backup, data, mode, password or None,
        )
    except backup.BackupPasswordError as e:
        # 423 Locked — vermittelt der App, dass Passwort fehlt/falsch ist
        raise HTTPException(423, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:  # noqa: BLE001
        log.exception("Backup-Import-Fehler")
        raise HTTPException(500, f"Backup-Import-Fehler: {type(e).__name__}: {e}")

    return {
        "ok": True,
        "mode": result.mode,
        "manifest": result.manifest.to_dict(),
        "conversations_added": result.conversations_added,
        "conversations_skipped": result.conversations_skipped,
        "messages_imported": result.messages_imported,
        "attachments_imported": result.attachments_imported,
        "pre_import_backup_path": result.pre_import_backup_path,
        "restart_recommended": result.mode == "replace",
    }


@app.post("/backup/peek")
async def peek_backup(
    file: UploadFile = File(...),
    password: str | None = None,
    user=Depends(require_admin),  # noqa: ARG001 — Peek vor Import = Admin-only
):
    """Liest NUR das Manifest aus dem Upload — für den Confirm-Dialog der App.
    Bei verschlüsselten Backups: `?password=...`. Ohne PW gibt's HTTP 423
    (Locked), darauf reagiert die App mit einem PW-Prompt."""
    data = await file.read()
    if not data:
        raise HTTPException(400, "Leere Datei.")
    try:
        m = backup.peek_manifest(data, password or None)
    except backup.BackupPasswordError as e:
        raise HTTPException(423, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "manifest": m.to_dict()}


# ---------- Default-Errorhandler ----------

@app.exception_handler(Exception)
async def fallback_error(_request, exc: Exception):  # noqa: ANN001
    # Details NUR ins Server-Log — niemals den rohen Exception-Text an den
    # Client geben (kann Pfade/SQL/3rd-Party-URLs mit Credentials enthalten).
    rid = uuid.uuid4().hex
    log.exception("Unbehandelter Server-Fehler [%s]", rid)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": rid},
    )


# ---------- Web-UI ----------
# Statics-Mount MUSS nach allen API-Routes kommen, weil StaticFiles auf "/"
# alles wegschnappt. Auth-Token wird browserseitig im localStorage gehalten,
# nicht über Cookies — die Statics selbst brauchen daher keinen Auth-Check.
from fastapi.staticfiles import StaticFiles
from pathlib import Path as _PathLib

class _HttpOnlyStaticFiles(StaticFiles):
    """Wrap StaticFiles to gracefully reject non-HTTP ASGI scopes.

    The default StaticFiles asserts ``scope["type"] == "http"`` (see
    starlette/staticfiles.py:91), which throws AssertionError into the
    journal every time a service worker or browser-extension speculatively
    opens a WebSocket on our root mount. Reject those with a clean close
    so we don't pollute logs with a stack trace per probe.
    """
    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            # Politely close any non-HTTP attempt (websocket, lifespan, …)
            if scope.get("type") == "websocket":
                await send({"type": "websocket.close", "code": 1008})
            return
        await super().__call__(scope, receive, send)

_webui_dir = _PathLib(__file__).parent / "webui"
if _webui_dir.exists():
    app.mount("/", _HttpOnlyStaticFiles(directory=str(_webui_dir), html=True), name="webui")
    log.info("Web-UI gemountet aus %s", _webui_dir)
else:
    log.warning("webui/-Verzeichnis nicht gefunden — Web-UI nicht aktiv.")
