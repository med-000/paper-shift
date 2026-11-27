# PaperShift

- 英語論文PDFを日本語PDFに翻訳。ページ数・図・画像をできるだけ維持し、訳文は選択・検索できます。
- 文字を抽出できるPDFが対象。スキャンPDFのOCRには未対応です。

## 使い方

- **Agent Skill**：Claude Code / Codex自身が翻訳。[Skill](skills/paper-shift/SKILL.md)をインストールして使います。CLIのログインは不要です。
- **CLI**：`pshift`をインストールし、ChatGPTアカウントでログインして使います。
- **ローカルPlugin**：[Plugin ZIP](https://github.com/med-000/paper-shift/releases/download/v0.3.1/paper-shift-plugin.zip)をChatGPTに登録して使います。Web版で動作確認済み。[詳しい使い方](docs/usage.md)

## インストール

- **Agent Skill（Claude Code / Codex）**：Python 3.11以降が必要です。PDF処理の依存関係は[`requirements.txt`](skills/paper-shift/requirements.txt)に記載しています。Claude Codeでは`/paper-shift`、Codexでは`$paper-shift`で呼び出します。

  ```sh
  npx skills add med-000/paper-shift --skill paper-shift -g -a claude-code -a codex
  ```

- **CLI：macOS Apple Silicon**

  ```sh
  curl -fsSL https://raw.githubusercontent.com/med-000/paper-shift/main/scripts/install-online-macos.sh | sh
  ```

- **CLI：Linux x86_64**（Debian 12 / glibc 2.36でビルド）

  ```sh
  curl -fsSL https://raw.githubusercontent.com/med-000/paper-shift/main/scripts/install-online-linux.sh | sh
  ```

- **CLI：Windows / Intel Mac**：ビルド済み版は未配布。下記のソース版を使用してください。Windows版は検証段階です。
- **ローカルPlugin**：[v0.3.1 Release](https://github.com/med-000/paper-shift/releases/tag/v0.3.1)からZIPを取得し、ChatGPTのPlugin ZIPアップロード画面で登録。PDFを添付して翻訳を依頼します。

## CLIコマンド

```sh
pshift login                           # ChatGPTアカウントで認証
pshift pdf paper.pdf -o paper-ja.pdf   # PDF翻訳。-oは省略可、上書き時は--force
pshift translate "English text"        # 短文翻訳
pshift model                           # モデル選択（一覧は model --list）
pshift status                          # 認証状態を確認
pshift logout                          # 認証情報を削除
pshift login --method headless         # 別端末で認証する手順を表示
```

API key方式（`--method api-key`）はChatGPTプランとは別の従量課金です。

## 更新

- **CLI**：標準インストール版（macOS arm64 / Linux x86_64）で最新版を確認・更新。v0.3.0の配布版には未搭載のため、最初の更新は上記インストールコマンドを再実行してください。

  ```sh
  pshift update --check
  pshift update
  ```

- **Agent Skill**：GitHub上のSkillを再取得します。

  ```sh
  npx skills update paper-shift -g
  ```

- **ローカルPlugin**：新しい[Plugin ZIP](https://github.com/med-000/paper-shift/releases/latest)をダウンロードし、ChatGPTのPlugin詳細から **Upload new version** で更新します。
- **ソース版CLI**：リポジトリで更新します。配布版向けの`pshift update`は使用しません。

  ```sh
  git pull
  uv sync
  ```

## 開発環境から使う

- Python 3.11以降と[uv](https://docs.astral.sh/uv/getting-started/installation/)を用意します。
- CLIの実行、Plugin ZIP生成、テスト：

  ```sh
  uv run pshift login
  uv run pshift pdf paper.pdf -o paper-ja.pdf
  uv run python scripts/package-plugin.py  # dist/paper-shift-plugin.zip
  uv run python -m unittest discover -s tests -q
  ```

[更新方法・詳しい使い方と制限](docs/usage.md) · [トラブルシューティング](docs/troubleshooting.md) · [ライセンス](docs/licenses.md)
