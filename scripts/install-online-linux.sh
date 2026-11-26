#!/bin/sh
set -eu

if [ "$(uname -s)" != "Linux" ]; then
    echo "Linuxで実行してください。" >&2
    exit 1
fi
if [ "$(uname -m)" != "x86_64" ]; then
    echo "Linux x86_64のみ対応しています。" >&2
    exit 1
fi

BASE_URL=${PAPERSHIFT_RELEASE_BASE_URL:-https://github.com/med-000/paper-shift/releases/latest/download}
TMP=$(mktemp -d "${TMPDIR:-/tmp}/pshift-install.XXXXXX")
trap 'rm -rf "$TMP"' EXIT HUP INT TERM
ARCHIVE=pshift-linux-x86_64.tar.gz
curl -fsSL "${BASE_URL%/}/$ARCHIVE" -o "$TMP/$ARCHIVE"
tar -xzf "$TMP/$ARCHIVE" -C "$TMP"
sh "$TMP/install-linux.sh"
