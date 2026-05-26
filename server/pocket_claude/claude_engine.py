"""Claude-Engine via `claude-agent-sdk` (offizielles Anthropic Python-SDK).

Architektur:
  - Auth: weiterhin über lokale Claude-Code-Anmeldung (`claude login` → OAuth-Token
    in `~/.claude/credentials.json`). Kein API-Key nötig.
  - Unter der Haube spawnt die SDK das gleiche `claude`-Binary, das wir vorher
    direkt aufgerufen haben. Die SDK gibt uns aber zwei wichtige Knöpfe an die
    Hand, die das CLI nicht hatte:
      * `system_prompt="..."` ersetzt den Claude-Code-Default KOMPLETT
        → keine Coding-Agent-Persona mehr, schlanker Prompt-Overhead
      * `setting_sources=[]` lädt keine CLAUDE.md o.ä. mehr
        → kein zusätzlicher Token-Müll aus Projekt-Configs
  - Sessions: weiterhin per `--resume <id>`-Mechanismus (über
    `ClaudeAgentOptions.resume=session_id`).
  - WebSearch standardmäßig erlaubt; Read kommt dazu wenn Anhänge dabei sind.

Anhänge: Text-Dateien werden inline in den Prompt eingebettet (gleiche Logik
wie zuvor). Bilder/PDFs werden via Read-Tool referenziert.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
from pathlib import Path
from typing import AsyncIterator

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    CLINotFoundError,
    ProcessError,
    ResultMessage,
    StreamEvent,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    query,
)

from pocket_claude import auth_modes, db, usage
from pocket_claude.config import settings

log = logging.getLogger(__name__)


# Slim, claude.ai-style system prompt. Fully replaces the Claude Code default
# (saves ~10K tokens per turn). Always respond in the user's language.
#
# IMPORTANT: every prompt must end with the explicit "always respond" clause
# below. The Claude Code CLI has a skip-turn shortcut intended for agentic
# runs that decides to reply with "No response requested." when the user's
# message looks like a bare statement. In a chat app that's a silent
# failure, so we forbid it.
SYSTEM_PROMPT = """You are Pocket Claude — a personal chat assistant the user talks \
to from their phone. Always reply in the same language the user writes in. Be friendly, \
direct, and helpful, like the Claude assistant on claude.ai. Markdown is allowed and \
renders nicely in the app; code blocks with a language hint (```kotlin etc.) are great. \
You have access to the WebSearch tool for current information and to the Read tool when \
the user attaches an image or PDF. No other tools — you are primarily a conversation \
partner, not a coding agent.

Every user message expects a substantive assistant reply — even if the message is a \
statement, observation, or single word rather than an explicit question. Never reply \
with "No response requested.", "(no reply)", or any other skip-turn placeholder. If \
you genuinely have nothing to add, briefly acknowledge and offer one relevant follow-up \
thought."""


# ---------- Text-Anhänge-Inline (unverändert aus dem alten Modul) ----------

MAX_TEXT_ATTACHMENT_BYTES = 200_000

_TEXT_MIME_PREFIXES = ("text/",)
_TEXT_MIME_TYPES = {
    # Universale Daten-/Konfig-Formate
    "application/json", "application/ld+json",
    "application/xml", "application/atom+xml", "application/rss+xml",
    "application/yaml", "application/x-yaml",
    "application/toml",
    "application/x-www-form-urlencoded",
    # Skript-/Source-Sprachen, die manchmal als application/* kommen
    "application/javascript", "application/ecmascript",
    "application/typescript",
    "application/x-shellscript", "application/x-sh",
    "application/x-python", "application/x-python-code",
    "application/x-ruby", "application/x-perl",
    "application/x-php",
    "application/sql",
    # Klassische plain-text Container ohne text/-Prefix
    "application/csv",
    "application/x-tex", "application/x-latex",
    "application/x-makefile",
}
_TEXT_EXTENSIONS = {
    # Klassiker
    ".md", ".markdown", ".txt", ".log", ".rst", ".adoc",
    # Daten
    ".json", ".jsonl", ".ndjson", ".yaml", ".yml", ".xml",
    ".csv", ".tsv", ".tab", ".toml", ".ini", ".cfg", ".conf", ".env",
    ".properties", ".plist", ".lock",
    # Web
    ".html", ".htm", ".css", ".scss", ".sass", ".less",
    ".vue", ".svelte", ".astro",
    # JS-Welt
    ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx",
    # Python-Welt
    ".py", ".pyx", ".pyi", ".ipynb",
    # JVM-Welt
    ".kt", ".kts", ".java", ".scala", ".groovy", ".clj", ".cljc", ".cljs",
    ".gradle",
    # Native + System
    ".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".hxx",
    ".rs", ".go", ".swift", ".m", ".mm",
    ".zig", ".nim", ".v", ".d",
    # Skript-Sprachen
    ".rb", ".pl", ".pm", ".php", ".lua", ".r", ".jl",
    ".sh", ".zsh", ".bash", ".fish", ".ps1", ".bat", ".cmd",
    # Funktional / ML
    ".ex", ".exs", ".erl", ".hrl", ".hs", ".ml", ".mli", ".elm", ".fs", ".fsi",
    # Dart / Flutter / sonstige
    ".dart",
    # DB / Query
    ".sql", ".graphql", ".gql", ".proto",
    # DevOps
    ".tf", ".tfvars", ".hcl", ".nomad", ".nix",
    # Sonstiges Text-Heavy
    ".tex", ".bib", ".diff", ".patch", ".srt", ".vtt",
}

# Files OHNE Punkt-Extension, die per Konvention reiner Text sind.
_TEXT_FILENAMES = {
    "dockerfile", "containerfile",
    "makefile", "gnumakefile",
    "rakefile", "gemfile", "procfile", "vagrantfile",
    "license", "licence", "copying", "readme", "changelog", "authors",
    "todo", "notes",
    ".gitignore", ".gitattributes", ".dockerignore", ".editorconfig",
    ".prettierrc", ".eslintrc", ".babelrc",
}


def _looks_like_text(filename: str, mime: str) -> bool:
    """Heuristik: gehört der Anhang inline in den Prompt-Text, oder soll er
    nur per Read-Tool referenziert werden?

    Reihenfolge:
      1. MIME-Prefix text/* → ja
      2. MIME aus expliziter Allowlist → ja
      3. Filename-Extension in der Allowlist → ja
      4. Filename selbst (ohne Punkt) in der Konventions-Liste → ja
      5. sonst nein (= Binär, per Read-Tool)
    """
    if any(mime.startswith(p) for p in _TEXT_MIME_PREFIXES):
        return True
    if mime in _TEXT_MIME_TYPES:
        return True
    lower = filename.lower()
    if any(lower.endswith(ext) for ext in _TEXT_EXTENSIONS):
        return True
    # Punkt-loser Filename (z.B. „Dockerfile", „Makefile") → letztes Path-Segment
    base = lower.rsplit("/", 1)[-1]
    if base in _TEXT_FILENAMES:
        return True
    return False


def _build_prompt_text(user_msg: dict, attachments_by_id: dict[str, dict]) -> str:
    content = user_msg["content"] or ""
    attach_ids = user_msg.get("attachment_ids") or []
    if not attach_ids:
        return content
    parts: list[str] = []
    if content.strip():
        parts.append(content.strip())
    for aid in attach_ids:
        a = attachments_by_id.get(aid)
        if not a:
            parts.append(f"\n\n[Anhang {aid} unauffindbar.]")
            continue
        filename = a["filename"]
        mime = a["mime_type"] or "application/octet-stream"
        path = Path(a["path"])
        if not path.exists():
            parts.append(f"\n\n[Anhang '{filename}' fehlt auf dem Server.]")
            continue
        if _looks_like_text(filename, mime):
            try:
                raw = path.read_bytes()
                truncated = False
                if len(raw) > MAX_TEXT_ATTACHMENT_BYTES:
                    raw = raw[:MAX_TEXT_ATTACHMENT_BYTES]
                    truncated = True
                text = raw.decode("utf-8", errors="replace")
                fence = "```"
                if fence in text:
                    fence = "````"
                trunc_note = "\n\n…[gekürzt]" if truncated else ""
                parts.append(
                    f"\n\n--- Anhang: **{filename}** "
                    f"({mime}, {a['size_bytes']} Bytes) ---\n"
                    f"{fence}\n{text}{trunc_note}\n{fence}\n--- Ende Anhang ---"
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("Anhang %s nicht als Text lesbar: %s", filename, exc)
                parts.append(f"\n\n[Anhang '{filename}' konnte nicht gelesen werden: {exc}]")
        else:
            abs_path = path.resolve()
            parts.append(
                f"\n\n--- Anhang: **{filename}** ({mime}, {a['size_bytes']} Bytes) ---\n"
                f"Bitte lies die Datei mit dem `Read`-Tool — absoluter Pfad:\n"
                f"`{abs_path}`\n"
                f"--- Ende Anhang ---"
            )
    return "".join(parts)


def _has_binary_attachments(
    attach_ids: list[str], attachments_by_id: dict[str, dict]
) -> bool:
    for aid in attach_ids:
        a = attachments_by_id.get(aid)
        if not a:
            continue
        if not _looks_like_text(a["filename"], a["mime_type"]):
            return True
    return False


# ---------- One-shot non-streaming Claude call ----------

async def oneshot_text(
    *,
    system_prompt: str,
    user_message: str,
    user_id: str | None = None,
    timeout_sec: float = 30.0,
    allowed_tools: list[str] | None = None,
) -> str:
    """Schickt EINEN Prompt an Claude, sammelt den vollen Antwort-Text und gibt
    ihn zurück. Keine Session, keine Tools (per default), kein Streaming-State.

    Nutzt den User-Auth-Kontext (Pro/Max OAuth, API-Key oder Bedrock) wenn
    `user_id` gesetzt ist; sonst läuft's gegen die Operator-Session (`claude
    login` auf dem Server). Geeignet für kurze interne Tasks wie
    Prompt-Übersetzungen, wo wir kein Conversation-State brauchen.

    Wirft `RuntimeError` bei Timeout / SDK-Fehler / leerer Antwort, damit
    der Caller das in eine sprechende UI-Meldung wickeln kann.
    """
    # Auth-Env (Bedrock-Override, API-Key-Mode etc.) wie im stream_reply
    engine_env: dict[str, str] = {}
    model_override: str | None = None
    if user_id is not None:
        provider_env, model_override = await auth_modes.build_provider_env(user_id)
        if provider_env:
            engine_env.update(provider_env)

    effective_model = model_override or (settings.claude_model or None)
    sandbox_cwd = settings.data_dir / "claude-sandbox"
    sandbox_cwd.mkdir(parents=True, exist_ok=True)

    options_kwargs: dict = dict(
        system_prompt=system_prompt,
        allowed_tools=allowed_tools or [],
        permission_mode="bypassPermissions",
        cwd=str(sandbox_cwd),
        include_partial_messages=False,
        model=effective_model,
        setting_sources=[],
        env=engine_env,
    )
    resolved_cli = settings.claude_binary or shutil.which("claude")
    if resolved_cli:
        options_kwargs["cli_path"] = resolved_cli
    options = ClaudeAgentOptions(**options_kwargs)

    text_parts: list[str] = []

    async def _run() -> None:
        async for message in query(prompt=user_message, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock) and block.text:
                        text_parts.append(block.text)
            # SystemMessage / ResultMessage / StreamEvent → ignoriert

    try:
        await asyncio.wait_for(_run(), timeout=timeout_sec)
    except asyncio.TimeoutError as e:
        raise RuntimeError(
            f"Claude antwortete nicht innerhalb von {int(timeout_sec)}s."
        ) from e
    except CLINotFoundError as e:
        raise RuntimeError(f"Claude-CLI nicht gefunden: {e}") from e
    except ProcessError as e:
        raise RuntimeError(f"Claude-Subprozess-Fehler: {e}") from e
    except Exception as e:  # noqa: BLE001 — alle anderen Fehler weiterreichen
        raise RuntimeError(f"Claude-Aufruf fehlgeschlagen: {e}") from e

    out = "".join(text_parts).strip()
    if not out:
        raise RuntimeError("Claude lieferte einen leeren Text-Output.")
    return out


# ---------- Streaming via claude-agent-sdk ----------

async def stream_reply(
    cid: str,
    user_message_id: int,
    effort: str = "high",
    system_prompt: str | None = None,
    skills: dict | None = None,
    user_id: int | None = None,
) -> AsyncIterator[dict]:
    """Yieldet SSE-kompatible Events:
      - {"type": "delta", "text": "..."}
      - {"type": "done", "assistant_message_id": int, "tokens_in": int,
         "tokens_out": int, "tokens_cached_read": int, "tokens_cached_write": int}
      - {"type": "error", "message": str}

    `user_id` enables per-user auth-mode resolution (Pro/Max OAuth vs.
    direct API key vs. AWS Bedrock). When None, falls back to the operator's
    `claude login` session (Pro/Max).
    """
    # Defensiv vor-initialisieren — falls eine frühe Exception (DB-Lookup-
    # Fehler etc.) in den `except ProcessError`-Branch fällt, wo wir
    # `session_id` lesen, hätten wir sonst einen NameError.
    session_id: str | None = None
    log.info("PC_SSE: stream_reply START cid=%s user_msg_id=%s effort=%s user_id=%s",
             cid, user_message_id, effort, user_id)
    try:
        conv = await db.get_conversation(cid)
        if not conv:
            yield {"type": "error", "message": "Konversation nicht gefunden."}
            return

        all_msgs = await db.list_messages(cid)
        user_msg = next((m for m in all_msgs if m["id"] == user_message_id), None)
        if not user_msg:
            yield {"type": "error", "message": "User-Message in DB nicht gefunden."}
            return

        # Anhänge laden für Inline-Einbettung
        attach_ids = user_msg.get("attachment_ids") or []
        attachments = await db.get_attachments(attach_ids) if attach_ids else []
        attachments_by_id = {a["id"]: a for a in attachments}

        prompt = _build_prompt_text(user_msg, attachments_by_id)
        need_read_tool = _has_binary_attachments(attach_ids, attachments_by_id)
        session_id = conv.get("claude_session_id")

        # Skills → allowed_tools.
        # Caller (server.py /messages-Endpoint) reicht ein dict mit den
        # SkillsDto-Feldern durch. Fehlende oder None → Server-Defaults
        # (WebSearch/WebFetch on, Bash off).
        sk = skills or {}
        allowed_tools: list[str] = []
        if sk.get("web_search", True):
            allowed_tools.append("WebSearch")
        if sk.get("web_fetch", True):
            allowed_tools.append("WebFetch")
        if sk.get("code_execution", False):
            # Server-side veto: even if the client requested Bash, drop it
            # unless the operator explicitly opted in via ALLOW_BASH=1 in
            # .env. Without this, any app user could run arbitrary commands
            # as the pocket-claude system user.
            if settings.allow_bash:
                allowed_tools.append("Bash")
            else:
                log.warning(
                    "Bash requested by client but blocked by server policy "
                    "(ALLOW_BASH=false). Set ALLOW_BASH=1 in .env to enable."
                )
        if need_read_tool:
            allowed_tools.append("Read")
        log.info("Skills enabled → allowed_tools: %s", allowed_tools)

        # Sandbox cwd so Claude Code (even if setting_sources had leaks)
        # doesn't pick up any project CLAUDE.md. We place it under the
        # data directory because systemd's PrivateTmp=true would otherwise
        # hide it from the subprocess — the data dir is explicitly granted
        # ReadWritePaths in the service unit.
        sandbox_cwd = settings.data_dir / "claude-sandbox"
        sandbox_cwd.mkdir(parents=True, exist_ok=True)

        # Effort-Level für Thinking via Env-Var an den Subprocess weitergeben.
        # Issue #7840: im headless Mode wird Thinking trotz aller Flags nicht
        # im Stream angezeigt — aber das Modell denkt. Effort steuert die Tiefe.
        # SDK-Werte: low, medium, high, xhigh, max. "off" → wir setzen die Var
        # nicht (CLI-Default greift). `xhigh` ist Opus-4.7-only, fällt auf
        # anderen Modellen auf `high` zurück; wir laufen auf Opus 4.7, also
        # ist es bei uns ein echtes Extra-Level.
        valid_efforts = {"low", "medium", "high", "xhigh", "max"}
        eff = (effort or "").lower().strip()
        engine_env: dict = {}
        if eff in valid_efforts:
            engine_env["CLAUDE_CODE_EFFORT_LEVEL"] = eff
            log.info("CLAUDE_CODE_EFFORT_LEVEL=%s", eff)
        elif eff and eff != "off":
            log.warning("Unbekanntes effort=%r, ignoriert", effort)

        # Multi-provider auth: load the user's configured auth mode and inject
        # the right env vars (ANTHROPIC_API_KEY for direct-API mode, or
        # CLAUDE_CODE_USE_BEDROCK=1 + AWS creds for Bedrock). Pro/Max OAuth is
        # the default and needs no extra env.
        model_override: str | None = None
        if user_id is not None:
            provider_env, model_override = await auth_modes.build_provider_env(user_id)
            if provider_env:
                engine_env.update(provider_env)
                mode = await auth_modes.get_mode(user_id)
                log.info("Auth-mode=%s, %d env override(s)", mode, len(provider_env))

        # System-Prompt: kommt von der App; Fallback ist unser kurzer Default.
        sp = (system_prompt or "").strip() or SYSTEM_PROMPT
        log.info(
            "SystemPrompt: %s (%d chars)",
            "App-supplied" if (system_prompt or "").strip() else "Server-Default",
            len(sp),
        )

        # For Bedrock mode the user pinned a specific Bedrock model ID
        # (`us.anthropic.claude-opus-4-7` etc.) — pass it as the explicit
        # model. Otherwise stick with the server-default (`claude-opus-4-7[1m]`
        # for Pro/Max + API-key modes, which both speak the same model namespace).
        effective_model = model_override or (settings.claude_model or None)

        # Permission mode: bypassPermissions skips per-tool prompts, which is
        # what we want for the read-only tools (WebSearch / WebFetch / Read).
        # The only way "destructive" tools reach this point is if the operator
        # set ALLOW_BASH=1 AND the user opted in per-chat — at that point the
        # operator has accepted the risk explicitly, so we still bypass to
        # avoid hanging on prompts the headless mode can't answer.
        options_kwargs: dict = dict(
            system_prompt=sp,
            allowed_tools=allowed_tools,
            permission_mode="bypassPermissions",
            cwd=str(sandbox_cwd),
            include_partial_messages=True,
            resume=session_id,
            model=effective_model,
            setting_sources=[],
            env=engine_env,
        )
        # cli_path: global installiertes `claude` (Dein Login + Sessions) statt SDK-Bundle
        resolved_cli = settings.claude_binary or shutil.which("claude")
        if resolved_cli:
            options_kwargs["cli_path"] = resolved_cli

        options = ClaudeAgentOptions(**options_kwargs)

        log.info(
            "SDK-query: %s [tools: %s]",
            f"resume {session_id[:8]}…" if session_id else "(neue Session)",
            ", ".join(allowed_tools),
        )

        # Streaming-Loop
        full_text_parts: list[str] = []
        new_session_id: str | None = None
        input_tokens = 0
        output_tokens = 0
        cache_read = 0
        cache_write = 0
        emitted_via_stream = False

        async for message in query(prompt=prompt, options=options):
            # Session-ID aus jedem Event abfischen (Init, Stream, Result haben sie)
            sid = getattr(message, "session_id", None)
            if sid:
                new_session_id = sid

            if isinstance(message, SystemMessage):
                # Init: enthält Modell, Tools, Cwd etc. — wir loggen nur das Modell
                if message.subtype == "init" and isinstance(message.data, dict):
                    mdl = message.data.get("model")
                    if mdl:
                        log.info("Modell: %s", mdl)

            elif isinstance(message, StreamEvent):
                # Token-Deltas — text_delta wird die Antwort, thinking_delta
                # ist die summarized Reasoning-Spur (display="summarized" oben).
                # Beide leiten wir an die App durch; die App entscheidet via
                # Setting, ob das Thinking angezeigt wird.
                ev = message.event or {}
                etype_inner = ev.get("type")
                if etype_inner == "content_block_delta":
                    delta = ev.get("delta") or {}
                    delta_type = delta.get("type")
                    if delta_type == "text_delta":
                        text = delta.get("text", "")
                        if text:
                            full_text_parts.append(text)
                            emitted_via_stream = True
                            yield {"type": "delta", "text": text}
                    elif delta_type == "thinking_delta":
                        thinking_text = delta.get("thinking", "")
                        if thinking_text:
                            log.debug("thinking_delta: %r", thinking_text[:80])
                            yield {"type": "thinking_delta", "text": thinking_text}
                    # signature_delta etc. → ignoriert
                elif etype_inner == "content_block_start":
                    block = ev.get("content_block") or {}
                    btype = block.get("type")
                    log.info("Stream-Block start: type=%s", btype)
                elif etype_inner == "content_block_stop":
                    yield {"type": "block_stop"}

            elif isinstance(message, AssistantMessage):
                # Diagnose: was für Content-Blöcke kommen rein?
                block_types = [type(b).__name__ for b in message.content]
                if block_types:
                    log.info("AssistantMessage block types: %s", block_types)
                # Falls Stream-Events nicht greifen, Volltext nachholen.
                if not emitted_via_stream:
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            text = block.text
                            if text:
                                full_text_parts.append(text)
                                yield {"type": "delta", "text": text}
                        elif isinstance(block, ThinkingBlock):
                            # Falls aus irgendeinem Grund thinking nicht über
                            # Stream-Events kommt, dann mal hier abgreifen:
                            thinking_str = getattr(block, "thinking", "") or ""
                            if thinking_str:
                                log.info("ThinkingBlock im AssistantMessage: %d chars", len(thinking_str))
                                yield {"type": "thinking_delta", "text": thinking_str}
                # Usage-Stats von AssistantMessage auch ablesen (ResultMessage hat sie
                # nochmal, aber je nach SDK-Version kann eines davon None sein)
                _accumulate_usage(message.usage, locals_dict := {})
                input_tokens = locals_dict.get("input_tokens", input_tokens)
                output_tokens = locals_dict.get("output_tokens", output_tokens)
                cache_read = locals_dict.get("cache_read", cache_read)
                cache_write = locals_dict.get("cache_write", cache_write)

            elif isinstance(message, ResultMessage):
                # Final stats — autoritativ wenn vorhanden
                if message.usage:
                    _accumulate_usage(message.usage, locals_dict := {})
                    input_tokens = locals_dict.get("input_tokens", input_tokens)
                    output_tokens = locals_dict.get("output_tokens", output_tokens)
                    cache_read = locals_dict.get("cache_read", cache_read)
                    cache_write = locals_dict.get("cache_write", cache_write)
                if message.is_error:
                    err_msg = (message.errors or ["unbekannter Fehler"])[0]
                    yield {"type": "error", "message": f"Claude: {err_msg}"}
                    return

        full_text = "".join(full_text_parts).strip()

        # Skip-turn guard. Claude Code's headless mode sometimes replies
        # with a short placeholder when it thinks no response is needed
        # (intended for agentic runs, not chat). Detect those and surface
        # an error to the app instead of saving a useless message.
        #
        # Match is intentionally narrow: only exact (case-/punctuation-
        # normalized) matches qualify, no prefix match. A legitimate reply
        # that happens to start with "(skip)" stays valid.
        SKIP_TURN_SENTINELS = {
            "no response requested",
            "(no reply)",
            "(skip)",
            "(no response)",
        }
        normalized = full_text.lower().rstrip(".").strip()
        is_skip_turn = not full_text or normalized in SKIP_TURN_SENTINELS
        if is_skip_turn:
            log.warning(
                "Skip-turn / empty reply detected (text=%r). Surfacing error to client.",
                full_text[:80],
            )
            yield {
                "type": "error",
                "message": (
                    "Claude returned an empty / skip-turn reply. This is a "
                    "Claude Code CLI optimization for agentic runs that "
                    "doesn't fit chat. Try rephrasing your message as a "
                    "question, or re-send to retry."
                ),
            }
            return

        current_context = input_tokens + output_tokens + cache_read + cache_write

        if new_session_id and new_session_id != session_id:
            await db.set_claude_session_id(cid, new_session_id)

        msg_id = await db.add_message(
            cid,
            role="assistant",
            content=full_text,
            tokens=current_context,
        )
        await db.set_total_tokens(cid, current_context)

        # Persist this turn's token usage if we have a user. Pro/Max calls
        # still flow through here so the operator can see the same chart for
        # all three modes — the UI just labels "pro_max" vs "billed" usage.
        if user_id is not None:
            try:
                mode = await auth_modes.get_mode(user_id)
                await usage.record(
                    user_id=user_id,
                    provider=mode,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cache_create=cache_write,
                    cache_read=cache_read,
                )
            except Exception as e:  # noqa: BLE001
                # Usage tracking must never break the user's chat reply.
                log.warning("usage.record failed: %s", e)

        log.info("PC_SSE: stream_reply ABOUT TO YIELD done cid=%s msg_id=%s "
                 "in=%d out=%d cr=%d cw=%d full_text_len=%d",
                 cid, msg_id, input_tokens, output_tokens,
                 cache_read, cache_write, len(full_text))
        yield {
            "type": "done",
            "assistant_message_id": msg_id,
            "tokens_in": input_tokens,
            "tokens_out": output_tokens,
            "tokens_cached_read": cache_read,
            "tokens_cached_write": cache_write,
        }
        log.info("PC_SSE: stream_reply YIELDED done cid=%s msg_id=%s", cid, msg_id)

    except CLINotFoundError as exc:
        log.error("Claude-CLI nicht gefunden: %s (Pfad: %s)", exc, exc.cli_path)
        yield {
            "type": "error",
            "message": (
                "Claude-CLI nicht gefunden. Stelle sicher dass `claude` im PATH liegt "
                "(`which claude`). Ggf. CLAUDE_BINARY in .env auf den Pfad setzen."
            ),
        }
    except ProcessError as exc:
        stderr_excerpt = (exc.stderr or "").strip()[:1200]
        log.error(
            "Claude-Subprocess abgestürzt (exit=%s):\n%s",
            exc.exit_code, stderr_excerpt or "(kein stderr)",
        )

        # Auto-Recovery: Session-ID veraltet (z.B. weil sie mit anderer CLI-Installation
        # angelegt wurde, oder Claude Code hat seinen Session-Storage aufgeräumt).
        # Wir löschen die Session-ID aus der DB und sagen dem User Bescheid.
        combined = stderr_excerpt + " " + str(exc)
        if (
            "no conversation found" in combined.lower()
            or "session id" in combined.lower()
        ) and session_id:
            log.warning(
                "Session %s nicht (mehr) auffindbar — lösche aus DB. "
                "Nächste Nachricht startet eine frische Session.",
                session_id,
            )
            await db.set_claude_session_id(cid, "")
            yield {
                "type": "error",
                "message": (
                    "Die Claude-Session zu diesem Chat ist nicht mehr verfügbar "
                    "(vermutlich von einer anderen CLI-Installation angelegt). "
                    "Schick die Nachricht nochmal — ich starte dann eine neue Session."
                ),
            }
            return

        # Häufige Diagnosen für andere Fehler
        hint = ""
        if "Invalid API key" in stderr_excerpt or "authentication" in stderr_excerpt.lower():
            hint = "  → Auth fehlt. Auf dem Server `claude login` ausführen."
        elif "unknown option" in stderr_excerpt.lower():
            hint = "  → Claude-CLI ist veraltet. `npm install -g @anthropic-ai/claude-code` aktualisieren."
        elif "permission" in stderr_excerpt.lower():
            hint = "  → Permission-Mode-Problem oder Tool-Zugriff verweigert."
        yield {
            "type": "error",
            "message": (
                f"Claude-CLI exit={exc.exit_code}.\n\n"
                f"{stderr_excerpt or '(kein stderr)'}"
                f"{hint}"
            ),
        }
    except Exception as exc:  # noqa: BLE001
        log.exception("SDK-Stream-Fehler in %s", cid)
        yield {"type": "error", "message": f"{type(exc).__name__}: {exc}"}


def _accumulate_usage(usage, out: dict) -> None:
    """Verträgt sowohl dict-Usage als auch typed-Objekt-Usage.

    Wichtig: wir nutzen `value if value is not None else fallback`, NICHT
    `value or fallback` — sonst würde ein legitimer 0-Wert (z.B. cache_write=0
    weil keine neuen Cache-Einträge entstanden sind) auf den Fallback
    zurückgesetzt und vorhandene Counts überschreiben.
    """
    if not usage:
        return

    def _pick(d_val, fallback):
        return d_val if d_val is not None else fallback

    if isinstance(usage, dict):
        out["input_tokens"] = _pick(usage.get("input_tokens"), out.get("input_tokens", 0))
        out["output_tokens"] = _pick(usage.get("output_tokens"), out.get("output_tokens", 0))
        out["cache_read"] = _pick(
            usage.get("cache_read_input_tokens"), out.get("cache_read", 0),
        )
        out["cache_write"] = _pick(
            usage.get("cache_creation_input_tokens"), out.get("cache_write", 0),
        )
    else:
        # Dataclass-Variante (z.B. TaskUsage)
        out["input_tokens"] = _pick(
            getattr(usage, "input_tokens", None), out.get("input_tokens", 0),
        )
        out["output_tokens"] = _pick(
            getattr(usage, "output_tokens", None), out.get("output_tokens", 0),
        )
        out["cache_read"] = _pick(
            getattr(usage, "cache_read_input_tokens", None), out.get("cache_read", 0),
        )
        out["cache_write"] = _pick(
            getattr(usage, "cache_creation_input_tokens", None), out.get("cache_write", 0),
        )
