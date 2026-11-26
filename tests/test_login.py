"""Exercise the local callback and identity checks without a real ChatGPT account."""

import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import urlopen

from cryptography.hazmat.primitives.asymmetric import rsa
import jwt

from src import auth
from src import cli


class LoginTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.urls: list[dict[str, str]] = []

    def _open_browser(self, url: str, *, state_override: str | None = None) -> bool:
        params = {key: value[0] for key, value in parse_qs(urlsplit(url).query).items()}
        self.urls.append(params)

        def callback() -> None:
            query = urlencode({
                "code": "authorization-code",
                "client_id": "oaiapp_test",
                "state": state_override or params["state"],
            })
            with urlopen(f"{params['redirect_uri']}?{query}", timeout=5):
                pass

        thread = threading.Thread(target=callback, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        return True

    def _tokens(self, code: str, client_id: str, verifier: str, redirect_uri: str) -> dict:
        params = self.urls[-1]
        self.assertEqual(code, "authorization-code")
        self.assertEqual(client_id, "oaiapp_test")
        self.assertEqual(redirect_uri, params["redirect_uri"])
        challenge = jwt.utils.base64url_encode(hashlib.sha256(verifier.encode()).digest()).decode()
        self.assertTrue(hmac.compare_digest(challenge, params["code_challenge"]))
        claims = {
            "iss": auth.ISSUER,
            "aud": client_id,
            "sub": "test-subject",
            "email": "user@example.com",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
            "nonce": params["nonce"],
        }
        return {
            "id_token": jwt.encode(claims, self.key, algorithm="RS256"),
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": auth.SCOPES,
        }

    def test_first_and_returning_login(self) -> None:
        jwk = SimpleNamespace(key=self.key.public_key())
        jwks_client = SimpleNamespace(get_signing_key_from_jwt=lambda token: jwk)
        with (
            patch("src.auth._config_dir", return_value=self.directory),
            patch("src.auth.webbrowser.open", side_effect=self._open_browser),
            patch("src.auth._exchange", side_effect=self._tokens),
            patch("src.auth.jwt.PyJWKClient", return_value=jwks_client),
        ):
            self.assertEqual(auth.login(), "user@example.com")
            self.assertEqual(auth.login(), "user@example.com")

        self.assertEqual(self.urls[0]["client_id"], "dynamic_agent_client")
        self.assertEqual(self.urls[0]["agent_name_hint"], "PaperShift")
        self.assertEqual(self.urls[1]["client_id"], "oaiapp_test")
        self.assertNotIn("agent_name_hint", self.urls[1])
        self.assertEqual(self.urls[0]["ext_agent_host_id"], self.urls[1]["ext_agent_host_id"])
        saved = json.loads((self.directory / "credentials.json").read_text())
        self.assertEqual(saved["subject"], "test-subject")
        self.assertEqual(saved["client_id"], "oaiapp_test")
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE((self.directory / "credentials.json").stat().st_mode), 0o600)

    def test_invalid_callback_state_never_exchanges_code(self) -> None:
        with (
            patch("src.auth._config_dir", return_value=self.directory),
            patch("src.auth.webbrowser.open", side_effect=lambda url: self._open_browser(url, state_override="wrong-state")),
            patch("src.auth._exchange") as exchange,
        ):
            with self.assertRaisesRegex(auth.LoginError, "state"):
                auth.login()
        exchange.assert_not_called()
        self.assertFalse((self.directory / "credentials.json").exists())

    def test_login_without_plan_permission_does_not_save_credentials(self) -> None:
        def tokens_without_permission(*args: str) -> dict:
            response = self._tokens(*args)
            response["scope"] = "openid profile email"
            return response

        with (
            patch("src.auth._config_dir", return_value=self.directory),
            patch("src.auth.webbrowser.open", side_effect=self._open_browser),
            patch("src.auth._exchange", side_effect=tokens_without_permission),
        ):
            with self.assertRaisesRegex(auth.LoginError, "権限"):
                auth.login()
        self.assertFalse((self.directory / "credentials.json").exists())

    def test_manual_method_prints_url_and_uses_same_callback(self) -> None:
        jwk = SimpleNamespace(key=self.key.public_key())
        jwks_client = SimpleNamespace(get_signing_key_from_jwt=lambda token: jwk)
        output = io.StringIO()
        opened = False

        def show_url(*args: object, **kwargs: object) -> None:
            nonlocal opened
            output.write(" ".join(str(arg) for arg in args) + "\n")
            if not opened:
                for line in output.getvalue().splitlines():
                    if line.startswith(auth.AUTHORIZE_URL):
                        opened = True
                        self._open_browser(line)
                        break

        with (
            patch("src.auth._config_dir", return_value=self.directory),
            patch("builtins.print", side_effect=show_url),
            patch("src.auth.webbrowser.open") as browser,
            patch("src.auth._exchange", side_effect=self._tokens),
            patch("src.auth.jwt.PyJWKClient", return_value=jwks_client),
        ):
            self.assertEqual(auth.login(method="manual"), "user@example.com")
        browser.assert_not_called()
        self.assertIn("127.0.0.1", output.getvalue())

    def test_interactive_method_selection(self) -> None:
        with (
            patch("src.cli.sys.stdin.isatty", return_value=True),
            patch("src.cli.sys.stdout.isatty", return_value=True),
            patch("src.cli.questionary.select") as select,
        ):
            for method in ("browser", "headless", "api-key"):
                select.return_value.ask.return_value = method
                self.assertEqual(cli._login_method(), method)
            self.assertEqual([choice.value for choice in select.call_args.kwargs["choices"]],
                             ["browser", "headless", "api-key"])
            select.return_value.ask.return_value = None
            with self.assertRaises(KeyboardInterrupt):
                cli._login_method()
        with patch("src.cli.sys.stdin.isatty", return_value=False):
            self.assertEqual(cli._login_method(), "browser")

    def test_status_shows_active_account_and_api_key_but_not_oauth_tokens(self) -> None:
        with patch("src.auth._config_dir", return_value=self.directory):
            self.assertEqual(auth.status_lines(), ["現在の認証: 未ログイン"])
            auth._save_json(self.directory / "credentials.json", {
                "subject": "test-subject", "email": "user@example.com", "access_token": "secret-access",
                "refresh_token": "secret-refresh", "id_token": "secret-id",
            })
            auth._save_json(self.directory / "api-key.json", {"api_key": "sk-secret-key"})
            auth._save_json(self.directory / "active.json", {"method": "chatgpt"})
            chatgpt_status = "\n".join(auth.status_lines())
            self.assertIn("現在の認証: ChatGPTプラン", chatgpt_status)
            self.assertIn("user@example.com", chatgpt_status)
            self.assertIn("API key: sk-secret-key", chatgpt_status)
            self.assertNotIn("secret-access", chatgpt_status)
            self.assertNotIn("secret-refresh", chatgpt_status)
            self.assertNotIn("secret-id", chatgpt_status)
            auth._save_json(self.directory / "active.json", {"method": "api-key"})
            api_status = "\n".join(auth.status_lines())
            self.assertIn("現在の認証: OpenAI Platform API key", api_status)
            self.assertIn("user@example.com", api_status)
            self.assertIn("API key: sk-secret-key", api_status)
            auth._save_json(self.directory / "active.json", {"method": "chatgpt"})
            (self.directory / "credentials.json").unlink()
            self.assertIn("現在の認証: 未ログイン", auth.status_lines())

    def test_headless_import_keeps_local_host_id(self) -> None:
        jwk = SimpleNamespace(key=self.key.public_key())
        jwks_client = SimpleNamespace(get_signing_key_from_jwt=lambda token: jwk)
        local = self.directory / "local"
        remote = self.directory / "remote"
        with (
            patch("src.auth._config_dir", return_value=local),
            patch("src.auth.webbrowser.open", side_effect=self._open_browser),
            patch("src.auth._exchange", side_effect=self._tokens),
            patch("src.auth.jwt.PyJWKClient", return_value=jwks_client),
        ):
            auth.login()
        local_id = json.loads((local / "host.json").read_text())["ext_agent_host_id"]
        with (
            patch("src.auth._config_dir", return_value=remote),
            patch("src.auth.jwt.PyJWKClient", return_value=jwks_client),
        ):
            self.assertIsNone(auth.import_headless(None))
            remote_id = json.loads((remote / "host.json").read_text())["ext_agent_host_id"]
            self.assertEqual(auth.import_headless(str(local / "credentials.json")), "user@example.com")
        self.assertNotEqual(local_id, remote_id)
        self.assertEqual(json.loads((remote / "credentials.json").read_text())["ext_agent_host_id"], remote_id)
        self.assertEqual(json.loads((remote / "active.json").read_text()), {"method": "chatgpt"})

    def test_api_key_validation_and_failure_do_not_overwrite_credentials(self) -> None:
        response = MagicMock()
        response.__enter__.return_value.status = 200
        with (
            patch("src.auth._config_dir", return_value=self.directory),
            patch("src.auth.getpass.getpass", return_value="sk-test-secret"),
            patch("src.auth.urlopen", return_value=response) as request,
        ):
            self.assertEqual(auth.login_api_key(), "OpenAI Platform API key（従量課金）")
        self.assertEqual(request.call_args.args[0].get_header("Authorization"), "Bearer sk-test-secret")
        self.assertEqual(json.loads((self.directory / "api-key.json").read_text())["api_key"], "sk-test-secret")
        self.assertEqual(json.loads((self.directory / "active.json").read_text()), {"method": "api-key"})
        with (
            patch("src.auth._config_dir", return_value=self.directory),
            patch("src.auth.getpass.getpass", return_value="sk-invalid"),
            patch("src.auth.urlopen", side_effect=HTTPError("https://api.openai.com/v1/models", 401, "unauthorized", {}, None)),
        ):
            with self.assertRaisesRegex(auth.LoginError, "401"):
                auth.login_api_key()
        self.assertEqual(json.loads((self.directory / "api-key.json").read_text())["api_key"], "sk-test-secret")


if __name__ == "__main__":
    unittest.main()
