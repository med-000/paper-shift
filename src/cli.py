"""Command-line entry point for PaperShift."""

import argparse
from importlib.metadata import version
from pathlib import Path
import sys

import questionary

from src.auth import LoginError, import_headless, login, login_api_key, logout
from src.inference import InferenceError, list_models, select_model, selected_model, translate, translate_many
from src.auth import active_credential
from src.pdf import PdfError, translate_pdf
from src.update import UpdateError, update


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


def _choose_model(models: list[tuple[str, str]], current: str | None) -> str | None:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return None
    choices = [questionary.Choice(f"{name} ({slug})" if name != slug else slug, value=slug) for slug, name in models]
    return questionary.select(
        "モデルを選択してください（↑↓、Enter。検索は入力で絞り込み）",
        choices=choices, default=current if current in {slug for slug, _ in models} else None,
        use_search_filter=True, use_shortcuts=False, use_jk_keys=False,
    ).ask()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pshift",
        description="英語論文PDFを日本語PDFに翻訳するツール",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {version('paper-shift')}",
    )
    subcommands = parser.add_subparsers(dest="command")
    subcommands.add_parser("status", help="保存済みの認証状態を表示")
    subcommands.add_parser("logout", help="保存済みの認証情報を削除")
    update_parser = subcommands.add_parser("update", help="CLIを最新のGitHub Releaseに更新")
    update_parser.add_argument("--check", action="store_true", help="更新の有無だけ確認")
    model_parser = subcommands.add_parser("model", help="利用可能なモデルを選択")
    model_parser.add_argument("slug", nargs="?", help="対話操作せずモデル名で選択")
    model_parser.add_argument("--list", action="store_true", help="モデル一覧を表示")
    translate_parser = subcommands.add_parser("translate", help="短い英文を日本語に翻訳")
    translate_parser.add_argument("text", help="翻訳する英文（最大4000文字）")
    pdf_parser = subcommands.add_parser("pdf", help="英語PDFを日本語PDFに翻訳して保存")
    pdf_parser.add_argument("source", type=Path, help="元の英語PDF")
    pdf_parser.add_argument("-o", "--output", type=Path, help="出力先（省略時は元ファイル名-ja.pdf）")
    pdf_parser.add_argument("--force", action="store_true", help="既存の出力先を上書き")
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
    if args.command == "pdf":
        try:
            method, credential = active_credential()
            model = selected_model(method, credential)
            if not model:
                model = list_models(method, credential)[0][0]
                select_model(method, credential, model)
                print(f"デフォルトモデル: {model}", file=sys.stderr)

            def translate_blocks(texts: list[str]) -> list[str]:
                current_method, current_credential = active_credential()
                if current_method != method:
                    raise PdfError("処理中にログイン方式が変更されました。")
                return translate_many(current_method, current_credential, model, texts)

            destination = args.output or args.source.with_name(f"{args.source.stem}-ja.pdf")
            pages, blocks = translate_pdf(
                args.source, destination, translate_blocks, force=args.force,
                progress=lambda current, total: print(f"PDF翻訳: {current}/{total}ページ", file=sys.stderr),
            )
            print(f"保存しました: {destination}（{pages}ページ・{blocks}テキスト領域）")
        except KeyboardInterrupt:
            parser.exit(130, "\nPDF翻訳を中断しました。\n")
        except (PdfError, LoginError, InferenceError, OSError) as error:
            parser.exit(1, f"PDF翻訳に失敗しました: {error}\n")
    elif args.command == "model":
        try:
            method, credential = active_credential()
            models = list_models(method, credential)
            current = selected_model(method, credential)
            if args.slug:
                if args.slug not in {slug for slug, _ in models}:
                    raise InferenceError("指定したモデルはこのアカウントの一覧にありません。pshift model --listで確認してください。")
                choice = args.slug
            elif args.list or not (sys.stdin.isatty() and sys.stdout.isatty()):
                for slug, name in models:
                    marker = "*" if slug == current else " "
                    print(f"{marker} {name} ({slug})" if name != slug else f"{marker} {slug}")
                if not args.list:
                    print("モデルを選ぶには `pshift model <モデル名>` を実行してください。")
                return
            else:
                choice = _choose_model(models, current)
                if choice is None:
                    return
            select_model(method, credential, choice)
            print(f"選択中のモデル: {choice}")
        except KeyboardInterrupt:
            parser.exit(130, "\nモデル選択を中断しました。\n")
        except (LoginError, InferenceError, OSError) as error:
            parser.exit(1, f"モデル選択に失敗しました: {error}\n")
    elif args.command == "translate":
        try:
            method, credential = active_credential()
            model = selected_model(method, credential)
            if not model:
                models = list_models(method, credential)
                model = models[0][0]
                select_model(method, credential, model)
                print(f"デフォルトモデル: {model}", file=sys.stderr)
            print(translate(method, credential, model, args.text))
        except KeyboardInterrupt:
            parser.exit(130, "\n翻訳を中断しました。\n")
        except (LoginError, InferenceError, OSError) as error:
            parser.exit(1, f"翻訳に失敗しました: {error}\n")
    elif args.command == "logout":
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
    elif args.command == "update":
        try:
            print(update(check=args.check))
        except KeyboardInterrupt:
            parser.exit(130, "\n更新を中断しました。\n")
        except UpdateError as error:
            parser.exit(1, f"更新に失敗しました: {error}\n")
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
