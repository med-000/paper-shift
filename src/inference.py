"""Account-specific model selection and short text translation via Responses."""

import hashlib
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src import auth


MODELS_URL = "https://api.openai.com/v1/models"
RESPONSES_URL = "https://api.openai.com/v1/responses"
MODEL_SLUG = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*\Z")


class InferenceError(Exception):
    """A model or inference operation did not complete."""


def _request_error(error: HTTPError) -> InferenceError:
    request_id = error.headers.get("x-request-id") if error.headers else None
    code = None
    try:
        body = json.load(error)
        detail = body.get("error", body.get("detail")) if isinstance(body, dict) else None
        if isinstance(detail, dict):
            code = detail.get("code") or detail.get("message")
        elif isinstance(detail, str):
            code = detail
    except (ValueError, UnicodeError, OSError):
        pass
    parts = [f"HTTP {error.code}"]
    if isinstance(code, str):
        parts.append(code[:200])
    if request_id:
        parts.append(f"request ID: {request_id}")
    return InferenceError("OpenAIのリクエストに失敗しました (" + ", ".join(parts) + ")。")


def _open(request: Request):
    try:
        return urlopen(request, timeout=90)
    except HTTPError as error:
        raise _request_error(error) from error
    except (URLError, TimeoutError) as error:
        raise InferenceError("OpenAIへの接続に失敗しました。") from error


def _model_identity(method: str, credential: str) -> str:
    if method == "api-key":
        return hashlib.sha256(credential.encode("utf-8")).hexdigest()
    saved = auth._load_json(auth._config_dir() / "credentials.json")
    client_id = saved.get("client_id") if saved else None
    if not isinstance(client_id, str) or not auth.CLIENT_ID_PATTERN.fullmatch(client_id):
        raise InferenceError("ChatGPTのクライアントIDが見つかりません。pshift loginを実行してください。")
    return client_id


def selected_model(method: str, credential: str) -> str | None:
    saved = auth._load_json(auth._config_dir() / "model.json")
    if not saved or saved.get("method") != method or saved.get("identity") != _model_identity(method, credential):
        return None
    slug = saved.get("slug")
    return slug if isinstance(slug, str) and MODEL_SLUG.fullmatch(slug) else None


def select_model(method: str, credential: str, slug: str) -> None:
    if not MODEL_SLUG.fullmatch(slug):
        raise InferenceError("モデル名が不正です。")
    auth._save_json(auth._config_dir() / "model.json", {
        "method": method, "identity": _model_identity(method, credential), "slug": slug,
    })


def list_models(method: str, credential: str) -> list[tuple[str, str]]:
    request = Request(MODELS_URL, headers={"Authorization": f"Bearer {credential}", "Accept": "application/json"})
    try:
        with _open(request) as response:
            body = json.load(response)
    except (ValueError, UnicodeError) as error:
        raise InferenceError("モデル一覧の応答を読み取れませんでした。") from error
    if not isinstance(body, dict):
        raise InferenceError("モデル一覧の形式が不正です。")
    entries = body.get("models") if method == "chatgpt" else body.get("data")
    if not isinstance(entries, list):
        raise InferenceError("モデル一覧の形式が不正です。")
    result = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if method == "chatgpt":
            if entry.get("visibility") != "list":
                continue
            slug = entry.get("slug")
            display = entry.get("display_name")
        else:
            slug = entry.get("id")
            display = slug
        if isinstance(slug, str) and MODEL_SLUG.fullmatch(slug):
            result.append((slug, display if isinstance(display, str) and display else slug))
    if not result:
        raise InferenceError("選択可能なモデルが見つかりませんでした。")
    return result


def _events(response):
    lines = []
    for raw in response:
        try:
            line = raw.decode("utf-8").rstrip("\r\n")
        except UnicodeError as error:
            raise InferenceError("推論ストリームを読み取れませんでした。") from error
        if not line:
            if lines:
                data = "\n".join(lines)
                lines = []
                if data != "[DONE]":
                    try:
                        yield json.loads(data)
                    except ValueError as error:
                        raise InferenceError("推論イベントの形式が不正です。") from error
        elif line.startswith("data:"):
            lines.append(line[5:].lstrip(" "))
    if lines:
        try:
            yield json.loads("\n".join(lines))
        except ValueError as error:
            raise InferenceError("推論イベントの形式が不正です。") from error


def _failure(event: dict) -> InferenceError:
    response = event.get("response")
    error = response.get("error") if isinstance(response, dict) else None
    if not isinstance(error, dict):
        error = event.get("error")
    code = error.get("code") or error.get("message") if isinstance(error, dict) else None
    return InferenceError(f"推論が完了しませんでした: {str(code)[:200] if code else event.get('type', 'unknown')}")


def _complete_text(credential: str, payload: dict) -> str:
    request = Request(
        RESPONSES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {credential}", "Content-Type": "application/json", "Accept": "text/event-stream"},
        method="POST",
    )
    chunks = []
    length = 0
    try:
        with _open(request) as response:
            for event in _events(response):
                if not isinstance(event, dict):
                    continue
                kind = event.get("type")
                if kind == "response.output_text.delta" and isinstance(event.get("delta"), str):
                    chunks.append(event["delta"])
                    length += len(event["delta"])
                    if length > 20000:
                        raise InferenceError("訳文が長すぎるため中断しました。")
                elif kind == "response.completed":
                    result = event.get("response")
                    if isinstance(result, dict) and result.get("status", "completed") != "completed":
                        raise _failure(event)
                    if not chunks:
                        if isinstance(result, dict):
                            for output in result.get("output", []) if isinstance(result.get("output"), list) else []:
                                if isinstance(output, dict):
                                    for content in output.get("content", []) if isinstance(output.get("content"), list) else []:
                                        if isinstance(content, dict) and content.get("type") == "output_text":
                                            value = content.get("text")
                                            if isinstance(value, str):
                                                chunks.append(value)
                    translation = "".join(chunks).strip()
                    if not translation:
                        raise InferenceError("推論は完了しましたが訳文がありません。")
                    return translation
                elif kind in ("response.failed", "response.incomplete", "error"):
                    raise _failure(event)
    except (URLError, TimeoutError, OSError) as error:
        raise InferenceError("推論ストリームが途中で切断されました。") from error
    raise InferenceError("推論ストリームが完了前に終了しました。")


def translate(method: str, credential: str, model: str, text: str) -> str:
    if not text.strip() or len(text) > 4000:
        raise InferenceError("翻訳する英文を1～4000文字で入力してください。")
    return _complete_text(credential, {
        "model": model,
        "instructions": "Translate the user's English text into natural Japanese. Output only the translation, without commentary.",
        "input": [{"role": "user", "content": text}],
        "store": False,
        "stream": True,
    })


def translate_many(method: str, credential: str, model: str, texts: list[str]) -> list[str]:
    """Translate ordered PDF fragments in one Responses turn with explicit correspondence."""
    if not texts or any(not item.strip() for item in texts) or sum(map(len, texts)) > 3500:
        raise InferenceError("PDFの翻訳領域が長すぎます。")
    if len(texts) == 1:
        return [translate(method, credential, model, texts[0])]
    result = _complete_text(credential, {
        "model": model,
        "instructions": (
            "Translate each string in the input JSON texts array from English into natural Japanese. "
            "Keep the order and number of items exactly the same. "
            'Respond with only a valid JSON object: {"translations":["Japanese text", ...]}. '
            "No markdown or other commentary."
        ),
        "input": [{"role": "user", "content": json.dumps({"texts": texts}, ensure_ascii=False)}],
        "store": False,
        "stream": True,
    })
    try:
        parsed = json.loads(result)
    except ValueError as error:
        raise InferenceError("モデルがPDF翻訳の対応表を返しませんでした。再実行してください。") from error
    translated = parsed.get("translations") if isinstance(parsed, dict) else None
    if not isinstance(translated, list) or len(translated) != len(texts) or not all(isinstance(item, str) and item.strip() for item in translated):
        raise InferenceError("モデルのPDF翻訳結果が元の領域数と一致しません。")
    return [item.strip() for item in translated]
