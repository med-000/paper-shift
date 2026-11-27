"""Update an installed PaperShift executable from the latest GitHub release."""

from importlib.metadata import version
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


RELEASE_URL = "https://api.github.com/repos/med-000/paper-shift/releases/latest"
MAX_ARCHIVE = 100 * 1024 * 1024
MAX_BINARY = 150 * 1024 * 1024


class UpdateError(Exception):
    """A release cannot be safely installed."""


def _version(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", value)
    if not match:
        raise UpdateError(f"リリースのバージョン形式が不正です: {value}")
    return tuple(map(int, match.groups()))


def _request(url: str):
    return urlopen(Request(url, headers={"User-Agent": "PaperShift-Updater", "Accept": "application/vnd.github+json"}), timeout=20)


def _release() -> dict:
    try:
        with _request(RELEASE_URL) as response:
            data = json.load(response)
        if not isinstance(data, dict) or not isinstance(data.get("assets"), list):
            raise ValueError("missing assets")
        return data
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as error:
        raise UpdateError("最新リリースを取得できませんでした。接続を確認してください。") from error


def _archive_name() -> str:
    system, machine = platform.system(), platform.machine().lower()
    if system == "Darwin" and machine == "arm64":
        return "pshift-macos-arm64.tar.gz"
    if system == "Linux" and machine == "x86_64":
        return "pshift-linux-x86_64.tar.gz"
    raise UpdateError("このOS・CPU向けのCLI配布物はありません。")


def _asset(release: dict, name: str) -> dict:
    matches = [asset for asset in release["assets"] if isinstance(asset, dict) and asset.get("name") == name]
    if len(matches) != 1:
        raise UpdateError(f"最新版に配布物がありません: {name}")
    asset = matches[0]
    url = asset.get("browser_download_url")
    expected = f"https://github.com/med-000/paper-shift/releases/download/{release['tag_name']}/{name}"
    if not isinstance(url, str) or url != expected:
        raise UpdateError("配布物のURLが不正です。")
    return asset


def _binary(asset: dict, archive_path: Path, binary_path: Path, release_version: str) -> None:
    try:
        digest = asset.get("digest")
        if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            raise UpdateError("配布物のチェックサムがありません。")
        checksum = hashlib.sha256()
        with _request(asset["browser_download_url"]) as response, archive_path.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                if output.tell() + len(chunk) > MAX_ARCHIVE:
                    raise UpdateError("配布物のサイズが大きすぎます。")
                checksum.update(chunk)
                output.write(chunk)
        if checksum.hexdigest() != digest.removeprefix("sha256:"):
            raise UpdateError("配布物のチェックサムが一致しません。")
        with tarfile.open(archive_path, "r:gz") as archive:
            member = archive.getmember("pshift")
            if not member.isfile() or member.size <= 0 or member.size > MAX_BINARY:
                raise UpdateError("配布物の実行ファイルが不正です。")
            stream = archive.extractfile(member)
            if stream is None:
                raise UpdateError("配布物を読み取れません。")
            with stream, binary_path.open("wb") as output:
                shutil.copyfileobj(stream, output)
        binary_path.chmod(0o755)
        result = subprocess.run([str(binary_path), "--version"], capture_output=True, text=True, timeout=30, check=False)
        if result.returncode != 0 or result.stdout.strip() != f"pshift {release_version}":
            raise UpdateError("ダウンロードした実行ファイルのバージョンが一致しません。")
    except (HTTPError, URLError, TimeoutError, OSError, tarfile.TarError, KeyError, subprocess.TimeoutExpired) as error:
        raise UpdateError("配布物の取得または検証に失敗しました。現在の実行ファイルは変更していません。") from error


def update(*, check: bool = False) -> str:
    if not getattr(sys, "frozen", False):
        raise UpdateError("ソース版は自動更新できません。git pullとuv syncで更新してください。")
    target = Path.home() / ".local/bin/pshift"
    if target.is_symlink() or not target.is_file() or not os.path.samefile(sys.executable, target):
        raise UpdateError("標準インストール先以外から実行中です。配布元のインストール手順で更新してください。")
    current = version("paper-shift")
    release = _release()
    latest = release.get("tag_name")
    if not isinstance(latest, str):
        raise UpdateError("リリースのバージョンが見つかりません。")
    if _version(latest) <= _version(current):
        return f"最新版です: {current}"
    name = _archive_name()
    asset = _asset(release, name)
    if check:
        return f"更新可能: {current} → {latest.lstrip('v')}"
    try:
        with tempfile.TemporaryDirectory(prefix=".pshift-update-", dir=target.parent) as directory:
            temp = Path(directory)
            replacement = temp / "pshift"
            _binary(asset, temp / name, replacement, latest.lstrip("v"))
            os.replace(replacement, target)
    except OSError as error:
        raise UpdateError("更新ファイルを配置できませんでした。現在の実行ファイルは変更していません。") from error
    return f"更新しました: {current} → {latest.lstrip('v')}"
