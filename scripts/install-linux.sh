#!/bin/sh
set -eu

if [ "$(uname -s)" != "Linux" ]; then
    echo "Linuxで実行してください。" >&2
    exit 1
fi

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
if [ -f "$SCRIPT_DIR/pshift" ]; then
    BINARY="$SCRIPT_DIR/pshift"
else
    BINARY="$SCRIPT_DIR/../dist/pshift"
fi
if [ ! -f "$BINARY" ]; then
    echo "pshiftが見つかりません。配布アーカイブを展開するか、先にscripts/build-linux.shを実行してください。" >&2
    exit 1
fi

mkdir -p "$HOME/.local/bin" "$HOME/.local/share/papershift"
install -m 755 "$BINARY" "$HOME/.local/bin/pshift"
install -m 644 "$SCRIPT_DIR/uninstall-linux.sh" "$HOME/.local/share/papershift/uninstall-linux.sh"
PROFILE="$HOME/.profile"
ENTRY='export PATH="$HOME/.local/bin:$PATH"'
if ! { [ -f "$PROFILE" ] && grep -Fqx "$ENTRY" "$PROFILE"; }; then
    printf '\n%s\n%s\n' '# PaperShift PATH' "$ENTRY" >> "$PROFILE"
fi
echo "インストールしました: $HOME/.local/bin/pshift"
echo "新しいログインシェルでpshift --helpを実行してください（現在のシェルでは . \"$PROFILE\"）。"
