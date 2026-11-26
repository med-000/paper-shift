"""Command-line entry point for PaperShift."""

import argparse
from importlib.metadata import version

from src.auth import LoginError, login


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pshift",
        description="PDF翻訳ツール（翻訳機能は今後実装予定）",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {version('paper-shift')}",
    )
    subcommands = parser.add_subparsers(dest="command")
    subcommands.add_parser("login", help="ChatGPTアカウントでログイン")
    args = parser.parse_args()
    if args.command == "login":
        try:
            identity = login()
        except KeyboardInterrupt:
            parser.exit(130, "\nログインを中断しました。\n")
        except (LoginError, OSError) as error:
            parser.exit(1, f"ログインに失敗しました: {error}\n")
        print(f"ログインしました: {identity}")
    else:
        parser.print_help()
