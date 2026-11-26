"""Exercise the local callback and identity checks without a real ChatGPT account."""

import hashlib
import hmac
import json
import os
from pathlib import Path
import stat
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import urlopen

from cryptography.hazmat.primitives.asymmetric import rsa
import jwt

from src import auth


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


if __name__ == "__main__":
    unittest.main()
