# 技術的な懸念と検証事項

## ChatGPTプランの利用

OpenAIはオープンソース・ローカル実行アプリ向けに、ユーザーが許可したChatGPTプランで対象のResponses APIリクエストを行う公式フローを公開しています。単なる「ChatGPTでサインイン」だけでは推論権限は得られず、別途スコープと同意が必要です。一般的なAPIキーによるAPI利用はChatGPTの契約と別の課金体系です。

公開されているOSS向けフローは`http://127.0.0.1:<port>/auth/callback`のローカルHTTPリスナーを前提とし、コールバックURLのホスト・パスを固定するよう指定しています。まずPythonのローカルプロセスで受け取る方式を検証します。Chrome拡張の`chrome.identity.launchWebAuthFlow`は別のリダイレクト先を使うため、拡張機能単体での認証は後から検討します。

このプラン利用フローはオープンソース・ローカル実行向けとして案内されています。有料またはリモートホスト型アプリについてOpenAIは[問い合わせ](https://openai.com/form/sign-in-with-chatgpt-interest/)を案内しています。リモート型で絶対に利用できないという意味ではありませんが、OSSや少人数利用を理由に、Cloudflareや自宅サーバー上でも同じフローを使えるとは判断しません。

**Phase 0の判定条件：** 公式フローでローカル認証とトークン更新を行い、固定英文を承認済みChatGPTプランで翻訳できること。アクセストークンの取得だけでなく推論完了を確認します。資格・利用制限・OSSとしての公開条件も調べます。開発者負担のAI API課金、非公開API、セッションCookieの流用で代替しません。

`pshift login`の初回・再認証フローとstate検証、モデル一覧取得、トークン更新、短文翻訳の`response.completed`判定はローカルの模擬応答で確認済みです。ChatGPTプラン認証の実アカウントで`pshift translate "The results were significant."`が「結果は有意だった。」と完了することを確認しました。モデル未選択からアカウントのモデル一覧の先頭（`gpt-6.2-sol`）を保存した後の成功です。実際のトークン更新や別のモデルでの推論はまだ未検証です。`pshift model`の表示だけでは推論の利用可否を保証しません。

ログイン時はブラウザ認証、headless端末への[保護した認証情報の転送](https://developers.openai.com/siwc/token-sharing-open-source/self-hosted-vms)、OpenAI Platform API keyを選べます。[Codex CLIのデバイスコード認証](https://developers.openai.com/codex/auth#login-on-headless-devices)はCodex向けで、PaperShiftの[OSS向け直接認証手順](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)にはデバイスコードの利用方法が示されていないため、ワンタイムコード方式は未対応です。API keyはChatGPTプランではなく別の従量課金です。API keyの有効性はモデル一覧APIで確認しますが、特定モデルの利用可否や推論完了は別途検証が必要です。

## 日本語版PDFの生成

PDFの文字には座標があっても、段落・読み順・数式の意味が常に得られるわけではありません。複数カラム、スキャンPDF、表のセル、長くなった訳文は特に難しい領域です。日本語フォントの埋め込み、原文の隠し方、訳文の配置と改行が保存後も成立する必要があります。元PDFに白い領域を重ねるだけでは、背後の英語テキストがPDF内に残る場合があります。

まずテキストを選択できる英語論文の本文段落だけを訳すPDF生成実験を行います。図・表・数式と内部のラベルや注記は翻訳対象から外し、元PDFの表示を同じ位置・大きさで残します。スクリーンショット化して貼り直すと画質やベクター情報を失うため、元ページを直接活用します。キャプションも初期段階では保全を優先します。

PyMuPDFの文字除去機能は、指定範囲に重なる画像や線にも影響し得ます。本文と図が接する場合は図を壊さないことを優先し、その領域の置換を見送ります。原文を安全に除去できない箇所や訳文が収まらない箇所の扱いは実PDFで決めます。元レイアウトの完全再現はMVPの保証に含めず、読めないPDFを正常な翻訳結果として返さない方法を検証します。

## Chrome標準PDFビューアとの統合（将来）

公開された`chrome.mimeHandler`はChrome 151以降で利用でき、`application/pdf`を扱う拡張機能ページを登録できます。標準ビューアにUIを足すAPIではなく、自作ビューアで**置き換える**方式です。対応バージョン、他のPDF拡張との競合、埋め込みPDF、ローカルファイルを実機で確認する必要があります。MVPではPC上のPDFを直接指定します。

## 参照した公式資料

- [OpenAI — Sign in with ChatGPT Quickstart](https://developers.openai.com/siwc/quickstart)
- [OpenAI — OSS向けChatGPTプラン利用：概要](https://developers.openai.com/siwc/token-sharing-open-source)
- [OpenAI — OSS向け登録・サインイン](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)
- [OpenAI — モデル・推論の要件](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference)
- [PyMuPDF — PDFページの編集・文字除去](https://pymupdf.readthedocs.io/en/latest/page.html)
- [PyMuPDF — ライセンス](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright)
- [Chrome Extensions — `chrome.identity`](https://developer.chrome.com/docs/extensions/reference/api/identity)
- [Chrome Extensions — `chrome.mimeHandler`](https://developer.chrome.com/docs/extensions/reference/api/mimeHandler)

初期のPDF生成は、PyMuPDFで英語テキスト領域を抽出・削除し、同梱のNoto Sans JP / Noto Serif JPでおおよそ同じ位置に配置します。元のブロックごとの文字サイズと太さを参考にし、必要な箇所のみ縮小します。元ページを使うため画像・線画とページ数を保てます。実際のChatGPTプラン認証で2ページの合成サンプルに加え、`test/`の7ページの論文を翻訳しました。論文のページ数と各ページの画像・線画の数は元PDFと一致し、51領域の日本語訳を含むPDFを保存できました。参考文献、著者・所属、投稿情報と非常に小さなヘッダー・脚注は原文のままです。図内の文字、数式、複雑な段組み、スキャンPDFの判定や精密な配置は今後の課題です。訳文が収まらない場合は出力せず停止します。
