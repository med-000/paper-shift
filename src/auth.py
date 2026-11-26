"""Official Sign in with ChatGPT flow for local open-source clients."""

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
from http.server import BaseHTTPRequestHandler, HTTPServer
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen
import uuid
import webbrowser

import jwt


ISSUER = "https://auth.openai.com"
AUTHORIZE_URL = f"{ISSUER}/api/accounts/authorize"
TOKEN_URL = f"{ISSUER}/api/accounts/oauth/token"
JWKS_URL = f"{ISSUER}/.well-known/jwks.json"
RESOURCE = "https://api.openai.com/v1"
CALLBACK_PATH = "/auth/callback"
SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
CLIENT_ID_PATTERN = re.compile(r"oaiapp_[A-Za-z0-9_-]+\Z")


class LoginError(Exception):
    """An authentication attempt could not be completed safely."""


def _config_dir() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "PaperShift"
    return Path.home() / ".config" / "papershift"


def _save_json(path: Path, value: dict) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(value, output, ensure_ascii=False)
            output.write("\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as error:
        raise LoginError(f"保存済みの認証情報を読めません: {path}") from error
    if not isinstance(value, dict):
        raise LoginError(f"保存済みの認証情報が不正です: {path}")
    return value


def _host_id(directory: Path) -> str:
    path = directory / "host.json"
    record = _load_json(path)
    if record is None:
        host_id = f"urn:uuid:{uuid.uuid4()}"
        _save_json(path, {"ext_agent_host_id": host_id})
        return host_id
    host_id = record.get("ext_agent_host_id")
    if not isinstance(host_id, str) or not host_id.startswith("urn:uuid:"):
        raise LoginError("保存済みのホストIDが不正です。")
    try:
        uuid.UUID(host_id.removeprefix("urn:uuid:"))
    except ValueError as error:
        raise LoginError("保存済みのホストIDが不正です。") from error
    return host_id


def _callback(server: HTTPServer, state: str, deadline: float) -> dict[str, str]:
    result: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            pass  # Never log a callback containing an authorization code.

        def do_GET(self) -> None:
            if urlsplit(self.path).path != CALLBACK_PATH or self.headers.get("Host") != f"127.0.0.1:{server.server_port}":
                self.send_error(404)
                return

            params = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
            returned_state = params.get("state", [])
            if len(returned_state) != 1 or not hmac.compare_digest(returned_state[0], state):
                result["error"] = "認証のstateが一致しません。最初からやり直してください。"
            else:
                for name in ("code", "client_id", "error"):
                    values = params.get(name, [])
                    if len(values) > 1:
                        result["error"] = "認証の戻り値が不正です。"
                        break
                    if values:
                        result[name] = values[0]

            body = (
                "<html><meta charset='utf-8'><body>"
                "認証結果を受け取りました。このタブを閉じてターミナルに戻ってください。"
                "</body></html>"
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)

    server.RequestHandlerClass = Handler
    server.timeout = 1
    while not result and time.monotonic() < deadline:
        server.handle_request()
    if not result:
        raise LoginError("認証が時間切れになりました。pshift loginを再実行してください。")
    return result


def _exchange(code: str, client_id: str, verifier: str, redirect_uri: str) -> dict:
    form = urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": verifier,
        "resource": RESOURCE,
    }).encode("utf-8")
    request = Request(
        TOKEN_URL,
        data=form,
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            tokens = json.load(response)
    except HTTPError as error:
        raise LoginError(f"OpenAIのトークン交換に失敗しました (HTTP {error.code})。") from error
    except (URLError, TimeoutError, ValueError) as error:
        raise LoginError("OpenAIとの通信または応答の読み取りに失敗しました。") from error
    if not isinstance(tokens, dict):
        raise LoginError("OpenAIのトークン応答が不正です。")
    return tokens


def _verify_identity(id_token: str, client_id: str, nonce: str) -> dict:
    try:
        key = jwt.PyJWKClient(JWKS_URL, timeout=15).get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token,
            key.key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=ISSUER,
            options={"require": ["iss", "aud", "exp", "iat", "sub"]},
        )
    except (jwt.PyJWTError, URLError, TimeoutError, ValueError) as error:
        raise LoginError("OpenAIのIDトークンを検証できませんでした。") from error
    if not isinstance(claims.get("sub"), str) or not claims["sub"]:
        raise LoginError("IDトークンにアカウントIDがありません。")
    if not isinstance(claims.get("nonce"), str) or not hmac.compare_digest(claims["nonce"], nonce):
        raise LoginError("IDトークンのnonceが一致しません。")
    return claims


def login() -> str:
    """Run the browser OAuth flow and save an authorized ChatGPT account locally."""
    directory = _config_dir()
    host_id = _host_id(directory)
    existing = _load_json(directory / "credentials.json")
    previous_client = existing.get("client_id") if existing else None
    if previous_client is not None and (not isinstance(previous_client, str) or not CLIENT_ID_PATTERN.fullmatch(previous_client)):
        raise LoginError("保存済みのクライアントIDが不正です。")

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")

    with HTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler) as server:
        redirect_uri = f"http://127.0.0.1:{server.server_port}{CALLBACK_PATH}"
        params = {
            "client_id": previous_client or "dynamic_agent_client",
            "ext_agent_host_id": host_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": SCOPES,
            "resource": RESOURCE,
            "state": state,
            "nonce": nonce,
            "code_challenge_method": "S256",
            "code_challenge": challenge,
        }
        if not previous_client:
            params["agent_name_hint"] = "PaperShift"
        auth_url = f"{AUTHORIZE_URL}?{urlencode(params)}"
        print("ChatGPTの認証ページをブラウザで開きます。完了まで最大5分待ちます。")
        if not webbrowser.open(auth_url):
            print(f"ブラウザを開けない場合は、次のURLを開いてください:\n{auth_url}")
        callback = _callback(server, state, time.monotonic() + 300)

    if callback.get("error"):
        if callback["error"] == "access_denied":
            raise LoginError("ChatGPTでの認証またはプラン利用の許可が取り消されました。")
        if callback["error"].startswith("認証の"):
            raise LoginError(callback["error"])
        raise LoginError("ChatGPTの認証が完了しませんでした。")
    code = callback.get("code")
    client_id = callback.get("client_id", previous_client)
    if not code or not client_id or not CLIENT_ID_PATTERN.fullmatch(client_id):
        raise LoginError("認証コードまたは発行済みクライアントIDを取得できませんでした。")
    if previous_client and client_id != previous_client:
        raise LoginError("登録済みのクライアントIDと一致しません。")

    tokens = _exchange(code, client_id, verifier, redirect_uri)
    for field in ("id_token", "access_token", "refresh_token"):
        if not isinstance(tokens.get(field), str) or not tokens[field]:
            raise LoginError(f"OpenAIの応答に{field}がありません。")
    token_type = tokens.get("token_type")
    if not isinstance(token_type, str) or token_type.lower() != "bearer":
        raise LoginError("OpenAIのトークン形式が不正です。")
    granted = tokens.get("scope")
    if not isinstance(granted, str) or not {"resource.invoke", "chatgpt.tokens.use.direct"}.issubset(granted.split()):
        raise LoginError("ChatGPTプラン利用の権限が付与されませんでした。")

    claims = _verify_identity(tokens["id_token"], client_id, nonce)
    if existing and (claims["sub"] != existing.get("subject") or client_id != existing.get("client_id")):
        raise LoginError("保存済みのChatGPTアカウントと一致しません。")
    record = {
        "issuer": ISSUER,
        "subject": claims["sub"],
        "email": claims.get("email") if isinstance(claims.get("email"), str) else None,
        "client_id": client_id,
        "ext_agent_host_id": host_id,
        "id_token": tokens["id_token"],
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": "Bearer",
        "expires_in": tokens.get("expires_in"),
        "scopes": granted.split(),
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_json(directory / "credentials.json", record)
    return record["email"] or claims["sub"]
