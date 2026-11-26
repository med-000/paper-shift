# 開発環境と配布

## 現在の構成

ソース版には`pshift login`の認証フローがありますが、実アカウントによるログイン成功は未検証です。公開済みのv0.1.0実行ファイルは`--help`と`--version`のみで、PDF翻訳はまだ動きません。`ps`はmacOSの標準コマンドと衝突するため使いません。

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
│   ├── build-windows.ps1   # Windows用の実行ファイルと配布アーカイブ
│   ├── install-windows.ps1 # 実行ファイルの配置とユーザーPATH設定
│   ├── uninstall-windows.ps1 # Windows向けアンインストール
│   └── install-online-windows.ps1 # 技術検証用オンライン取得
├── src/
│   ├── __init__.py
│   ├── __main__.py         # python -m src の起動口
│   ├── cli.py              # pshift コマンドの起動口
│   └── auth.py             # ChatGPT認証フロー
├── docs/
└── README.md
```

認証、PDF抽出、翻訳、PDF生成は技術検証後に`src/`へ追加します。先に空のモジュールや汎用インターフェースは作りません。macOSとWindowsで同じコードが動くよう、ファイルパスには`pathlib`を使用します。

## ソースから起動する

[uv](https://docs.astral.sh/uv/getting-started/installation/)とPython 3.11以降を用意し、リポジトリのルートで実行します。macOSのターミナルとWindowsのPowerShellで同じコマンドです。

```sh
uv run pshift --help
uv run pshift --version
uv run pshift login
uv run pshift status
uv run pshift translate "The results were significant."
uv run pshift model  # 必要ならモデルを変更
uv run pshift logout
```

`pshift login`は矢印キーとEnterでChatGPTブラウザ認証、headless端末への認証情報の取り込み、OpenAI Platform API keyを選べます。`--method browser`、`--method headless`、`--method api-key`でも指定できます。従来のURL手動表示は`--method manual`で利用できますが、headless認証とは異なります。`pshift status`は保存済みの認証状態、ChatGPTのメールアドレスとAPI keyの値を表示します。ネットワークへは接続せず、現在のトークンの有効性を保証するものではありません。API keyによる推論はChatGPTプランではなく従量課金です。

`pshift logout`は保存済みのChatGPT認証とAPI keyの両方をローカルから削除します。ChatGPTの更新トークンは公式の失効エンドポイントで失効を試みます。失効を確認できなかったときもローカルから削除し、メッセージを表示します。次回の認証に備えてクライアントIDとホストIDは保持します。API key自体をOpenAI Platformで無効化するわけではありません。

モデル未選択のまま`pshift translate "英文"`を実行すると、ログイン中のアカウントのモデル一覧の先頭をデフォルトとして保存し、Responses APIのストリームを完了まで読み取ります。`pshift model`はモデル一覧から矢印キーで選択し直せます。非対話環境では`pshift model --list`と`pshift model <slug>`を使います。ChatGPTプラン利用では`store: false`・`stream: true`を指定します。モデル一覧に出ることと、実際の推論が完了することは別です。

headless端末で`pshift login --method headless`を実行すると、手元の端末で認証して`credentials.json`のみを安全に転送する手順が表示されます。転送後は`pshift login --method headless --from-file <転送したファイル>`で取り込みます。headless端末のホストIDは維持されます。認証ファイルは秘密情報です。認証情報の自動更新は未実装のため、アクセストークンの期限後は再取得が必要です。

## macOS（arm64で動作確認済み）

PyInstallerでPython込みの単体実行ファイルを作ります。ビルドにはPythonとuvが必要です。

```sh
sh scripts/build-macos.sh
```

`dist/pshift-macos-<arch>.tar.gz`が生成されます。ソース版からビルドしたアーカイブには`login`が入りますが、実アカウントでの認証は未検証です。GitHub Releaseに添付済みのv0.1.0アーカイブは以前のビルドで、`login`を含みません。手動配布の場合は利用者がアーカイブを展開し、そのフォルダで次を実行します。利用者にPython・uv・Gitは不要です。

```sh
sh install-macos.sh
```

`~/.local/bin/pshift`へ配置し、zshが使用する`.zprofile`（通常は`~/.zprofile`）へPATHを追加します。新しいターミナルで`pshift --help`が使えます。今のターミナルで使いたければ`source "${ZDOTDIR:-$HOME}/.zprofile"`で設定を読み直します。ChatGPTへのログインにはブラウザとインターネット接続が必要です。署名・公証によるOS警告の軽減は後の改善項目です。

アンインストールは`sh "$HOME/.local/share/papershift/uninstall-macos.sh"`です。インストーラーが追加したPATH行だけを`.zprofile`から削除します。新しいターミナルで変更が反映されます。

**GitHub公開後の一行インストール案：**

```sh
curl -fsSL https://raw.githubusercontent.com/med-000/paper-shift/main/scripts/install-online-macos.sh | sh
```

オンラインスクリプトはデフォルトで[GitHub Releasesのlatest](https://github.com/med-000/paper-shift/releases/latest)から`pshift-macos-<arch>.tar.gz`を取得します。**v0.1.0のmacOS arm64版は公開済み**で、一行インストール・起動・アンインストールを確認しました。ただし翻訳機能は未実装です。Intel Mac向けビルドはまだありません。ローカルで別の配布先を検証するときは`PAPERSHIFT_RELEASE_BASE_URL`で上書きできます。Homebrew対応は後から追加します。

## Windows（未検証）

現時点の検証用PowerShellスクリプトでは、開発側が`scripts/build-windows.ps1`を実行してアーカイブを作り、利用者が展開先で`.\install-windows.ps1`を実行する想定です。ユーザーのアプリ用フォルダに`pshift.exe`をコピーし、ユーザーPATHと現在のPowerShellのPATHを設定します。PowerShellの実行ポリシーによる制限を含め、Windows実機での確認が必要です。

この検証用インストールのアンインストールコマンドは`& "$env:LOCALAPPDATA\Programs\PaperShift\uninstall-windows.ps1"`です。インストーラーが追加した場合にだけユーザーPATHから削除します。Windows実機での動作確認はまだ行っていません。

一般向けには、**cmdの`curl.exe`でダウンロードして起動できる`.exe`インストーラー**を用意する方針です。PATH設定までインストーラーで行います。現在のPowerShellスクリプト（`install-online-windows.ps1`を含む）は技術検証用で、`.exe`インストーラーは未実装です。

## 配布の完成条件

Windows/macOSのクリーン環境でPython・uv・Gitを別途インストールせず`pshift`を起動できること。実際の翻訳・PDF出力と合わせて確認します。GitHubにソースを公開するだけでは、配布用のビルドやインストールURLは完成しません。
