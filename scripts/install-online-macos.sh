#!/bin/sh
set -eu

if [ "$(uname -s)" != "Darwin" ]; then
    echo "macOSで実行してください。" >&2
    exit 1
fi

BASE_URL=${PAPERSHIFT_RELEASE_BASE_URL:-}
if [ -z "$BASE_URL" ]; then
    echo "公開URLはまだありません。リリース公開後にPAPERSHIFT_RELEASE_BASE_URLを設定してください。" >&2
    exit 1
fi

case "$(uname -m)" in
    arm64|x86_64) ARCH=$(uname -m) ;;
    *) echo "未対応のCPUアーキテクチャです。" >&2; exit 1 ;;
esac

TMP=$(mktemp -d "${TMPDIR:-/tmp}/pshift-install.XXXXXX")
trap 'rm -rf "$TMP"' EXIT HUP INT TERM

ARCHIVE="pshift-macos-${ARCH}.tar.gz"
curl -fsSL "${BASE_URL%/}/$ARCHIVE" -o "$TMP/$ARCHIVE"
tar -xzf "$TMP/$ARCHIVE" -C "$TMP"
sh "$TMP/install-macos.sh"
