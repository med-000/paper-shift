# PaperShift

英語論文PDFの本文を日本語に翻訳し、ページ数・図・画像をできるだけ保ったPDFを作ります。訳文は選択・検索できるテキストです。抽出可能な文字を含むPDFが対象で、スキャンPDFのOCRには対応していません。

## 使い方を選ぶ

- **Agent Skill（Claude Code / Codex）**: [`skills/paper-shift/`](skills/paper-shift/)をエージェントにインストール。エージェント自身が翻訳し、PDF処理には[v0.3.0のPlugin ZIP](https://github.com/med-000/paper-shift/releases/tag/v0.3.0)を使います。CLIへのログインは不要です。
- **CLI**: `pshift`で手元のPDFを翻訳。ChatGPTアカウントでログインして利用します。
- **ローカルPlugin（ChatGPT）**: [Plugin ZIP](https://github.com/med-000/paper-shift/releases/download/v0.3.0/paper-shift-plugin.zip)をChatGPTに登録し、PDFを添付して依頼します。ChatGPT本体が翻訳し、開発者側の翻訳用APIキーは不要です。[詳細](docs/plugin-mvp.md)。公開Pluginディレクトリへの掲載とは別です。

## インストール

### Agent Skill（macOS / Linux / Windows）

リポジトリの[`skills/paper-shift/`](skills/paper-shift/)フォルダを、Claude Codeなら`~/.claude/skills/paper-shift/`、Codexなら`~/.agents/skills/paper-shift/`へコピーします。必要なものはPython 3.11以降、PyMuPDF、初回実行時のGitHubへの接続です。Claude Codeでは`/paper-shift`、Codexでは`$paper-shift`で呼び出してください。詳細な手順は[SKILL.md](skills/paper-shift/SKILL.md)にあります。

### CLI（macOS Apple Silicon）

```sh
curl -fsSL https://raw.githubusercontent.com/med-000/paper-shift/main/scripts/install-online-macos.sh | sh
```

新しいターミナルで`pshift login`を実行します。削除する場合は`sh "$HOME/.local/share/papershift/uninstall-macos.sh"`を実行してください。

### CLI（Linux x86_64）

```sh
curl -fsSL https://raw.githubusercontent.com/med-000/paper-shift/main/scripts/install-online-linux.sh | sh
```

新しいログインシェルで`pshift login`を実行します。削除する場合は`sh "$HOME/.local/share/papershift/uninstall-linux.sh"`を実行してください。配布物はDebian 12（glibc 2.36）でビルドしており、古いglibc環境では動作しない場合があります。

### CLI（Windows / Intel Mac）

ビルド済みのCLIは未配布です。Python 3.11以降と[uv](https://docs.astral.sh/uv/getting-started/installation/)を用意し、下記のソース版を使用してください。Windowsのソース版は検証段階です。

### ローカルPlugin（ChatGPT Web）

[v0.3.0 Release](https://github.com/med-000/paper-shift/releases/tag/v0.3.0)から`paper-shift-plugin.zip`をダウンロードし、ChatGPTのPlugin ZIPアップロード画面で登録します。PDFを添付し、日本語PDFへの翻訳を依頼してください。Web版での登録・利用を確認済みです。

## CLIコマンド

```sh
pshift login                           # ChatGPTアカウントで認証
pshift pdf paper.pdf -o paper-ja.pdf   # 英語PDFを翻訳（出力先省略可）
pshift pdf paper.pdf --force           # 既存の出力PDFを上書き
pshift translate "The results were significant."
pshift model                           # モデルを選択
pshift model --list                    # 利用可能なモデルを表示
pshift status                          # 認証状態を確認
pshift logout                          # 認証情報を削除
```

headless端末では`pshift login --method headless`で転送手順を確認できます。`--method api-key`も選べますが、API keyはChatGPTプランとは別のOpenAI Platform従量課金です。

## 開発環境から使う

Python 3.11以降とuvを用意し、リポジトリのルートで実行します。

```sh
uv run pshift --version
uv run pshift login
uv run pshift pdf paper.pdf -o paper-ja.pdf
uv run python scripts/package-plugin.py  # dist/paper-shift-plugin.zipを生成
uv run python -m unittest discover -s tests -q
```

[仕様と制限](docs/feasibility.md) · [ビルドと配布](docs/distribution.md) · [ライセンス](LICENSE)（同梱フォントは[OFL](src/fonts/README.md)）
