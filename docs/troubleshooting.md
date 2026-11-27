# トラブルシューティング

## インストール・認証

- **`pshift: command not found`**：インストール後に新しいターミナルを開いてください。macOSは`~/.local/bin`を読み込むzshの`.zprofile`、Linuxは`.profile`を確認します。
- **未ログイン／セッション失効／プランの権限不足**：`pshift login`で再認証します。`pshift status`は保存済み情報の表示で、有効性の確認ではありません。
- **ブラウザがない端末**：`pshift login --method headless`で別端末から認証情報を取り込む手順を表示します。認証ファイルを公開しないでください。
- **モデルが選べない／推論に失敗する**：`pshift model --list`でアカウントのモデル一覧を確認し、別のモデルを選びます。通信障害の場合は接続を確認して再実行してください。

## PDF・Skill・Plugin

- **「翻訳できる英文テキストがありません」**：文字を選択できる英語PDFか確認してください。スキャンPDFのOCRは未対応です。
- **出力先が既に存在する**：別の出力名を指定するか、CLIでは`--force`で上書きします。入力PDFと同じパスは指定できません。
- **訳文を配置できない**：長い日本語が元の領域に収まらない場合があります。未完成のPDFは作成されません。別のPDFや短い文章で試してください。
- **Skillが表示されない**：Claude Codeは`~/.claude/skills/paper-shift/SKILL.md`、Codexは`~/.agents/skills/paper-shift/SKILL.md`の配置を確認し、エージェントを再起動します。
- **SkillでZIP取得／ハッシュ検証に失敗**：GitHubへの接続を確認してください。チェックサムが違うZIPは実行せず、[v0.3.0 Release](https://github.com/med-000/paper-shift/releases/tag/v0.3.0)から取り直します。
- **Plugin/SkillでPyMuPDFが見つからない**：実行環境に`PyMuPDF>=1.26,<2`をインストールできるか確認してください。利用できない環境ではPDFの再構築はできません。
- **参考文献の後が英語のまま**：References見出し以降は、後続セクションも含め翻訳対象外です。[詳しい制限](usage.md#pdfの仕上がり)を参照してください。
