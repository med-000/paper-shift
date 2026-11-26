#!/bin/sh
set -eu

if [ "$(uname -s)" != "Darwin" ]; then
    echo "macOSで実行してください。" >&2
    exit 1
fi

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
if [ -f "$SCRIPT_DIR/pshift" ]; then
    BINARY="$SCRIPT_DIR/pshift"
else
    BINARY="$SCRIPT_DIR/../dist/pshift"
fi

if [ ! -f "$BINARY" ]; then
    echo "pshiftが見つかりません。配布アーカイブを展開するか、先にscripts/build-macos.shを実行してください。" >&2
    exit 1
fi

mkdir -p "$HOME/.local/bin"
install -m 755 "$BINARY" "$HOME/.local/bin/pshift"

PROFILE="${ZDOTDIR:-$HOME}/.zprofile"
ENTRY='export PATH="$HOME/.local/bin:$PATH"'
if ! { [ -f "$PROFILE" ] && grep -Fqx "$ENTRY" "$PROFILE"; }; then
    printf '\n%s\n' "$ENTRY" >> "$PROFILE"
fi

echo "インストールしました: $HOME/.local/bin/pshift"
echo "PATHを${PROFILE}に設定しました。新しいターミナルでpshift --helpを実行してください。"
