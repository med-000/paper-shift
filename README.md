# PaperShift

英語論文などのPDFを、図・表・数式をできるだけ残しながら日本語版PDFにするオープンソースのCLIツールです。まずはmacOS・Windowsでのローカル実行を目指します。

> **開発初期段階：** ソース版で認証、モデル選択、短文翻訳を試せます。実際のChatGPTアカウントでの推論はまだ未検証です。公開中のv0.1.0実行ファイルには未収録で、PDF翻訳とWindows向け配布も未実装です。

## 開発環境から起動

Python 3.11以降と[uv](https://docs.astral.sh/uv/getting-started/installation/)を用意し、リポジトリのルートで実行します。

```sh
uv run pshift --help
uv run pshift login
uv run pshift status
uv run pshift model
uv run pshift translate "The results were significant."
uv run pshift logout
uv run pshift login --method headless
uv run pshift login --method api-key
```

対話式で矢印キーとEnterを使い、ChatGPTのブラウザ認証、headless端末への認証情報の取り込み、OpenAI Platform API keyを選べます。`--method browser`、`--method headless`、`--method api-key`で直接指定できます。`pshift status`では現在の方式、保存済みのChatGPTメールアドレスとAPI keyの値を表示します（OAuthトークンは表示しません）。headless方式は手元の端末でブラウザ認証した後、安全に転送した`credentials.json`を`--from-file`で取り込みます。ワンタイムコード方式ではありません。API keyは**ChatGPTプランの対象外で、利用時には別途従量課金**です。

`pshift logout`はChatGPTの更新トークン失効を試み、保存済みのChatGPTトークンとAPI keyを端末から削除します。ネットワークエラーで失効を確認できなかった場合もローカルからは削除し、その結果を表示します。API key自体をOpenAI Platformで無効化する操作は含みません。

`pshift model`はログイン中のアカウントのモデル一覧から選びます。ターミナルで選択できない場合は`pshift model --list`で一覧を見て`pshift model <slug>`で指定してください。モデル一覧への表示だけでは利用可能とは限らず、`pshift translate "英文"`が完了したときに推論を確認できます。API keyでの翻訳はChatGPTプラン外の従量課金です。

ChatGPTへのログインはブラウザで本人が許可する必要があります。認証情報はリポジトリ外（macOSでは`~/.config/papershift/`、Windowsでは`%LOCALAPPDATA%\PaperShift\`）に保存します。API keyは別ファイルに保存し、最後に成功した方式を記録します。実アカウントによる翻訳完了の確認はこれからです。

## ドキュメント

- [プロダクト概要・技術スタック・MVP条件](docs/overview.md)
- [技術的な懸念と公式資料](docs/feasibility.md)
- [開発ロードマップ](docs/roadmap.md)
- [ビルド・インストール・配布](docs/distribution.md)
