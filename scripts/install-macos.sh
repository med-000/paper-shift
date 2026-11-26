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
mkdir -p "$HOME/.local/share/papershift"
install -m 755 "$BINARY" "$HOME/.local/bin/pshift"
UNINSTALL="$SCRIPT_DIR/uninstall-macos.sh"
if [ -f "$UNINSTALL" ]; then
    install -m 644 "$UNINSTALL" "$HOME/.local/share/papershift/uninstall-macos.sh"
fi

PROFILE="${ZDOTDIR:-$HOME}/.zprofile"
ENTRY='export PATH="$HOME/.local/bin:$PATH"'
if ! { [ -f "$PROFILE" ] && grep -Fqx "$ENTRY" "$PROFILE"; }; then
    printf '\n%s\n%s\n' '# PaperShift PATH' "$ENTRY" >> "$PROFILE"
fi

echo "インストールしました: $HOME/.local/bin/pshift"
echo "PATHを${PROFILE}に設定しました。新しいターミナルでpshift --helpを実行してください。"
