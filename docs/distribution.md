# 開発環境と配布

## 現在の構成

現在はCLIの起動口のみ実装しています。`pshift --help`と`pshift --version`が使えますが、PDF翻訳はまだ動きません。`ps`はmacOSの標準コマンドと衝突するため使いません。

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
│   └── cli.py              # pshift コマンドの起動口
├── docs/
└── README.md
```

認証、PDF抽出、翻訳、PDF生成は技術検証後に`src/`へ追加します。先に空のモジュールや汎用インターフェースは作りません。macOSとWindowsで同じコードが動くよう、ファイルパスには`pathlib`を使用します。

## ソースから起動する

[uv](https://docs.astral.sh/uv/getting-started/installation/)とPython 3.11以降を用意し、リポジトリのルートで実行します。macOSのターミナルとWindowsのPowerShellで同じコマンドです。

```sh
uv run pshift --help
uv run pshift --version
```

## macOS（arm64で動作確認済み）

PyInstallerでPython込みの単体実行ファイルを作ります。ビルドにはPythonとuvが必要です。

```sh
sh scripts/build-macos.sh
```

`dist/pshift-macos-<arch>.tar.gz`が生成されます。手動配布の場合は利用者がアーカイブを展開し、そのフォルダで次を実行します。利用者にPython・uv・Gitは不要です。

```sh
sh install-macos.sh
```

`~/.local/bin/pshift`へ配置し、zshが使用する`.zprofile`（通常は`~/.zprofile`）へPATHを追加します。新しいターミナルで`pshift --help`が使えます。今のターミナルで使いたければ`source "${ZDOTDIR:-$HOME}/.zprofile"`で設定を読み直します。ChatGPTへのログインにはブラウザとインターネット接続が必要です。署名・公証によるOS警告の軽減は後の改善項目です。

アンインストールは`sh "$HOME/.local/share/papershift/uninstall-macos.sh"`です。インストーラーが追加したPATH行だけを`.zprofile`から削除します。新しいターミナルで変更が反映されます。

**GitHub公開後の一行インストール案：**

```sh
curl -fsSL https://raw.githubusercontent.com/med-000/paper-shift/main/scripts/install-online-macos.sh | sh
```

オンラインスクリプトはデフォルトで[GitHub Releasesのlatest](https://github.com/med-000/paper-shift/releases/latest)から`pshift-macos-<arch>.tar.gz`を取得します。**リリースアーカイブは未公開**なので、現時点ではこのコマンドでインストールできません。macOS arm64以外のビルドもまだありません。ローカルで別の配布先を検証するときは`PAPERSHIFT_RELEASE_BASE_URL`で上書きできます。Homebrew対応は後から追加します。

## Windows（未検証）

現時点の検証用PowerShellスクリプトでは、開発側が`scripts/build-windows.ps1`を実行してアーカイブを作り、利用者が展開先で`.\install-windows.ps1`を実行する想定です。ユーザーのアプリ用フォルダに`pshift.exe`をコピーし、ユーザーPATHと現在のPowerShellのPATHを設定します。PowerShellの実行ポリシーによる制限を含め、Windows実機での確認が必要です。

この検証用インストールのアンインストールコマンドは`& "$env:LOCALAPPDATA\Programs\PaperShift\uninstall-windows.ps1"`です。インストーラーが追加した場合にだけユーザーPATHから削除します。Windows実機での動作確認はまだ行っていません。

一般向けには、**cmdの`curl.exe`でダウンロードして起動できる`.exe`インストーラー**を用意する方針です。PATH設定までインストーラーで行います。現在のPowerShellスクリプト（`install-online-windows.ps1`を含む）は技術検証用で、`.exe`インストーラーは未実装です。

## 配布の完成条件

Windows/macOSのクリーン環境でPython・uv・Gitを別途インストールせず`pshift`を起動できること。実際の翻訳・PDF出力と合わせて確認します。GitHubにソースを公開するだけでは、配布用のビルドやインストールURLは完成しません。
