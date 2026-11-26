#!/bin/sh
set -eu

if [ "$(uname -s)" != "Darwin" ]; then
    echo "macOSで実行してください。" >&2
    exit 1
fi

ROOT=$(CDPATH= cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

uv run --with pyinstaller pyinstaller \
    --noconfirm \
    --clean \
    --onefile \
    --name pshift \
    --copy-metadata paper-shift \
    --add-data "$ROOT/src/fonts:src/fonts" \
    src/__main__.py

ARCH=$(uname -m)
tar -czf "dist/pshift-macos-${ARCH}.tar.gz" \
    -C "$ROOT/dist" pshift \
    -C "$ROOT/scripts" install-macos.sh uninstall-macos.sh

echo "作成しました: dist/pshift-macos-${ARCH}.tar.gz"
