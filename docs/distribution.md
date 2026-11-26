# 開発環境と配布

## 現在の構成

ソース版ではChatGPTプランでの短文翻訳と、実論文の日本語PDF保存を確認済みです。v0.2.2はmacOS arm64・Linux x86_64向けに認証・モデル選択・PDF翻訳を配布します。Windows・Intel Macは対象外です。`ps`はmacOSの標準コマンドと衝突するため使いません。

```text
paper-shift/
├── .gitignore
├── pyproject.toml          # PythonパッケージとCLIの定義
├── uv.lock                 # uvの依存関係ロック
├── scripts/
│   ├── build-macos.sh      # macOS用の実行ファイルと配布アーカイブ
│   ├── install-macos.sh    # 実行ファイルの配置とzshのPATH設定
│   ├── uninstall-macos.sh  # macOS向けアンインストール
│   ├── install-online-macos.sh   # リリースアーカイブの取得・インストール
│   ├── build-linux.sh      # Linux x86_64用の実行ファイルと配布アーカイブ
│   ├── install-linux.sh / uninstall-linux.sh / install-online-linux.sh
│   ├── build-windows.ps1   # Windows用の実行ファイルと配布アーカイブ
│   ├── install-windows.ps1 # 実行ファイルの配置とユーザーPATH設定
│   ├── uninstall-windows.ps1 # Windows向けアンインストール
│   └── install-online-windows.ps1 # リリースZIPの取得とインストール
├── src/
│   ├── __init__.py
│   ├── __main__.py         # python -m src の起動口
│   ├── cli.py              # pshift コマンドの起動口
│   ├── auth.py             # ChatGPT認証フロー
│   ├── inference.py        # モデル選択と翻訳
│   └── pdf.py              # PDFの英文抽出と日本語配置
├── docs/
└── README.md
```

PDF抽出と生成はPyMuPDF、短文・本文ブロックの翻訳はResponses APIを使います。macOSとWindowsで同じコードが動くよう、ファイルパスには`pathlib`を使用します。

## ソースから起動する

[uv](https://docs.astral.sh/uv/getting-started/installation/)とPython 3.11以降を用意し、リポジトリのルートで実行します。macOSのターミナルとWindowsのPowerShellで同じコマンドです。

```sh
uv run pshift --help
uv run pshift --version
uv run pshift login
uv run pshift status
uv run pshift translate "The results were significant."
uv run pshift pdf paper.pdf -o paper-ja.pdf
uv run pshift model  # 必要ならモデルを変更
uv run pshift logout
```

`pshift login`は矢印キーとEnterでChatGPTブラウザ認証、headless端末への認証情報の取り込み、OpenAI Platform API keyを選べます。`--method browser`、`--method headless`、`--method api-key`でも指定できます。従来のURL手動表示は`--method manual`で利用できますが、headless認証とは異なります。`pshift status`は保存済みの認証状態、ChatGPTのメールアドレスとAPI keyの値を表示します。ネットワークへは接続せず、現在のトークンの有効性を保証するものではありません。API keyによる推論はChatGPTプランではなく従量課金です。

`pshift logout`は保存済みのChatGPT認証とAPI keyの両方をローカルから削除します。ChatGPTの更新トークンは公式の失効エンドポイントで失効を試みます。失効を確認できなかったときもローカルから削除し、メッセージを表示します。次回の認証に備えてクライアントIDとホストIDは保持します。API key自体をOpenAI Platformで無効化するわけではありません。

モデル未選択のまま`pshift translate "英文"`を実行すると、ログイン中のアカウントのモデル一覧の先頭をデフォルトとして保存し、Responses APIのストリームを完了まで読み取ります。`pshift model`はモデル一覧から矢印キーで選択し直せます。非対話環境では`pshift model --list`と`pshift model <slug>`を使います。ChatGPTプラン利用では`store: false`・`stream: true`を指定します。モデル一覧に出ることと、実際の推論が完了することは別です。

`pshift pdf paper.pdf -o paper-ja.pdf`は元ページ上の英文をブロック単位で抽出し、同じページの近い領域に日本語を置きます。複数ブロックをまとめて翻訳して推論回数を抑えます。出力先省略時は元ファイル名に`-ja`を付けます。出力先が既存なら失敗し、`--force`で上書きできます。ページ数・ページサイズを維持し、画像・線画と参考文献を残します。短すぎるヘッダー・脚注などは元のままです。長い訳文が収まらないときは不完全な出力ファイルを保存せずに終了します。現時点では図・数式を識別して除外する処理や、スキャンPDFのOCRはありません。

headless端末で`pshift login --method headless`を実行すると、手元の端末で認証して`credentials.json`のみを安全に転送する手順が表示されます。転送後は`pshift login --method headless --from-file <転送したファイル>`で取り込みます。headless端末のホストIDは維持されます。認証ファイルは秘密情報です。トークン更新処理は実装済みですが、実アカウントでの更新はまだ未検証です。

## macOS（arm64で動作確認済み）

PyInstallerでPython込みの単体実行ファイルを作ります。ビルドにはPythonとuvが必要です。

```sh
sh scripts/build-macos.sh
```

`dist/pshift-macos-arm64.tar.gz`が生成されます。手動配布の場合は利用者がアーカイブを展開し、そのフォルダで次を実行します。利用者にPython・uv・Gitは不要です。

```sh
sh install-macos.sh
```

`~/.local/bin/pshift`へ配置し、zshが使用する`.zprofile`（通常は`~/.zprofile`）へPATHを追加します。新しいターミナルで`pshift --help`が使えます。今のターミナルで使いたければ`source "${ZDOTDIR:-$HOME}/.zprofile"`で設定を読み直します。ChatGPTへのログインにはブラウザとインターネット接続が必要です。署名・公証によるOS警告の軽減は後の改善項目です。

アンインストールは`sh "$HOME/.local/share/papershift/uninstall-macos.sh"`です。インストーラーが追加したPATH行だけを`.zprofile`から削除します。新しいターミナルで変更が反映されます。

**一行インストール：**

```sh
curl -fsSL https://raw.githubusercontent.com/med-000/paper-shift/main/scripts/install-online-macos.sh | sh
```

オンラインスクリプトはデフォルトで[GitHub Releasesのlatest](https://github.com/med-000/paper-shift/releases/latest)からアーカイブを取得します。Intel Mac向けビルドはまだありません。ローカルで別の配布先を検証するときは`PAPERSHIFT_RELEASE_BASE_URL`で上書きできます。

## Linux（x86_64）

Linux x86_64環境で`binutils`とuvを用意して`sh scripts/build-linux.sh`を実行し、`pshift-linux-x86_64.tar.gz`を作成します。v0.2.2はDebian 12（glibc 2.36）コンテナでビルド・起動・インストール・削除を確認済みです。展開先で`sh install-linux.sh`、または`curl -fsSL https://raw.githubusercontent.com/med-000/paper-shift/main/scripts/install-online-linux.sh | sh`でインストールできます。`~/.local/bin`に配置し、`~/.profile`にPATHを追加します。削除は`sh "$HOME/.local/share/papershift/uninstall-linux.sh"`です。古いglibcの環境や別アーキテクチャは対象外です。

## Windows（配布対象外）

既存の`scripts/build-windows.ps1`などは技術検証用として残します。v0.2.2にはWindows用のアーカイブを添付せず、インストールURLも提供しません。

## 配布の完成条件

macOSとLinuxの実行ファイルとインストーラースクリプトを手元でビルド・検証した後、GitHub Releaseに手動で添付します。自動リリースは今後の課題です。実アカウントでのPDF翻訳はmacOSで確認済みであり、Linuxでも認証と翻訳の実地検証は今後の課題です。
