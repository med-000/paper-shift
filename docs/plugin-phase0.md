# ChatGPT Plugin Phase 0 — 技術調査

調査日: 2026-11-27。対象は既存CLIを残したまま、利用者がChatGPTにPDFを渡し、ChatGPT本体で翻訳して日本語PDFを受け取る方式。**この文書はPhase 0の仕様調査時点の記録であり、ChatGPT上で動作するPluginの実証ではない。** 後続のローカル実装と検証結果は[Plugin MVP](plugin-mvp.md)に記載する。

## 暫定判断

**Skills-only Pluginを第一候補として維持する。ただし採用確定は保留。** 公式資料に、スキル単独のPlugin、スクリプト等の同梱、ChatGPT Workによるコード実行・PDF入出力、一般向けPlugin Directoryへの提出経路がある。一方、スキルのPythonスクリプトにPyMuPDFと同梱フォントを読み込ませ、モデルが翻訳した大量のテキストを欠落なく渡して複数ページのPDFを完了できることは、この調査だけでは証明できない。特にChatGPT Chatのデータ分析環境、Work Cloud、Work Localは**別の実行環境**であり、どれか一つの説明から全環境での動作を推定しない。

Remote MCPは現時点で着手しない。下記の実機判定でSkills-onlyが必要な入出力・実行・品質・公開条件を満たせないと判明した場合にのみ検討する。Skills-onlyでも「ローカル実行限定」ならサーバー不要だが、ユーザーはデスクトップアプリとローカル実行が必要となり、Web/モバイルからは利用できない。その制約を許容できるかは別途判断する。

## 要件ごとの根拠と未確認事項

1. **Plugin仕様・一般公開: 仕様上可能。** Pluginは`plugin.json`、`skills/<name>/SKILL.md`、任意のスクリプト・アセットで構成でき、MCPを含まないSkills-onlyでも公開DirectoryへZIPを提出できる。提出には開発者の本人/組織確認と審査が必要。Skills-onlyの公開でも一覧メタデータと適用されるプライバシー要件を満たす必要がある。個人のChatGPT Plus/Proアカウントだけで作成・提出できるか、利用者のプランと地域で利用できるかは未確認。[[1]](#sources) [[2]](#sources) [[3]](#sources) [[4]](#sources)
2. **Python・PyMuPDF・日本語フォント: ローカルでは再利用可能、Plugin実行環境では未検証。** スキルには`scripts/`と`assets/`を含められる。ChatGPT Workはコードとシェルを実行できるが、利用可能なPython・依存パッケージ・ネットワーク・ファイルパスは選択したCloud/Local環境や権限による。PyMuPDFがプリインストールされる保証、`pip install`の可否、フォントを含むPlugin ZIPの許容容量を公式Plugin資料では確認できなかった。リポジトリの3フォントは約18.7 MiB（未圧縮）。APIの「Skills」機能の容量制限をChatGPT Pluginの制限として流用しない。[[1]](#sources) [[5]](#sources) [[6]](#sources)
3. **PDFアップロード・ダウンロード: ChatGPTの機能として可能、スキルからの参照は要検証。** ChatGPTはPDFを添付でき、Workは完成したPDFを作成・ダウンロードできる。文書アップロード上限は原則512 MB/ファイルだが、プラン・モデル・ワークスペース等で利用可否や実用上の制限が異なる。添付PDFがスキルのスクリプトから読めるパスで提供されるか、生成PDFのリンクを返せるかは実機確認が必要。[[5]](#sources) [[7]](#sources) [[8]](#sources)
4. **モデル翻訳とスクリプトの連携: 方式は設計可能、長文の実証なし。** 既存`src/pdf.py::translate_pdf`は原文の断片を`translate_texts(list[str]) -> list[str]`へ渡し、戻り値の件数・空文字を検査する。Skills版ではモデルが順序付きのID付きJSONとして訳文を作り、Python側がID・件数・長さを検証してPDFへ配置する構想。現在の関数はPythonコールバック内で翻訳を要求するため、ChatGPT本体を使うには「抽出 → モデル翻訳 → 注入して再構築」に処理境界を分ける必要がある。CLIの`src/inference.py`のResponses API呼び出しをスキルへ持ち込むとAPI/認証経路の要件から外れる。ChatGPTのデータ分析Python環境は外部API呼び出し不可。[[6]](#sources)
5. **複数ページ・参考文献: CLIでは実例あり、Pluginでは未実証。** 11ページ/60テキスト領域のPDF出力と参考文献の原文維持をCLIで確認済み（ローカル`test/`内の実PDF）。今回のローカル確認でもPyMuPDF 1.28.2で11ページの原本から最初のページの6領域を抽出でき、同梱の3フォントを読み込めた。これはPluginのモデル実行時間・文脈長・セッション持続性の保証にはならない。ChatGPT側で長文が一度に処理されず、途中で切れる場合はページ単位の再開と結果の永続化が必要。現状のCLIは参考文献開始以降のページを翻訳しないことも品質比較に含める。[[7]](#sources)
6. **公開範囲と費用: 条件付き。** Plugin Directoryは広く提供されるが、個別PluginとSkillsの使用可能なプラン・地域・ワークスペース設定は異なる。個人向けSkillsの案内は主にBusiness/Enterprise/Healthcare/Eduを対象としており、Plus/Proの一般利用者がSkills-only Pluginを使えるかは特に検証が必要。ChatGPTのモデルが翻訳するSkills-only方式なら開発者が翻訳用APIキーを同梱する必要はない。ただし利用者側のChatGPT/Work利用枠・実行環境の制約は残る。デスクトップのみのスキルには`requires_local_executor: true`があり、公開手順もある（ローカルMCPの承認制と混同しない）。Remote MCPなら公開用の安定したHTTPSエンドポイントと運用費が必要。[[3]](#sources) [[4]](#sources) [[9]](#sources) [[10]](#sources) [[11]](#sources)

## 実機判定（Phase 0の未完了ゲート）

コード実装に入る前に、利用予定のChatGPTアカウントで以下を**Skills-onlyの最小検証**として実施する。現時点ではChatGPTのPlugin実行セッション・開発者ポータルの権限をこの作業環境から確認できていないため、結果を推測で埋めない。

- アカウントでSkills-only Pluginの作成・ローカルインストール・ChatGPT Workでの呼び出しが可能か確認する。CloudとLocalを区別し、公開提出に必要な開発者確認・対象プランも確認する。
- スキルに同梱したPythonスクリプトから`import pymupdf`とフォント読み込みを確認する。インストールが必要なら再現可能な手順、ネットワーク制限、ZIPサイズを測る。
- 添付した英語PDFをスクリプトから開き、原文のブロック数・座標を取得する。モデルがID付き訳文を返し、Python側に渡せることを小さいPDFで確かめる。
- 11ページの実論文で最後まで処理し、全ページ数とページ寸法、訳文の欠落・重複、参考文献の原文維持、生成PDFのダウンロードを確認する。途中停止後の再開も試す。
- **Go:** 実行・ファイル入出力・全文連携・公開条件を満たすならSkills-onlyで進める。**条件付きGo:** ローカルデスクトップのみで満たす場合は、その配布範囲を許容するか確認する。**No-Go:** 必須要件が実測で満たせない場合のみRemote MCPを評価する。MCPでもChatGPT本体が翻訳したテキストをツールへ渡す経路を実測で確認し、APIキーをサーバーへ隠して「ユーザー枠で推論」とは主張しない。

## Sources

公式資料（閲覧日: 2026-11-27）。機能・申請条件は変わりうるので実装・公開前に再確認する。

1. [Plugin architecture](https://developers.openai.com/plugins/concepts/plugins) — Skills-only / MCP / 併用の選択。
2. [Package your plugin](https://developers.openai.com/plugins/build/plugins) — `plugin.json`と同梱ファイル。
3. [Upload and submit your plugin](https://developers.openai.com/plugins/deploy/submission) — Skills-onlyの提出、本人確認・審査。
4. [Plugins in ChatGPT](https://help.openai.com/articles/20001256) — Plugin Directoryとプラン・環境の制約。
5. [Build skills](https://developers.openai.com/plugins/build/skills) — `SKILL.md`と`scripts/`・`assets/`。
6. [Data analysis with ChatGPT](https://help.openai.com/articles/8437071) — Python実行と外部API通信不可の制約。
7. [Uploading files to ChatGPT](https://help.openai.com/articles/8555545) — PDF添付、ファイルサイズ等。
8. [Use ChatGPT](https://developers.openai.com/codex/use-chatgpt) — Workのファイル生成・ダウンロード、Cloud/Local。
9. [Submit desktop-only plugins](https://developers.openai.com/plugins/deploy/desktop-only) — `requires_local_executor`と公開範囲。
10. [Build an MCP server](https://developers.openai.com/plugins/build/mcp-server) — Remote MCPのHTTPS・運用要件。
11. [Skills in ChatGPT](https://help.openai.com/en/articles/20001066-skills-in-chatgpt) — 個人向けSkillsの対象プランとワークスペース制御。
