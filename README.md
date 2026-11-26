# PaperShift

英語論文などのPDFを、図・表・数式をできるだけ残しながら日本語版PDFにするオープンソースのCLIツールです。まずはmacOS・Windowsでのローカル実行を目指します。

> **開発初期段階：** 現在は`pshift --help`と`--version`のみ動作します。ChatGPT認証、PDF翻訳、Windows向け配布は未実装です。

## 開発環境から起動

Python 3.11以降と[uv](https://docs.astral.sh/uv/getting-started/installation/)を用意し、リポジトリのルートで実行します。

```sh
uv run pshift --help
```

## ドキュメント

- [プロダクト概要・技術スタック・MVP条件](docs/overview.md)
- [技術的な懸念と公式資料](docs/feasibility.md)
- [開発ロードマップ](docs/roadmap.md)
- [ビルド・インストール・配布](docs/distribution.md)
