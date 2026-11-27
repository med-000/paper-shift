# PaperShift

- 英語論文PDFを日本語PDFに翻訳。ページ数・図・画像をできるだけ維持し、訳文は選択・検索できます。
- 文字を抽出できるPDFが対象。スキャンPDFのOCRには未対応です。

## 使い方

- **Agent Skill**：Claude Code / Codex自身が翻訳。[Skill](skills/paper-shift/SKILL.md)をインストールして使います。CLIのログインは不要です。
- **CLI**：`pshift`をインストールし、ChatGPTアカウントでログインして使います。
- **ローカルPlugin**：[Plugin ZIP](https://github.com/med-000/paper-shift/releases/download/v0.3.0/paper-shift-plugin.zip)をChatGPTに登録して使います。Web版で動作確認済み。[詳細](docs/plugin-mvp.md)

## インストール

- **Agent Skill（Claude Code / Codex）**：`npx skills add med-000/paper-shift --skill paper-shift -g -a claude-code -a codex`。Python 3.11以降とPyMuPDFが必要です。Claude Codeでは`/paper-shift`、Codexでは`$paper-shift`で呼び出します。
- **CLI：macOS Apple Silicon**：`curl -fsSL https://raw.githubusercontent.com/med-000/paper-shift/main/scripts/install-online-macos.sh | sh`
- **CLI：Linux x86_64**：`curl -fsSL https://raw.githubusercontent.com/med-000/paper-shift/main/scripts/install-online-linux.sh | sh`（Debian 12 / glibc 2.36でビルド）
- **CLI：Windows / Intel Mac**：ビルド済み版は未配布。下記のソース版を使用してください。Windows版は検証段階です。
- **ローカルPlugin**：[v0.3.0 Release](https://github.com/med-000/paper-shift/releases/tag/v0.3.0)からZIPを取得し、ChatGPTのPlugin ZIPアップロード画面で登録。PDFを添付して翻訳を依頼します。

## CLIコマンド

- `pshift login`：ChatGPTアカウントで認証
- `pshift pdf paper.pdf -o paper-ja.pdf`：PDF翻訳（`-o`は省略可、上書き時は`--force`）
- `pshift translate "English text"`：短文翻訳
- `pshift model` / `pshift model --list`：モデル選択・一覧
- `pshift status` / `pshift logout`：認証状態の確認・削除

headless認証には`pshift login --method headless`を使用します。`--method api-key`はChatGPTプランとは別の従量課金です。

## 開発環境から使う

- Python 3.11以降と[uv](https://docs.astral.sh/uv/getting-started/installation/)を用意します。
- CLI：`uv run pshift login` → `uv run pshift pdf paper.pdf -o paper-ja.pdf`
- Plugin ZIP生成：`uv run python scripts/package-plugin.py`（出力先：`dist/paper-shift-plugin.zip`）
- テスト：`uv run python -m unittest discover -s tests -q`

[仕様と制限](docs/feasibility.md) · [配布の詳細](docs/distribution.md) · [ライセンス](LICENSE)（フォントは[OFL](src/fonts/README.md)）
