# Skills-only Plugin MVP

CLIは引き続き`uv run pshift`で使用できる。Pluginは別の認証フローや開発者用AI APIキーを使わず、ChatGPT本体が翻訳した文字列を受け取り、既存のPDF処理コードで日本語PDFを生成する。Web版ChatGPTへのZIP登録と使用は利用者が確認済み。公開ディレクトリへの提出・審査はまだ行っていない。

## パッケージと操作

```sh
uv run python scripts/package-plugin.py
```

Pluginのソースは`plugins/plugin.json`、`plugins/skills/translate-paper/SKILL.md`、`plugins/scripts/pdf_bridge.py`に置く。`dist/paper-shift-plugin.zip`にはこれらとCLIの`src/pdf.py`・同梱フォントを`paper-shift/`ディレクトリにまとめる。Pluginを再ビルドすれば`src/pdf.py`とフォントの最新版を取り込む。GitHub ReleaseへのZIP添付は、公開Pluginディレクトリへの申請とは別。

スキルの処理手順:

1. `python <plugin-root>/scripts/pdf_bridge.py extract <source.pdf> <manifest.json>`でページ番号・原文断片・バッチIDをJSONとして書き出す。参考文献は対象外。PDF本体はモデルへのテキスト入力にしない。
2. ChatGPT本体が各バッチの`texts`を同じ順序・件数の日本語に訳し、`{"batches":[{"id":"...","translations":["...", ...]}]}`の形式で保存する。実装スクリプトは翻訳APIを呼ばない。
3. `python <plugin-root>/scripts/pdf_bridge.py render <source.pdf> <manifest.json> <translations.json> <output.pdf>`で原PDFのSHA-256・原文バッチと訳文ID/件数/内容を検証し、既存の`translate_pdf`でレイアウト・ページ寸法を維持して出力する。ページ・バッチIDを渡すので、同一英文が複数ページにあっても訳文を取り違えない。欠落・重複・不一致時はPDFを作成しない。

`src/pdf.py`からページ・バッチの選択処理を共有しているため、CLIとPluginの翻訳対象は同じ。翻訳用のResponses API呼び出し・OAuth情報はZIPに入れない。フォント3個を含むため、ZIPの容量と依存関係の可否はChatGPT上で確認する。

## ローカルで確認済み

- `uv run python -m unittest discover -s tests -q`：33件成功。ZIPを展開した状態で2ページのPDFを抽出・訳文注入・再構築し、同じ英文が2ページにある場合の訳文の対応、欠落した訳文・変更された原本の拒否を確認した。
- 既存の11ページ実論文をZIP内のスクリプトで抽出：24バッチ、参考文献の原文は翻訳依頼に含まれず、最後の翻訳対象は10ページ目。

## 公開ディレクトリでの未検証事項

- 対象プランや他の利用者の環境でも同梱Pythonスクリプト・PyMuPDF・フォントを実行できること。
- 11ページ論文の24バッチを欠落なく訳し、生成PDFをダウンロードできること。長文・途中停止・再開も確認する。
- ZIPのメタデータ・アイコン・サポート/プライバシー情報の審査要件を満たし、開発者の本人確認後に一般公開できること。現段階では申請・公開しない。

ChatGPT環境の検証でSkills-onlyが必要な機能を満たせない場合にのみRemote MCPを検討する。ローカル実行限定なら`requires_local_executor`でDesktop onlyとして公開可能だが、Web/モバイルに提供する要件を満たすか先に判断する。
