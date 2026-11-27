# 詳しい使い方と制限

基本的なインストールとコマンドは[README](../README.md)を参照してください。

## CLI

- 初回は`pshift login`でChatGPTブラウザ認証を選びます。モデルを指定しなければ、利用可能な一覧の先頭が選ばれます。選び直すには`pshift model`を実行します。
- 出力先を省くと`paper.pdf`から`paper-ja.pdf`を作ります。既存の出力を上書きするときだけ`--force`を指定します。入力PDFは変更しません。
- ブラウザを開けない端末では、`pshift login --method headless`に表示される手順に従い、別端末の認証ファイルを安全に転送します。読み込みは次のコマンドです。

  ```sh
  pshift login --method headless --from-file <認証ファイル>
  ```

- `pshift status`は保存された認証方式を表示しますが、トークンが現在も有効かは検証しません。`pshift logout`はローカルの認証情報を削除します。
- `pshift login --method api-key`はOpenAI Platformの従量課金です。ChatGPTプランへ自動で切り替わることはありません。

## Agent Skill / ChatGPT Plugin

- [Agent Skill](../skills/paper-shift/SKILL.md)はClaude Code / Codexのモデルが翻訳します。初回は[v0.3.1のPlugin ZIP](https://github.com/med-000/paper-shift/releases/tag/v0.3.1)をダウンロード・ハッシュ検証し、同梱のPDF処理と日本語フォントを使います。Python 3.11以降とPyMuPDFが必要です。
- [ChatGPT用Plugin ZIP](https://github.com/med-000/paper-shift/releases/download/v0.3.1/paper-shift-plugin.zip)はChatGPTに登録して利用します。ChatGPT本体が訳文を作るため、CLIのログインや開発者の翻訳用APIキーは使いません。ZIPの配布とPlugin公開ディレクトリへの掲載は別です。
- どちらもPDFから原文を抽出し、ID付きの訳文を検証して再構築します。長い論文では全翻訳バッチの完了が必要です。

## 更新方法

- **配布版CLI**：v0.3.1以降は`pshift update --check`で最新版を確認し、`pshift update`で更新できます。macOS arm64 / Linux x86_64の標準インストール先（`~/.local/bin/pshift`）が対象です。GitHub Releaseのチェックサムと実行ファイルのバージョンを検証してから置き換えます。**v0.3.0の実行ファイルにはまだupdateコマンドがないため、最初の更新はREADMEのインストールコマンドを再実行してください。**
- **ソース版CLI**：リポジトリで`git pull`してから`uv sync`を実行します。`pshift update`はソース版を書き換えません。
- **Agent Skill**：`npx skills update paper-shift -g`でインストール済みSkillを更新します。Skillはv0.3.1のPlugin ZIPを指定しているため、Skill側の参照先が新しいリリースに更新されるまでPDFエンジンは変わりません。
- **ChatGPTのローカルPlugin**：新しいリリースのPlugin ZIPを入手し、ChatGPTのPlugin詳細で**Upload new version**があればアップロードします。ワークスペース管理者によるアップロードの場合は、そのワークスペースの管理画面から更新してください。GitHub Releaseの公開だけでは登録済みPluginは更新されません。

## PDFの仕上がり

- ページ数・サイズ、図や画像はできるだけ維持しますが、段組みや訳文の配置を完全には再現できません。
- References見出しを検出すると、その位置以降と後続ページは原文のまま残します。参考文献以外の後続セクションも翻訳されません。
- 図中の文字、数式、著者・所属、小さなヘッダーや脚注は英語のまま残ることがあります。
- 画像だけのスキャンPDF、暗号化PDFには対応しません。訳文が領域に収まらない場合、未完成のPDFは保存しません。
