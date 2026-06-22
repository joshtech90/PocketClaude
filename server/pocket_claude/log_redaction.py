"""Query-String-Secret-Redaction für Logs.

Media-Endpoints akzeptieren `?token=…` (ExoPlayer/<img> können keine
Auth-Header senden) und der Backup-Export `?password=…`. Solche Werte dürfen
NICHT im Klartext in Access-/App-Logs landen (Logs, History, Reverse-Proxies).
Dieser Filter maskiert sie in jedem LogRecord — auch im uvicorn-Access-Log.
"""
from __future__ import annotations

import logging
import re

_SECRET_QS_RE = re.compile(
    r"(?i)\b((?:token|password|pwd|api[_-]?key)=)[^&\s\"'<>]+"
)


def _scrub_secret(value):
    return _SECRET_QS_RE.sub(r"\1<redacted>", value) if isinstance(value, str) else value


class _RedactQuerySecretsFilter(logging.Filter):
    """Maskiert token=/password=/api_key=-Werte in Log-Messages + -Args."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        try:
            record.msg = _scrub_secret(record.msg)
            if isinstance(record.args, tuple):
                record.args = tuple(_scrub_secret(a) for a in record.args)
            elif isinstance(record.args, dict):
                record.args = {k: _scrub_secret(v) for k, v in record.args.items()}
        except Exception:  # pragma: no cover — Logging darf nie crashen
            pass
        return True


def install_query_secret_redaction() -> _RedactQuerySecretsFilter:
    """Hängt den Redaction-Filter an Root- + uvicorn-Logger.

    Gibt den Filter zurück (praktisch für Tests / Re-Use).
    """
    redact_filter = _RedactQuerySecretsFilter()
    for handler in logging.getLogger().handlers:
        handler.addFilter(redact_filter)
    # Logger-Level-Filter überleben uvicorns dictConfig (entfernt nur Handler,
    # nicht Filter) und greifen für Records, die direkt an diesen Loggern
    # entstehen.
    for logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logging.getLogger(logger_name).addFilter(redact_filter)
    return redact_filter
