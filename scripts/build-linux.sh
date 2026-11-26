#!/bin/sh
set -eu

if [ "$(uname -s)" != "Linux" ]; then
    echo "Linuxで実行してください。" >&2
    exit 1
fi

ROOT=$(CDPATH= cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

uv run --with pyinstaller pyinstaller \
    --noconfirm --clean --onefile --name pshift \
    --copy-metadata paper-shift \
    --add-data "$ROOT/src/fonts:src/fonts" \
    src/__main__.py

case "$(uname -m)" in
    x86_64) ARCH=x86_64 ;;
    *) echo "未対応のLinuxアーキテクチャです。" >&2; exit 1 ;;
esac
tar -czf "dist/pshift-linux-${ARCH}.tar.gz" \
    -C "$ROOT/dist" pshift \
    -C "$ROOT/scripts" install-linux.sh uninstall-linux.sh
echo "作成しました: dist/pshift-linux-${ARCH}.tar.gz"
