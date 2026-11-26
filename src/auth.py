"""Official Sign in with ChatGPT flow for local open-source clients."""

import base64
import getpass
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
from filelock import FileLock, Timeout as LockTimeout


ISSUER = "https://auth.openai.com"
AUTHORIZE_URL = f"{ISSUER}/api/accounts/authorize"
TOKEN_URL = f"{ISSUER}/api/accounts/oauth/token"
REVOCATION_URL = f"{ISSUER}/api/accounts/oauth/revoke"
JWKS_URL = f"{ISSUER}/.well-known/jwks.json"
RESOURCE = "https://api.openai.com/v1"
CALLBACK_PATH = "/auth/callback"
SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
CLIENT_ID_PATTERN = re.compile(r"oaiapp_[A-Za-z0-9_-]+\Z")


class LoginError(Exception):
    """An authentication attempt could not be completed safely."""


def status_lines() -> list[str]:
    """Describe locally saved accounts and the API key on explicit request."""
    directory = _config_dir()
    active = _load_json(directory / "active.json")
    chatgpt = _load_json(directory / "credentials.json")
    api = _load_json(directory / "api-key.json")
    has_chatgpt = bool(chatgpt and isinstance(chatgpt.get("subject"), str) and chatgpt["subject"])
    has_api = bool(api and isinstance(api.get("api_key"), str) and api["api_key"])
    method = active.get("method") if active else ("chatgpt" if has_chatgpt else "api-key" if has_api else None)
    if method == "chatgpt" and has_chatgpt:
        lines = ["現在の認証: ChatGPTプラン"]
    elif method == "api-key" and has_api:
        lines = ["現在の認証: OpenAI Platform API key（従量課金）"]
    else:
        lines = ["現在の認証: 未ログイン"]
    if has_chatgpt:
        email = chatgpt.get("email")
        label = email if isinstance(email, str) and email else chatgpt["subject"]
        # Saved display names must not be able to write terminal control sequences.
        label = "".join(char for char in label if char.isprintable() and char not in "\x1b\x7f")
        lines.append(f"ChatGPTアカウント: {label}")
    if has_api:
        lines.append(f"API key: {api['api_key']}")
    return lines


def _revoke_refresh_token(client_id: str, refresh_token: str) -> bool:
    request = Request(
        REVOCATION_URL,
        data=urlencode({
            "token": refresh_token,
            "token_type_hint": "refresh_token",
            "client_id": client_id,
        }).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    for attempt in range(2):
        try:
            with urlopen(request, timeout=5) as response:
                return response.status == 200
        except HTTPError as error:
            if error.code < 500 or attempt == 1:
                return False
        except (URLError, TimeoutError):
            if attempt == 1:
                return False
        time.sleep(0.5)
    return False


def logout() -> list[str]:
    """End the renewable session and remove both locally stored login methods."""
    directory = _config_dir()
    if not directory.exists():
        return ["ログイン情報はありません。"]
    try:
        with FileLock(str(directory / "auth.lock"), timeout=10):
            return _logout_locked(directory)
    except LockTimeout as error:
        raise LoginError("認証情報の更新が進行中です。しばらくしてから再試行してください。") from error


def _logout_locked(directory: Path) -> list[str]:
    credentials = _load_json(directory / "credentials.json")
    api = _load_json(directory / "api-key.json")
    if credentials is None and api is None:
        (directory / "active.json").unlink(missing_ok=True)
        return ["ログイン情報はありません。"]

    revoked = True
    if credentials:
        client_id = credentials.get("client_id")
        refresh_token = credentials.get("refresh_token")
        subject = credentials.get("subject")
        if isinstance(client_id, str) and CLIENT_ID_PATTERN.fullmatch(client_id) and isinstance(subject, str) and subject:
            # Keep the account/client association, but never retain credentials.
            _save_json(directory / "registration.json", {
                "client_id": client_id, "subject": subject,
                "email": credentials.get("email") if isinstance(credentials.get("email"), str) else None,
            })
        if isinstance(client_id, str) and CLIENT_ID_PATTERN.fullmatch(client_id) and isinstance(refresh_token, str) and refresh_token:
            revoked = _revoke_refresh_token(client_id, refresh_token)
        else:
            revoked = False

    (directory / "credentials.json").unlink(missing_ok=True)
    (directory / "api-key.json").unlink(missing_ok=True)
    (directory / "active.json").unlink(missing_ok=True)
    messages = ["この端末のログイン情報を削除しました。"]
    if credentials and not revoked:
        messages.append("ChatGPT側でのトークン失効は確認できませんでした。必要ならChatGPTの設定からPaperShiftの接続を解除してください。")
    if api:
        messages.append("API key自体はOpenAI Platformで有効なままです。")
    return messages


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


def active_credential() -> tuple[str, str]:
    """Return the selected credential, refreshing ChatGPT tokens when necessary."""
    directory = _config_dir()
    active = _load_json(directory / "active.json")
    method = active.get("method") if active else None
    if method == "api-key":
        saved = _load_json(directory / "api-key.json")
        key = saved.get("api_key") if saved else None
        if not isinstance(key, str) or not key:
            raise LoginError("API keyが見つかりません。pshift loginを実行してください。")
        return method, key
    if method != "chatgpt":
        raise LoginError("ログインしていません。pshift loginを実行してください。")

    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        with FileLock(str(directory / "auth.lock"), timeout=10):
            path = directory / "credentials.json"
            saved = _load_json(path)
            if not saved or not isinstance(saved.get("access_token"), str) or not saved["access_token"]:
                raise LoginError("ChatGPT認証情報が見つかりません。pshift loginを実行してください。")
            scopes = saved.get("scopes")
            if not isinstance(scopes, list) or "chatgpt.tokens.use.direct" not in scopes:
                raise LoginError("ChatGPTプラン利用の権限がありません。pshift loginを実行してください。")
            try:
                expires_at = datetime.fromisoformat(saved["saved_at"]).timestamp() + int(saved["expires_in"])
            except (KeyError, TypeError, ValueError, OverflowError):
                expires_at = 0
            if time.time() + 60 >= expires_at:
                saved = _refresh_credentials(path, saved)
            return method, saved["access_token"]
    except LockTimeout as error:
        raise LoginError("認証情報の更新が進行中です。しばらくしてから再試行してください。") from error


def _refresh_credentials(path: Path, saved: dict) -> dict:
    client_id = saved.get("client_id")
    refresh_token = saved.get("refresh_token")
    if not isinstance(client_id, str) or not CLIENT_ID_PATTERN.fullmatch(client_id) or not isinstance(refresh_token, str) or not refresh_token:
        raise LoginError("更新に必要な認証情報がありません。pshift loginを実行してください。")
    request = Request(
        TOKEN_URL,
        data=urlencode({
            "grant_type": "refresh_token", "client_id": client_id,
            "refresh_token": refresh_token, "resource": RESOURCE,
        }).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            renewed = json.load(response)
    except HTTPError as error:
        if error.code == 400:
            try:
                code = json.load(error).get("error")
            except (ValueError, AttributeError):
                code = None
            if code in ("invalid_grant", "invalid_refresh_token", "refresh_token_expired", "refresh_token_invalidated", "refresh_token_reused"):
                _save_json(path.parent / "registration.json", {
                    "client_id": client_id, "subject": saved.get("subject"), "email": saved.get("email"),
                })
                path.unlink(missing_ok=True)
                raise LoginError("ChatGPTのセッションが失効しました。pshift loginを再実行してください。") from error
        raise LoginError(f"ChatGPTトークンの更新に失敗しました (HTTP {error.code})。") from error
    except (URLError, TimeoutError, ValueError) as error:
        raise LoginError("ChatGPTトークンの更新中に通信エラーが発生しました。") from error
    if not isinstance(renewed, dict) or not all(isinstance(renewed.get(k), str) and renewed[k] for k in ("access_token", "refresh_token")):
        raise LoginError("ChatGPTのトークン更新応答が不正です。")
    if not isinstance(renewed.get("token_type"), str) or renewed["token_type"].lower() != "bearer":
        raise LoginError("ChatGPTのトークン形式が不正です。")
    scopes = renewed.get("scope")
    if not isinstance(scopes, str) or not {"resource.invoke", "chatgpt.tokens.use.direct"}.issubset(scopes.split()):
        raise LoginError("ChatGPTプラン利用の権限がありません。pshift loginを再実行してください。")
    lifetime = renewed.get("expires_in")
    if not isinstance(lifetime, int) or lifetime <= 0:
        raise LoginError("ChatGPTの有効期限が不正です。")
    saved.update(
        access_token=renewed["access_token"], refresh_token=renewed["refresh_token"],
        expires_in=lifetime, scopes=scopes.split(), saved_at=datetime.now(timezone.utc).isoformat(),
    )
    _save_json(path, saved)
    return saved


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


def login(method: str = "browser") -> str:
    """Run the browser OAuth flow and save an authorized ChatGPT account locally."""
    if method not in ("browser", "manual"):
        raise LoginError("ログイン方法が不正です。")
    directory = _config_dir()
    host_id = _host_id(directory)
    existing = _load_json(directory / "credentials.json")
    previous = existing or _load_json(directory / "registration.json")
    previous_client = previous.get("client_id") if previous else None
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
        if method == "manual":
            print(f"次のURLをこの端末のブラウザで開いてください（5分以内）:\n{auth_url}")
            print("認証後はこの端末の127.0.0.1に戻るため、別の端末のブラウザでは完了しません。")
        else:
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
    if previous and (claims["sub"] != previous.get("subject") or client_id != previous.get("client_id")):
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
    _save_json(directory / "active.json", {"method": "chatgpt"})
    return record["email"] or claims["sub"]


def import_headless(source: str | None) -> str | None:
    """Import credentials obtained locally, keeping this machine's host ID."""
    directory = _config_dir()
    host_id = _host_id(directory)
    if source is None:
        print("headless端末のChatGPT認証手順:")
        print("  1. ブラウザが使える手元の端末で `pshift login --method browser` を実行")
        print("  2. 手元の認証ファイルをSSHなどの安全な方法でheadless端末に転送")
        print("     macOS/Linux: ~/.config/papershift/credentials.json")
        print("     Windows: %LOCALAPPDATA%\\PaperShift\\credentials.json")
        print("  3. headless端末で `pshift login --method headless --from-file <転送したファイル>` を実行")
        print("認証ファイルにはアクセストークンと更新トークンが含まれます。公開・共有しないでください。")
        return None

    try:
        incoming = _load_json(Path(source))
    except OSError as error:
        raise LoginError("転送された認証ファイルを読めません。") from error
    if incoming is None:
        raise LoginError("転送された認証ファイルが見つかりません。")
    client_id = incoming.get("client_id")
    if not isinstance(client_id, str) or not CLIENT_ID_PATTERN.fullmatch(client_id):
        raise LoginError("転送されたクライアントIDが不正です。")
    if incoming.get("issuer") != ISSUER:
        raise LoginError("転送された認証情報の発行元が不正です。")
    if not isinstance(incoming.get("id_token"), str):
        raise LoginError("転送されたIDトークンがありません。")
    try:
        key = jwt.PyJWKClient(JWKS_URL, timeout=15).get_signing_key_from_jwt(incoming["id_token"])
        claims = jwt.decode(
            incoming["id_token"], key.key, algorithms=["RS256"],
            audience=client_id, issuer=ISSUER,
            options={"require": ["iss", "aud", "sub", "iat", "exp"], "verify_exp": False},
        )
    except (jwt.PyJWTError, URLError, TimeoutError, ValueError) as error:
        raise LoginError("転送されたIDトークンを検証できませんでした。") from error
    if not isinstance(claims.get("sub"), str) or not claims["sub"] or claims["sub"] != incoming.get("subject"):
        raise LoginError("転送されたアカウントIDが一致しません。")
    if not all(isinstance(incoming.get(field), str) and incoming[field] for field in ("access_token", "refresh_token")):
        raise LoginError("転送された認証情報に必要なトークンがありません。")
    scopes = incoming.get("scopes")
    if not isinstance(scopes, list) or not all(isinstance(scope, str) for scope in scopes) or not {"offline_access", "resource.invoke", "chatgpt.tokens.use.direct"}.issubset(scopes):
        raise LoginError("転送された認証情報にはChatGPTプラン利用権限がありません。")
    existing = _load_json(directory / "credentials.json")
    if existing and (existing.get("subject"), existing.get("client_id")) != (claims["sub"], client_id):
        raise LoginError("既存のChatGPTアカウントと異なります。")
    incoming["ext_agent_host_id"] = host_id
    incoming["email"] = claims.get("email") if isinstance(claims.get("email"), str) else None
    _save_json(directory / "credentials.json", incoming)
    _save_json(directory / "active.json", {"method": "chatgpt"})
    return incoming["email"] or claims["sub"]


def login_api_key() -> str:
    """Validate and store a user-supplied Platform API key separately from ChatGPT."""
    print("API keyはChatGPT Pro/Plusプランとは別のOpenAI Platform従量課金です。")
    key = getpass.getpass("OpenAI API key: ").strip()
    if not key:
        raise LoginError("API keyが入力されていません。")
    request = Request(
        "https://api.openai.com/v1/models",
        headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=15) as response:
            if response.status != 200:
                raise LoginError("API keyを検証できませんでした。")
    except HTTPError as error:
        raise LoginError(f"API keyの検証に失敗しました (HTTP {error.code})。") from error
    except (URLError, TimeoutError) as error:
        raise LoginError("API keyの検証中に通信エラーが発生しました。") from error
    directory = _config_dir()
    _save_json(directory / "api-key.json", {"api_key": key})
    _save_json(directory / "active.json", {"method": "api-key"})
    return "OpenAI Platform API key（従量課金）"
