#!/bin/sh
set -eu

if [ "$(uname -s)" != "Darwin" ]; then
    echo "macOSで実行してください。" >&2
    exit 1
fi

rm -f "$HOME/.local/bin/pshift"
rm -f "$HOME/.local/share/papershift/uninstall-macos.sh"
rmdir "$HOME/.local/share/papershift" 2>/dev/null || true

PROFILE="${ZDOTDIR:-$HOME}/.zprofile"
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

echo 'PaperShiftを削除しました。新しいターミナルでPATHの変更が反映されます。'
