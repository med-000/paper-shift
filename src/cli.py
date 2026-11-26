"""Command-line entry point for PaperShift."""

import argparse
from importlib.metadata import version
import sys

import questionary

from src.auth import LoginError, import_headless, login, login_api_key, logout


def _login_method() -> str:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return "browser"
    method = questionary.select(
        "OpenAIへの認証方法を選択してください（↑↓で選択、Enterで決定）",
        choices=[
            questionary.Choice("ChatGPT Pro/Plus (browser)", value="browser"),
            questionary.Choice("ChatGPT Pro/Plus (headless: 別端末で認証して転送)", value="headless"),
            questionary.Choice("API key (ChatGPTプラン外・従量課金)", value="api-key"),
        ],
        use_shortcuts=False,
    ).ask()
    if method is None:
        raise KeyboardInterrupt
    return method


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
    subcommands.add_parser("status", help="保存済みの認証状態を表示")
    subcommands.add_parser("logout", help="保存済みの認証情報を削除")
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
    if args.command == "logout":
        try:
            for line in logout():
                print(line)
        except (LoginError, OSError) as error:
            parser.exit(1, f"ログアウトに失敗しました: {error}\n")
    elif args.command == "status":
        from src.auth import status_lines

        try:
            for line in status_lines():
                print(line)
        except (LoginError, OSError) as error:
            parser.exit(1, f"認証状態を確認できませんでした: {error}\n")
    elif args.command == "login":
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
