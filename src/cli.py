"""Command-line entry point for PaperShift."""

import argparse
from importlib.metadata import version
import sys

from src.auth import LoginError, import_headless, login, login_api_key


def _login_method() -> str:
    if not sys.stdin.isatty():
        return "browser"
    print("OpenAIへの認証方法を選択してください:")
    print("  1. ChatGPT Pro/Plus (browser)")
    print("  2. ChatGPT Pro/Plus (headless: 別端末で認証して転送)")
    print("  3. API key (ChatGPTプラン外・従量課金)")
    while True:
        choice = input("選択 [1]: ").strip()
        if choice in ("", "1"):
            return "browser"
        if choice == "2":
            return "headless"
        if choice == "3":
            return "api-key"
        print("1、2、3のいずれかを入力してください。")


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
    login_parser = subcommands.add_parser("login", help="ChatGPTまたはAPI keyで認証")
    login_parser.add_argument(
        "--method", choices=("browser", "headless", "api-key", "manual"),
        help="browser / headless / api-key （manualは旧URL表示モード）",
    )
    login_parser.add_argument(
        "--from-file", metavar="PATH",
        help="headless: 手元の端末から安全に転送したcredentials.jsonを取り込む",
    )
    args = parser.parse_args()
    if args.command == "login":
        try:
            method = args.method or _login_method()
            if args.from_file and method != "headless":
                parser.error("--from-fileは--method headlessと一緒に指定してください。")
            if method == "headless":
                identity = import_headless(args.from_file)
                if identity is None:
                    return
            elif method == "api-key":
                identity = login_api_key()
            else:
                identity = login(method=method)
        except KeyboardInterrupt:
            parser.exit(130, "\nログインを中断しました。\n")
        except EOFError:
            parser.exit(1, "ログイン方法を選択できませんでした。--methodを指定してください。\n")
        except (LoginError, OSError) as error:
            parser.exit(1, f"ログインに失敗しました: {error}\n")
        print(f"ログインしました: {identity}")
    else:
        parser.print_help()
