"""Google Cloud Billing — Spend + Credit-Abfrage.

Liest den aktuellen Monatsverbrauch des verknüpften Cloud-Projekts und den
Restwert des AI-Pro-Credit. Wird vom `/billing/status`-Endpoint benutzt um in
der App live anzuzeigen wie viel der User schon verbraucht hat und wieviel
Credit noch übrig ist — bevor der Killswitch greift.

Zwei Datenquellen:
1. **Budget-API** (`billingbudgets.googleapis.com`):
   liefert `actualSpend.amount` pro Budget. Wir picken das Budget mit
   `displayName="Pocket-Claude Hard Cap"` (oder das erste, falls's umbenannt
   wurde).
2. **Credits**: Es gibt KEINEN public-API-Endpoint der die monatlichen
   AI-Pro-Credits direkt listet. Wir umgehen das pragmatisch:
   - Wir wissen aus der Console: Credit = 8,56 € pro Monat
     (CREDIT_TYPE_MONTHLY).
   - Restwert = max(0, monatlicher Credit − Spend).
   Wenn Google die Höhe ändert, hardcoded angepassen oder über env-var
   parametrisieren.

Auth: nutzt das gleiche Service-Account-JSON wie Cloud-TTS (das SA muss
zusätzlich die Rolle `Rechnungskontobetrachter` / `roles/billing.viewer` am
Billing-Account haben — siehe Cloud Console → Billing → Kontoverwaltung →
„Prinzipal hinzufügen").

Cache: Cloud-Console-Spend hat ~24h-Lag, ein API-Call pro Sekunde lohnt nicht.
Wir cachen den Status für **5 Minuten** in-process.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

from pocket_claude.config import settings

log = logging.getLogger(__name__)


# --- Configuration ---------------------------------------------------------

# Billing-account ID. Set via the POCKET_CLAUDE_BILLING_ACCOUNT_ID environment
# variable. When unset, billing-status endpoints stay disabled and the app UI
# hides the spend widget — this module is purely opt-in for operators who want
# live Google-Cloud spend visibility in the TTS settings.
import os as _os
BILLING_ACCOUNT_ID = _os.environ.get("POCKET_CLAUDE_BILLING_ACCOUNT_ID", "").strip()

# Monatliches AI-Pro-Credit-Volumen in EUR. Verifiziert in der Cloud Console
# unter Billing → Gutschriften (Stand 2026-05-18). Wenn Google die Höhe
# ändert, hier anpassen — oder dynamisch per Service-Account-API aushandeln,
# was die Public-API derzeit aber nicht erlaubt.
MONTHLY_CREDIT_EUR = 8.56
CREDIT_NAME = "Google Developer Program premium benefit"

# Cache-TTL: 5 Minuten. Cloud-Billing-Daten haben sowieso ~24h-Lag, häufiger
# abfragen bringt nichts und kostet Quota.
CACHE_TTL_SEC = 300.0

# Service-Account-JSON Pfad — gleicher wie für Cloud-TTS.
CREDENTIALS_FILENAME = "google_tts_credentials.json"


@dataclass
class _CacheEntry:
    payload: dict
    expires_at: float


_cache: Optional[_CacheEntry] = None
_cache_lock = asyncio.Lock()


def _credentials_path() -> Path:
    return settings.data_dir / CREDENTIALS_FILENAME


def is_configured() -> bool:
    return bool(BILLING_ACCOUNT_ID) and _credentials_path().exists()


async def _get_access_token() -> str:
    """Holt einen OAuth2-Access-Token via Service-Account-JSON.

    Nutzt `google.oauth2.service_account` (kommt mit `google-cloud-texttospeech`
    sowieso mit). Scopes: `cloud-platform` reicht für Billing-API.
    """
    if not is_configured():
        raise RuntimeError(
            "Cloud-Credentials nicht hinterlegt — kein Service-Account-JSON da."
        )
    # Lazy import damit der Server startet auch wenn google-auth fehlt.
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request as _AuthRequest

    creds = service_account.Credentials.from_service_account_file(
        str(_credentials_path()),
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    # `creds.refresh()` ist sync — in einen Thread auslagern damit der
    # Event-Loop nicht blockiert. Mit Timeout begrenzen (wie die httpx-Calls
    # mit timeout=10.0), sonst kann ein hängender OAuth-Exchange den Request
    # festfrieren.
    try:
        await asyncio.wait_for(
            asyncio.to_thread(creds.refresh, _AuthRequest()), timeout=15.0
        )
    except asyncio.TimeoutError as exc:
        raise RuntimeError(
            "Service-Account-Token-Refresh hat das Timeout überschritten."
        ) from exc
    if not creds.token:
        raise RuntimeError("Kein Access-Token vom Service-Account erhalten.")
    return creds.token


async def _list_budgets(token: str) -> list[dict]:
    """Liest alle Budgets des Billing-Accounts.

    GET https://billingbudgets.googleapis.com/v1/billingAccounts/{id}/budgets
    """
    url = (
        f"https://billingbudgets.googleapis.com/v1/"
        f"billingAccounts/{BILLING_ACCOUNT_ID}/budgets"
    )
    async with httpx.AsyncClient(timeout=10.0) as cli:
        r = await cli.get(url, headers={"Authorization": f"Bearer {token}"})
    if r.status_code != 200:
        raise RuntimeError(
            f"Budget-API HTTP {r.status_code}: {r.text[:240]}"
        )
    data = r.json() or {}
    return data.get("budgets") or []


async def _resolve_billing_project_id(token: str) -> Optional[str]:
    """Sucht das mit dem Billing-Account verknüpfte Projekt (für UI-Anzeige).

    GET billingAccounts/{id}/projects
    Returns the ProjectId of the first linked project, or None if none
    is linked.
    """
    url = (
        f"https://cloudbilling.googleapis.com/v1/"
        f"billingAccounts/{BILLING_ACCOUNT_ID}/projects"
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as cli:
            r = await cli.get(url, headers={"Authorization": f"Bearer {token}"})
        if r.status_code != 200:
            log.warning("Project-Lookup HTTP %d: %s",
                        r.status_code, r.text[:200])
            return None
        data = r.json() or {}
        for proj in data.get("projectBillingInfo") or []:
            if proj.get("billingEnabled"):
                return proj.get("projectId")
        return None
    except Exception as exc:  # noqa: BLE001
        log.warning("Project-Lookup fehlgeschlagen: %s", exc)
        return None


def _extract_budget_data(budget: dict) -> dict:
    """Extrahiert Spend + Budget-Amount aus einem Budget-Objekt.

    Spec: https://cloud.google.com/billing/docs/reference/budget/rest/v1/billingAccounts.budgets
    Felder:
      - displayName
      - amount.specifiedAmount.{currencyCode, units, nanos}
      - spendBasis (nicht direkt; muss aus Cost-Reports kommen)

    Note: the public Budget API does NOT return current spend — only the
    budget setup itself. The Cloud Console reads spend from a separate
    internal RPC. Workaround: we surface only the budget setup and derive
    estimated spend from our own monthly Cloud-TTS character counter
    (`_KV_TTS_CHARS_THIS_MONTH × Studio price`), see `server.py`.

    Für eine echte Spend-Anzeige aus Google-Daten bräuchten wir entweder:
    - BigQuery-Billing-Export einrichten + Query
    - Cloud Monitoring API (`monitoring.timeSeries.list`) auf der Metric
      `billing.googleapis.com/billing/cost` — aber das ist teurer + komplexer.
    """
    name = budget.get("displayName", "")
    amount = budget.get("amount", {}).get("specifiedAmount", {})
    currency = amount.get("currencyCode", "EUR")
    try:
        units = int(amount.get("units") or 0)
        nanos = int(amount.get("nanos") or 0)
    except (TypeError, ValueError):
        units = nanos = 0
    budget_eur = units + nanos / 1e9
    return {
        "displayName": name,
        "currency_code": currency,
        "budget_amount": budget_eur,
    }


async def fetch_billing_status_uncached() -> dict:
    """Ruft Cloud-Billing-Daten frisch ab. Liefert ein dict mit dem Status
    der `BillingStatusDto`-Felder. Bei Fehlern: `{available: False, error: ...}`."""
    if not is_configured():
        return {
            "available": False,
            "error": (
                "Cloud-Credentials fehlen — Service-Account-JSON noch nicht "
                "hochgeladen."
            ),
        }

    try:
        token = await _get_access_token()
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "error": f"Auth: {exc}"}

    # Project lookup + Budget parallel. Beide individuell behandeln —
    # Budget-API ist optional (in vielen Projekten nicht aktiviert), das
    # darf den ganzen Status nicht killen.
    project_id_result, budgets_result = await asyncio.gather(
        _resolve_billing_project_id(token),
        _list_budgets(token),
        return_exceptions=True,
    )

    if isinstance(project_id_result, Exception):
        return {
            "available": False,
            "error": f"Cloud-Billing-API-Fehler: {project_id_result}",
        }
    project_id = project_id_result

    info: dict = {}
    budget_warning: str | None = None
    if isinstance(budgets_result, Exception):
        msg = str(budgets_result)
        if "Cloud Billing Budget API has not been used" in msg or "billingbudgets" in msg:
            budget_warning = (
                "Budget-Anzeige nicht verfügbar (Cloud Billing Budget API noch "
                "nicht aktiviert). Aktiviere sie in der Cloud Console wenn Du "
                "ein Limit + Spend-Warnung in der App sehen willst."
            )
        else:
            budget_warning = f"Budget-API-Fehler: {msg[:160]}"
        log.warning("billing: Budget-API gescheitert (graceful): %s", msg[:200])
    elif not budgets_result:
        budget_warning = (
            "Kein Budget am Billing-Account konfiguriert. Lege eines in der "
            "Cloud Console an, dann erscheint hier die Spend-Info."
        )
    else:
        # Bevorzugt das Budget mit „Pocket-Claude" im Namen. Sonst das erste.
        chosen = next(
            (b for b in budgets_result if "pocket" in (b.get("displayName") or "").lower()),
            budgets_result[0],
        )
        # Budget-Parsing darf den ganzen Status nicht killen (siehe Docstring).
        try:
            info = _extract_budget_data(chosen)
        except Exception as exc:  # noqa: BLE001
            budget_warning = f"Budget-Daten unlesbar: {str(exc)[:160]}"
            log.warning("billing: Budget-Parsing gescheitert (graceful): %s", exc)

    # Spend aus Cloud-Billing-Reports zu holen ist über die Public-API nicht
    # ohne weiteres möglich (nur via BigQuery-Export). Wir zeigen daher den
    # konfigurierten Budget-Wert + Credit-Info und überlassen den App-User
    # dem Vergleich mit der Cloud-Console.
    #
    # WICHTIG: Der App-Client soll das aktuell selbst aus dem Cloud-TTS-Counter
    # `cloud_tts_chars_this_month` x Preis berechnen — siehe das Widget.
    return {
        "available": True,
        "billing_account_id": BILLING_ACCOUNT_ID,
        "project_id": project_id,
        "currency_code": info.get("currency_code") or "EUR",
        # Server-Side haben wir keinen echten Spend — diese 0.0 wird vom
        # Server-Endpoint mit dem User-spezifischen TTS-Counter überschrieben.
        "spend_this_month": 0.0,
        "budget_amount": info.get("budget_amount"),
        "budget_name": info.get("displayName"),
        "credit_remaining": MONTHLY_CREDIT_EUR,
        "credit_original": MONTHLY_CREDIT_EUR,
        "credit_name": CREDIT_NAME,
        "estimated_real_cost": 0.0,
        # Informativer Hinweis falls Budget-API/Setup unvollständig — App
        # zeigt das als kleinen Info-Text statt großem Error-Banner.
        "warning": budget_warning,
    }


async def fetch_billing_status() -> dict:
    """Cached-Variante. TTL 5 min."""
    global _cache
    now = time.monotonic()
    # Lock nur für den In-Memory-Cache-Zugriff halten — NICHT über den
    # Netzwerk-Roundtrip, sonst serialisieren alle /billing/status-Requests
    # hinter einem langsamen Google-Call.
    async with _cache_lock:
        if _cache is not None and now < _cache.expires_at:
            return dict(_cache.payload)  # shallow copy damit Caller nicht mutiert
    payload = await fetch_billing_status_uncached()
    async with _cache_lock:
        _cache = _CacheEntry(payload=payload, expires_at=time.monotonic() + CACHE_TTL_SEC)
    return dict(payload)


def invalidate_cache() -> None:
    """Cache leeren — wird nach Cloud-Credentials-Wechsel aufgerufen damit der
    nächste Request frisch durchgeht."""
    global _cache
    _cache = None
