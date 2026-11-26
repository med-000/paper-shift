"""Model catalogs, selection, OAuth renewal, and completed streamed translation."""

from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs

import questionary

from src import auth, cli, inference


def sse(*events: dict) -> io.BytesIO:
    return io.BytesIO("".join(f"data: {json.dumps(event)}\n\n" for event in events).encode())


class InferenceTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)

    def test_chatgpt_catalog_filters_visibility_and_preserves_order(self) -> None:
        catalog = {"models": [
            {"slug": "gpt-test-b", "display_name": "Test B", "visibility": "list"},
            {"slug": "gpt-hidden", "display_name": "Hidden", "visibility": "hide"},
            {"slug": "gpt-test-a", "display_name": "Test A", "visibility": "list"},
        ]}
        with patch("src.inference.urlopen", return_value=io.BytesIO(json.dumps(catalog).encode())) as opened:
            models = inference.list_models("chatgpt", "oauth-test")
        self.assertEqual(models, [("gpt-test-b", "Test B"), ("gpt-test-a", "Test A")])
        self.assertEqual(opened.call_args.args[0].get_header("Authorization"), "Bearer oauth-test")

    def test_api_key_catalog_and_selection_is_tied_to_key(self) -> None:
        catalog = {"data": [{"id": "gpt-a"}, {"id": "gpt-b"}]}
        with (
            patch("src.auth._config_dir", return_value=self.directory),
            patch("src.inference.urlopen", return_value=io.BytesIO(json.dumps(catalog).encode())),
        ):
            self.assertEqual(inference.list_models("api-key", "sk-a"), [("gpt-a", "gpt-a"), ("gpt-b", "gpt-b")])
            inference.select_model("api-key", "sk-a", "gpt-b")
            self.assertEqual(inference.selected_model("api-key", "sk-a"), "gpt-b")
            self.assertIsNone(inference.selected_model("api-key", "sk-b"))
        self.assertNotIn("sk-a", (self.directory / "model.json").read_text())

    def test_translation_requires_completed_event(self) -> None:
        completed = {"type": "response.completed", "response": {"status": "completed"}}
        with patch("src.inference.urlopen", return_value=sse(
            {"type": "response.output_text.delta", "delta": "良い"},
            {"type": "response.output_text.delta", "delta": "結果です。"}, completed,
        )) as opened:
            self.assertEqual(inference.translate("chatgpt", "oauth-test", "gpt-test", "Good results."), "良い結果です。")
        request = opened.call_args.args[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.full_url, inference.RESPONSES_URL)
        self.assertEqual(request.get_header("Authorization"), "Bearer oauth-test")
        body = json.loads(request.data)
        self.assertEqual(body["model"], "gpt-test")
        self.assertEqual(body["input"], [{"role": "user", "content": "Good results."}])
        self.assertIs(body["store"], False)
        self.assertIs(body["stream"], True)

        for events in (
            ({"type": "response.output_text.delta", "delta": "partial"},),
            ({"type": "response.failed", "response": {"error": {"code": "subscription_sharing_usage_limit_exceeded"}}},),
            ({"type": "response.incomplete"},),
        ):
            with patch("src.inference.urlopen", return_value=sse(*events)):
                with self.assertRaises(inference.InferenceError):
                    inference.translate("chatgpt", "oauth-test", "gpt-test", "Good results.")

    def test_http_inference_failure_keeps_code_and_request_id(self) -> None:
        error = HTTPError(
            inference.RESPONSES_URL, 429, "limited", {"x-request-id": "req-test"},
            io.BytesIO(b'{"error":{"code":"subscription_sharing_usage_limit_exceeded"}}'),
        )
        with patch("src.inference.urlopen", side_effect=error):
            with self.assertRaises(inference.InferenceError) as failure:
                inference.translate("chatgpt", "oauth-test", "gpt-test", "Good results.")
        self.assertIn("HTTP 429", str(failure.exception))
        self.assertIn("subscription_sharing_usage_limit_exceeded", str(failure.exception))
        self.assertIn("req-test", str(failure.exception))

    def test_expired_chatgpt_token_refreshes_once_and_rotates_both_tokens(self) -> None:
        saved = {
            "access_token": "expired", "refresh_token": "old-refresh", "client_id": "oaiapp_test",
            "subject": "subject", "scopes": ["chatgpt.tokens.use.direct"], "expires_in": 3600,
            "saved_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        }
        response = {
            "access_token": "new-access", "refresh_token": "new-refresh", "token_type": "Bearer",
            "expires_in": 3600, "scope": "openid offline_access resource.invoke chatgpt.tokens.use.direct",
        }
        auth._save_json(self.directory / "active.json", {"method": "chatgpt"})
        auth._save_json(self.directory / "credentials.json", saved)
        with (
            patch("src.auth._config_dir", return_value=self.directory),
            patch("src.auth.urlopen", return_value=io.BytesIO(json.dumps(response).encode())) as opened,
        ):
            self.assertEqual(auth.active_credential(), ("chatgpt", "new-access"))
            self.assertEqual(auth.active_credential(), ("chatgpt", "new-access"))
        opened.assert_called_once()
        form = parse_qs(opened.call_args.args[0].data.decode())
        self.assertEqual(form["grant_type"], ["refresh_token"])
        self.assertEqual(form["resource"], [auth.RESOURCE])
        self.assertEqual(form["refresh_token"], ["old-refresh"])
        persisted = json.loads((self.directory / "credentials.json").read_text())
        self.assertEqual(persisted["refresh_token"], "new-refresh")

    def test_invalid_grant_requires_relogin_without_switching_to_api_key(self) -> None:
        auth._save_json(self.directory / "active.json", {"method": "chatgpt"})
        auth._save_json(self.directory / "api-key.json", {"api_key": "sk-test"})
        auth._save_json(self.directory / "credentials.json", {
            "client_id": "oaiapp_test", "subject": "subject", "refresh_token": "old-refresh",
            "access_token": "expired", "scopes": ["chatgpt.tokens.use.direct"],
        })
        error = HTTPError(auth.TOKEN_URL, 400, "bad request", {}, io.BytesIO(b'{"error":"invalid_grant"}'))
        with (patch("src.auth._config_dir", return_value=self.directory), patch("src.auth.urlopen", side_effect=error)):
            with self.assertRaisesRegex(auth.LoginError, "pshift login"):
                auth.active_credential()
            with self.assertRaisesRegex(auth.LoginError, "pshift login"):
                auth.active_credential()
        self.assertFalse((self.directory / "credentials.json").exists())
        self.assertEqual(json.loads((self.directory / "registration.json").read_text())["client_id"], "oaiapp_test")

    def test_cli_selects_model_then_translates_with_it(self) -> None:
        output = io.StringIO()
        with (
            patch("src.auth._config_dir", return_value=self.directory),
            patch("src.cli.active_credential", return_value=("api-key", "sk-test")),
            patch("src.cli.list_models", return_value=[("gpt-test", "Test")]),
            patch("src.cli.sys.argv", ["pshift", "model", "gpt-test"]),
            patch("src.cli.sys.stdout", output),
        ):
            cli.main()
        self.assertIn("選択中のモデル: gpt-test", output.getvalue())
        output = io.StringIO()
        with (
            patch("src.auth._config_dir", return_value=self.directory),
            patch("src.cli.active_credential", return_value=("api-key", "sk-test")),
            patch("src.inference.urlopen", return_value=sse(
                {"type": "response.output_text.delta", "delta": "有意でした。"},
                {"type": "response.completed"},
            )) as opened,
            patch("src.cli.sys.argv", ["pshift", "translate", "Significant."]),
            patch("src.cli.sys.stdout", output),
        ):
            cli.main()
        self.assertEqual(output.getvalue().strip(), "有意でした。")
        self.assertEqual(json.loads(opened.call_args.args[0].data)["model"], "gpt-test")

    def test_model_picker_uses_keyboard_choices(self) -> None:
        with (
            patch("src.cli.sys.stdin.isatty", return_value=True),
            patch("src.cli.sys.stdout.isatty", return_value=True),
            patch("src.cli.questionary.select", wraps=questionary.select) as picker,
            patch("questionary.question.Question.ask", return_value="gpt-test"),
        ):
            self.assertEqual(cli._choose_model([("gpt-test", "Test")], None), "gpt-test")
        self.assertTrue(picker.call_args.kwargs["use_search_filter"])
        self.assertFalse(picker.call_args.kwargs["use_jk_keys"])


if __name__ == "__main__":
    unittest.main()
