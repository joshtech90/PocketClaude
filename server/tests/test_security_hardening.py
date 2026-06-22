"""Regression tests for the server security hardening.

Covers three already-applied fixes:
  (a) Settings.cors_origin_list parsing
  (b) placeholder SERVER_TOKEN rejection at construction time
  (c) query-string secret redaction in log records

Notes on imports:
  pocket_claude.config instantiates a module-level `Settings()` singleton at
  import time (requires SERVER_TOKEN, creates DATA_DIR). We therefore set a
  valid SERVER_TOKEN and a temp DATA_DIR in the environment BEFORE importing it,
  so importing the module does not pollute the repo or fail.

  The redaction symbols live in the lightweight pocket_claude.log_redaction
  module (extracted from server.py) so they can be imported without pulling in
  the full FastAPI app and its many dependencies.
"""
from __future__ import annotations

import os
import tempfile

import pytest

# Make config importable cleanly: a valid token + a throwaway data dir.
_TMP_DATA_DIR = tempfile.mkdtemp(prefix="pc-test-data-")
os.environ.setdefault("SERVER_TOKEN", "x" * 40)
os.environ.setdefault("DATA_DIR", _TMP_DATA_DIR)

from pydantic import ValidationError  # noqa: E402

from pocket_claude.config import Settings  # noqa: E402
from pocket_claude.log_redaction import (  # noqa: E402
    _RedactQuerySecretsFilter,
    _scrub_secret,
)

# A real, long, random-looking token that must be accepted.
_REAL_TOKEN = "Zr8kQp2vN6tLwX1aE4yH9cB3dF7gJ0sMuV5nK8qT2wPzR6xY"


def _make_settings(**overrides) -> Settings:
    """Build a Settings with the required fields filled, plus overrides.

    DATA_DIR points at a throwaway temp dir so nothing is written into the repo.
    """
    kwargs = {
        "server_token": _REAL_TOKEN,
        "data_dir": _TMP_DATA_DIR,
    }
    kwargs.update(overrides)
    return Settings(**kwargs)


# --- (a) CORS origin parsing -------------------------------------------------

def test_cors_origin_list_wildcard():
    assert _make_settings(cors_origins="*").cors_origin_list == ["*"]


def test_cors_origin_list_empty_is_wildcard():
    assert _make_settings(cors_origins="").cors_origin_list == ["*"]


def test_cors_origin_list_comma_separated_with_spaces():
    assert _make_settings(cors_origins="a, b").cors_origin_list == ["a", "b"]


def test_cors_origin_list_strips_blanks():
    assert _make_settings(
        cors_origins="https://x.de, ,https://y.de "
    ).cors_origin_list == ["https://x.de", "https://y.de"]


# --- (b) placeholder SERVER_TOKEN rejection ----------------------------------

def test_placeholder_token_rejected():
    with pytest.raises(ValidationError):
        _make_settings(server_token="change-me-to-a-long-random-string")


@pytest.mark.parametrize(
    "bad", ["changeme", "change-me", "secret", "token", "your-token-here"]
)
def test_other_placeholder_tokens_rejected(bad):
    with pytest.raises(ValidationError):
        _make_settings(server_token=bad)


def test_real_token_accepted():
    s = _make_settings(server_token=_REAL_TOKEN)
    assert s.server_token == _REAL_TOKEN


def test_too_short_token_rejected():
    # min_length=8 on the field — a short token must fail too.
    with pytest.raises(ValidationError):
        _make_settings(server_token="abc")


# --- (c) query-string secret redaction ---------------------------------------

@pytest.mark.parametrize("key", ["token", "password", "api_key", "api-key", "pwd"])
def test_scrub_secret_masks_known_keys(key):
    masked = _scrub_secret(f"/media/file?{key}=SUPERSECRET")
    assert "SUPERSECRET" not in masked
    assert f"{key}=<redacted>" in masked


def test_scrub_secret_preserves_other_params():
    masked = _scrub_secret("/m?token=SECRET&foo=bar")
    assert masked == "/m?token=<redacted>&foo=bar"


def test_scrub_secret_case_insensitive_key():
    masked = _scrub_secret("/m?Token=SECRET")
    assert "SECRET" not in masked
    assert "<redacted>" in masked


def test_scrub_secret_non_string_passthrough():
    assert _scrub_secret(123) == 123
    assert _scrub_secret(None) is None


def test_redact_filter_masks_record_msg():
    import logging

    f = _RedactQuerySecretsFilter()
    rec = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg="GET /export?password=hunter2 HTTP/1.1", args=None, exc_info=None,
    )
    assert f.filter(rec) is True
    assert "hunter2" not in rec.getMessage()
    assert "password=<redacted>" in rec.getMessage()


def test_redact_filter_masks_record_args_tuple():
    import logging

    f = _RedactQuerySecretsFilter()
    rec = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg="%s %s", args=("GET", "/m?api_key=SECRET"), exc_info=None,
    )
    assert f.filter(rec) is True
    formatted = rec.getMessage()
    assert "SECRET" not in formatted
    assert "api_key=<redacted>" in formatted
