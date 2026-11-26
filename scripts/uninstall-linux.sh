#!/bin/sh
set -eu

if [ "$(uname -s)" != "Linux" ]; then
    echo "Linuxで実行してください。" >&2
    exit 1
fi

rm -f "$HOME/.local/bin/pshift" "$HOME/.local/share/papershift/uninstall-linux.sh"
rmdir "$HOME/.local/share/papershift" 2>/dev/null || true
PROFILE="$HOME/.profile"
if [ -f "$PROFILE" ] && grep -Fqx '# PaperShift PATH' "$PROFILE"; then
    TEMP=$(mktemp "${TMPDIR:-/tmp}/pshift-profile.XXXXXX")
    trap 'rm -f "$TEMP"' EXIT HUP INT TERM
    awk '
        $0 == "# PaperShift PATH" {
            if (getline next_line > 0 && next_line == "export PATH=\"$HOME/.local/bin:$PATH\"") next
            print
            print next_line
            next
        }
        { print }
    ' "$PROFILE" > "$TEMP"
    cat "$TEMP" > "$PROFILE"
fi
echo 'PaperShiftを削除しました。新しいログインシェルでPATHの変更が反映されます。'
