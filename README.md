# PaperShift

**英語論文PDFを、日本語で読めるPDFに。** 元PDFのページ数・図・画像・線画をできるだけ保ちながら、抽出した英文を翻訳して同じページの近い位置に配置するオープンソースのCLIです。生成された日本語は画像ではなく、選択・検索できるPDFテキストです。

> **v0.2.2:** macOS Apple Silicon（arm64）・Linux x86_64向けに配布。Windows・Intel Mac用の実行ファイルはまだありません。テキストを抽出できるPDFが対象で、スキャンPDFのOCRには未対応です。

- [macOS](#macosapple-siliconで使う) · [Linux](#linux-x86_64で使う)
- [ソースからの実行](#ソースから使う)
- [仕組み・制限](#仕組みと現在の範囲)

## macOS（Apple Silicon）で使う

ターミナルでインストールします。Python・uv・Gitは不要です。

```sh
curl -fsSL https://raw.githubusercontent.com/med-000/paper-shift/main/scripts/install-online-macos.sh | sh
```

新しいターミナルを開き、ChatGPTアカウントで認証してPDFを翻訳します。

```sh
pshift login                         # 矢印キーでChatGPT Pro/Plus (browser)を選択
pshift pdf paper.pdf -o paper-ja.pdf  # 英語PDF → 日本語PDF
```

初回はブラウザで認証と許可を行います。モデルを選んでいなければ、アカウントのモデル一覧の先頭を自動で保存します。入力はローカルのPDFファイルです。出力先`-o`を省くと元のファイル名に`-ja`を付けます。既存の出力を上書きするときだけ`--force`を付けてください。長い論文はモデルへの複数回の問い合わせが必要なため、処理に時間がかかることがあります。

```sh
pshift status                         # 保存済みの認証方式を確認
pshift model                          # 利用するモデルを選択
pshift model --list                   # モデル一覧を表示
pshift translate "The results were significant."  # 短文の翻訳
pshift pdf --help                     # PDFコマンドのオプション
pshift logout                        # ローカルの認証情報を削除
```

アンインストールは`sh "$HOME/.local/share/papershift/uninstall-macos.sh"`で行えます。

## Linux (x86_64) で使う

Python・uv・Gitは不要です。ターミナルでインストールし、新しいログインシェルを開いてからログイン・翻訳してください。

```sh
curl -fsSL https://raw.githubusercontent.com/med-000/paper-shift/main/scripts/install-online-linux.sh | sh
```

```sh
pshift login
pshift pdf paper.pdf -o paper-ja.pdf
```

現在のシェルでPATHを読み直す場合は`. "$HOME/.profile"`、アンインストールは`sh "$HOME/.local/share/papershift/uninstall-linux.sh"`です。配布バイナリはDebian 12（glibc 2.36）環境でビルドしています。古いglibcのディストリビューションでは動作しない場合があります。

## ソースから使う

macOS・Linuxでは、Python 3.11以降と[uv](https://docs.astral.sh/uv/getting-started/installation/)を用意して、リポジトリのルートから実行できます。Windowsはソース版の検証段階で、v0.2.2の配布対象ではありません。

```sh
uv run pshift login
uv run pshift pdf paper.pdf -o paper-ja.pdf
```

headless端末では、ブラウザがある端末で認証した後、保護した認証ファイルを転送して`pshift login --method headless --from-file <ファイル>`で取り込みます。`pshift login --method api-key`も選べますが、**API keyはChatGPTプランとは別のOpenAI Platform従量課金**です。自動でAPI key方式へ切り替えることはありません。

## 仕組みと現在の範囲

1. PyMuPDFでPDFの英文ブロックと座標・文字サイズ・太さを取得する。
2. 対象テキストを複数ブロックずつ、ログイン中のアカウントで翻訳する。PDFファイル全体は送信しない。
3. 元ページ上の英文を取り除き、同梱のNoto Sans JP / Noto Serif JPで日本語を配置して保存する。

ページ数・ページサイズを保ち、画像と線画は元ページに残します。長い訳文が収まらないブロックは必要に応じて縮小します。参考文献の見出しを検出した場合、その後のページを含め原文のまま残します（参考文献以外の後続セクションも翻訳されません）。著者・所属、投稿情報、小さなヘッダー・脚注などは原文のまま残る場合があります。図中の文字や数式の判定、複雑な段組みの精密な再現、スキャンPDFのOCRにはまだ対応していません。訳文が収まらない場合は不完全なPDFを保存せずに終了します。

認証ファイルはリポジトリ外の`~/.config/papershift/`（macOS・Linux）または`%LOCALAPPDATA%\PaperShift\`（Windows）に保存します。`pshift status`は保存済みの認証状態を表示しますが、現在のトークンの有効性は保証しません。

## 開発・ライセンス

- [技術方針](docs/overview.md) · [検証事項と制限](docs/feasibility.md) · [ロードマップ](docs/roadmap.md) · [ビルド・配布](docs/distribution.md)
- `plugin`ブランチで開発中の[ChatGPT Skills-only Plugin MVP](docs/plugin-mvp.md)は、ローカルのZIP生成・PDF再構築まで検証済みです。ChatGPT上での動作と一般公開は未検証です。
- ソースコード: [GNU AGPLv3](LICENSE)。同梱のNotoフォントにはそれぞれの[SIL Open Font License](src/fonts/README.md)が適用されます。
- v0.1.0はCLIの起動確認用の旧リリースです。PDF翻訳はv0.2.0以降を使用してください。
