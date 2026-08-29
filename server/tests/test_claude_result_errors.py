from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import patch

from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

from pocket_claude.claude_engine import (
    _process_error_client_message,
    _result_error_message,
    oneshot_text,
)


def _message(*, status=None, errors=None, subtype="success"):
    return SimpleNamespace(
        api_error_status=status,
        errors=errors,
        subtype=subtype,
    )


class ResultErrorMessageTests(TestCase):
    def test_unauthorized_explains_relogin(self):
        text = _result_error_message(_message(status=401))
        self.assertIn("Anmeldung", text)
        self.assertNotIn("unbekannt", text.lower())

    def test_rate_limit_is_actionable(self):
        text = _result_error_message(_message(status=429))
        self.assertIn("Nutzungslimit", text)

    def test_temporary_api_statuses_keep_status_code(self):
        for status in (500, 502, 503, 529):
            with self.subTest(status=status):
                self.assertIn(str(status), _result_error_message(_message(status=status)))

    def test_other_http_status_is_preserved(self):
        self.assertIn("HTTP 403", _result_error_message(_message(status=403)))

    def test_known_status_wins_over_raw_sdk_error(self):
        text = _result_error_message(
            _message(status=401, errors=["internal request id and provider detail"])
        )
        self.assertIn("Anmeldung", text)
        self.assertNotIn("request id", text)

    def test_raw_sdk_error_is_not_exposed(self):
        text = _result_error_message(
            _message(errors=["internal request id and provider detail"])
        )
        self.assertIn("Providerfehler", text)
        self.assertNotIn("request id", text)

    def test_non_success_subtype_is_not_exposed(self):
        text = _result_error_message(_message(subtype="error_during_execution"))
        self.assertIn("Aufruf ist fehlgeschlagen", text)
        self.assertNotIn("error_during_execution", text)

    def test_success_without_metadata_has_safe_fallback(self):
        text = _result_error_message(_message())
        self.assertIn("ohne weitere Fehlermeldung", text)


class ResultCompletionTests(IsolatedAsyncioTestCase):
    async def test_oneshot_rejects_text_without_result_message(self):
        async def incomplete_query(**_kwargs):
            yield AssistantMessage(
                content=[TextBlock("partial")],
                model="test-model",
            )

        with patch("pocket_claude.claude_engine.query", incomplete_query):
            with self.assertRaisesRegex(RuntimeError, "Abschlussmeldung"):
                await oneshot_text(
                    system_prompt="test",
                    user_message="test",
                    timeout_sec=1,
                )

    async def test_oneshot_accepts_text_with_success_result_message(self):
        async def complete_query(**_kwargs):
            yield AssistantMessage(
                content=[TextBlock("complete")],
                model="test-model",
            )
            yield ResultMessage(
                subtype="success",
                duration_ms=1,
                duration_api_ms=1,
                is_error=False,
                num_turns=1,
                session_id="test-session",
            )

        with patch("pocket_claude.claude_engine.query", complete_query):
            result = await oneshot_text(
                system_prompt="test",
                user_message="test",
                timeout_sec=1,
            )

        self.assertEqual("complete", result)

    async def test_oneshot_hides_unexpected_exception_details(self):
        async def failing_query(**_kwargs):
            raise RuntimeError("secret provider detail")
            yield  # pragma: no cover

        with patch("pocket_claude.claude_engine.query", failing_query):
            with self.assertRaises(RuntimeError) as raised:
                await oneshot_text(
                    system_prompt="test",
                    user_message="test",
                    timeout_sec=1,
                )

        self.assertIn("intern fehlgeschlagen", str(raised.exception))
        self.assertNotIn("secret provider detail", str(raised.exception))


class ProcessErrorMessageTests(TestCase):
    def test_raw_diagnostic_is_never_returned(self):
        text = _process_error_client_message(1, "secret path and provider detail")
        self.assertIn("Fehlercode 1", text)
        self.assertNotIn("secret", text)

    def test_auth_diagnostic_maps_to_safe_message(self):
        text = _process_error_client_message(1, "authentication failed for secret account")
        self.assertIn("Anmeldung", text)
        self.assertNotIn("secret account", text)
