# PaperShift

英語論文などのPDFを入力し、図・表・数式とページレイアウトをできるだけ保った日本語版PDFを生成するオープンソースのアプリ構想です。まずは自分のPCでPDFを指定し、日本語版PDFを保存できるローカル実行版を作ります。ソースをGitHubで公開し、Windows・macOSのまっさらなPCでもインストーラーから導入できるCLIとして配布します。Webサービス化、Chrome拡張機能、画面上での訳文切り替えは後から検討します。

> **現状：構想・技術検証段階。** まだアプリは実装されていません。最優先は、ユーザーが公式のSign in with ChatGPTで認証し、許可されたChatGPTプランの枠で翻訳できるMVPです。特にPlus以上のユーザーを想定しますが、利用資格・モデル・利用制限は公式仕様と実際のアカウントで確認します。開発者がAI推論の利用料金を負担しないことは必須条件です。公開されているOSS向け認証フローはローカル実行を前提としているため、まずこの経路を検証します。

## 目指す体験

- 自分のPCで手元の英語PDFを指定して翻訳し、日本語版PDFを保存する。
- 図・表・数式は、中にある英語の軸ラベルや文字も含めて翻訳せず、元の位置・大きさで残す。本文の翻訳文だけをページ内に配置する。
- 後からWeb上のPDFの取り込みや、原文と訳文の画面上での切り替えに対応する。
- PDFの解析と日本語版PDFの生成は自分のPCで行い、翻訳に必要なテキストだけをOpenAIに送る。
- 将来的に並列表示、選択範囲の翻訳、要約、複数プロバイダーを追加する。

## 暫定的な技術構成

- **Python 3.11以降 / uv**：ローカルでのOAuthコールバック受信、PDF処理、ファイルの入出力。まずはCLIで小さく検証する
- **PyMuPDF**：PDFの文字・座標・フォント情報の抽出、元ページの編集、日本語版PDFの生成。図や表を元ページのまま残し、本文だけを処理できるか実PDFで検証する
- **日本語フォント**：訳文をPDFに配置するために使用。埋め込みと配布条件を確認する
- **端末内ストレージ（未定）**：認証情報の保護、翻訳結果の再利用や一時ファイルの管理
- **Sign in with ChatGPT + Responses API**：公式OAuthフローと承認済みChatGPTプランによる推論の検証対象
- **React / TypeScript（必要になれば）**：後から使いやすいローカルUIやWeb UIを付ける際の候補
- **WXT / Manifest V3 / Chrome MIME Handler API**：成立した場合に追加するChrome拡張機能・PDFナビゲーション統合
- **Cloudflareまたは自宅サーバー**：将来的なWebサービス化の候補。公式のリモートホスト型利用条件が確認できた場合に検討する

翻訳プロバイダーはPDF処理から分離しつつ、検証前に汎用フレームワークを作らない方針です。MVPの翻訳元はOpenAIのみとし、後にGoogleなどを追加できるようにします。開発者のAI用APIキーや開発者負担の推論枠は使わず、各利用者が自分のPCで認証し、自分で承認したChatGPTプランを利用します。GitHubでソースを公開し、当初は開発者自身が起動する形で配布します。

## ライセンス方針

PaperShiftは**AGPLv3でOSS公開する方針**とし、PyMuPDFのAGPLv3版をPDF処理の第一候補として検証します。公開する段階で正式な`LICENSE`ファイル、著作権・依存ライブラリの表記を整えます。PaperShiftで生成した翻訳済みPDFにAGPLv3が自動的に適用されるわけではありません。

## 開発用の構成

現在はCLIの起動口のみ実装しています。`pshift --help`と`pshift --version`が使えますが、PDF翻訳はまだ動きません。`ps`はmacOSの標準コマンドと衝突するため使いません。

```text
paper-shift/
├── .gitignore
├── pyproject.toml          # PythonパッケージとCLIの定義
├── uv.lock                 # uvの依存関係ロック
├── scripts/
│   ├── build-macos.sh      # macOS用の実行ファイルと配布アーカイブを作成
│   ├── install-macos.sh    # 実行ファイルを配置し、zshのPATHを設定
│   ├── install-online-macos.sh   # 公開アーカイブを取得してインストール
│   ├── build-windows.ps1   # Windows用の実行ファイルと配布アーカイブを作成
│   ├── install-windows.ps1 # 実行ファイルを配置し、ユーザーのPATHを設定
│   └── install-online-windows.ps1 # 公開アーカイブを取得してインストール
├── src/
│   ├── __init__.py
│   ├── __main__.py         # python -m src の起動口
│   └── cli.py              # pshift コマンドの起動口
└── README.md
```

認証、PDF抽出、翻訳、PDF生成は、それぞれの技術検証が済んだ段階で`src/`に追加します。最初から空のモジュールや共通インターフェースは作りません。macOSとWindowsで同じコードが動くよう、ファイルパスには`pathlib`を使用します。

[uv](https://docs.astral.sh/uv/getting-started/installation/)とPython 3.11以降を用意したら、リポジトリのルートで次を実行します（macOSのターミナルとWindowsのPowerShellで同じコマンドです）。

```sh
uv run pshift --help
uv run pshift --version
```

## 配布目標

開発者はPythonとuvでソースから実行します。PyInstallerでPython込みの単体実行ファイルとOS別の配布アーカイブを作る構成です。現時点の実行ファイルは`--help`と`--version`のみで、PDF翻訳は未実装です。macOS arm64では動作確認済みですが、Windowsのスクリプトと実行ファイルはWindows実機での検証が必要です。

macOSのビルド環境で以下を実行します（Pythonとuvが必要です）。

```sh
sh scripts/build-macos.sh
```

**現時点の手動配布**では、生成した`dist/pshift-macos-<arch>.tar.gz`を利用者がダウンロード・展開し、そのフォルダで次を実行します。インストーラーが実行ファイルを`~/.local/bin/pshift`へコピーします。利用者にPython・uv・Gitは不要です。

```sh
sh install-macos.sh
```

インストーラーは`~/.local/bin/pshift`に配置し、zshが使用する`.zprofile`（通常は`~/.zprofile`）へPATHの設定を追加します。**新しいターミナルを開いて**次を実行します。

```sh
pshift --help
```

`curl ... | sh`や`sh install-macos.sh`から現在のターミナルのPATHは変更できません。すぐに同じターミナルで使いたい場合だけ`source "${ZDOTDIR:-$HOME}/.zprofile"`で設定を読み直してください。次回以降は不要です。ChatGPTへのログインにはブラウザとインターネット接続が必要です。macOSの署名・公証によるOS警告の軽減は、まず動く配布物を作った後の改善項目です。

Windowsでは開発側がPowerShellから`scripts/build-windows.ps1`を実行してアーカイブを作る想定です。利用者は展開したフォルダで次を実行します（**Windows上では未検証**）。

```powershell
.\install-windows.ps1
pshift --help
```

`install-windows.ps1`はユーザーのアプリ用フォルダに実行ファイルをコピーし、ユーザーのPATHと現在のPowerShellのPATHを設定します。PowerShellの実行ポリシーによってスクリプト実行が制限される場合があるため、Windowsでの配布方法と合わせて実機で確認します。

**公開時の配布方針**は、macOSとWindowsで操作を分けます。macOSは`curl -fsSL <公開URL>/install-online-macos.sh | sh`による一行インストールです。GitHubにスクリプトを公開するだけでなく、対応CPU向けのビルド済みアーカイブをGitHub Releasesに置き、スクリプトのダウンロード先を公開URLに設定する必要があります。現在のオンラインスクリプトは`PAPERSHIFT_RELEASE_BASE_URL`による配布先指定が必要で、macOS arm64以外は未ビルドです。インストール後は新しいターミナルを開くか`source "${ZDOTDIR:-$HOME}/.zprofile"`でPATHを反映します。

Windowsはcmdから`curl.exe`で`.exe`インストーラーをダウンロードして起動し、インストーラーでPATHも設定する方針です。現在のPowerShell用スクリプトは技術検証用で、一般向けの`.exe`インストーラーは未実装です。GitHubにコードを公開しただけでは、両OSともインストール用URLや実行ファイルは完成しません。

現在は公開URLがなく、一行インストールはまだ利用できません。オンライン用スクリプトはリリース先のURLを`PAPERSHIFT_RELEASE_BASE_URL`として渡せるようにしてあり、公開時に配布先を確定します。Windowsのビルド・インストールは実機での動作確認が必要です。

Homebrewからのインストールは後から追加します。まずはこの配布アーカイブと手動のPATH設定でmacOS向けCLIを検証します。

## 先に解消する技術的な懸念

### 1. ChatGPTプランの利用と提供形態

OpenAIはオープンソース・ローカル実行アプリ向けに、ユーザーが許可したChatGPTプランで対象のResponses APIリクエストを行う公式フローを公開しています。単なる「ChatGPTでサインイン」だけでは推論権限は得られず、別途スコープと同意が必要です。一般的なAPIキーによるAPI利用はChatGPTの契約と別の課金体系です。

公開されているオープンソース向けフローは **`http://127.0.0.1:<port>/auth/callback` のローカルHTTPリスナー**を前提とし、コールバックURLのホスト・パスを固定するよう指定しています。これをPythonのローカルプロセスで受け取る構成から検証します。Webサイト上のログイン完了をサーバーで受け取る設計とはそのままでは両立しません。Chrome拡張の `chrome.identity.launchWebAuthFlow` も別のリダイレクト先を使うため、拡張機能単体での認証は後から検討します。

また、OpenAIの公開資料はこのプラン利用フローを「オープンソース・ローカル実行アプリ向け」と説明し、有料またはリモートホスト型アプリについては[問い合わせ](https://openai.com/form/sign-in-with-chatgpt-interest/)を案内しています。**リモート型で絶対に利用できないという意味ではなく、公開中のOSS向け手順だけでは利用可否が確定しない**という意味です。OSSであることや少人数利用を理由に、Cloudflareや自宅サーバー上で同じ認証フローを使えるとは判断しません。

**Phase 0の判定条件：** ローカルで公式の認証・トークン更新を行い、固定英文を自分の承認済みChatGPTプランで翻訳できること。アクセストークンの取得だけでなく、推論の完了まで確かめます。利用資格・制限・OSSとしての公開条件も確認します。開発者負担のAI API課金や非公開API・セッションCookie流用で代替しません。

### 2. Chrome標準PDFビューアとの統合

公開された `chrome.mimeHandler` は **Chrome 151以降**で利用でき、`application/pdf` を処理する拡張機能ページを登録できます。これはChrome標準ビューアにUIを足すAPIではなく、PDF表示を自作ビューアで**置き換える**方式です。拡張機能化する際に対応バージョン、他のPDF拡張との競合、埋め込みPDF、ローカルファイルを実機で確認します。MVPではPC上のPDFファイルを直接指定します。

### 3. 日本語版PDFの生成とレイアウト維持

PDFの文字には座標があっても、段落・読み順・数式の意味が常に得られるわけではありません。複数カラム、スキャンPDF、表のセル、長くなった訳文は特に難しい領域です。さらに、画面への重ね表示と違い、生成したPDFには日本語フォントを埋め込み、原文の隠し方・訳文の配置・改行を保存後も成立させる必要があります。元PDFに白い領域を重ねるだけでは、背後の英語テキストがPDF内に残る場合もあります。

まずテキストを選択できる英語論文を対象に、**本文段落だけ**を訳す小さなPDF生成実験を行います。図・表・数式およびその内部の軸ラベルや注記は翻訳対象から外し、元PDF上の表示を同じ位置・大きさで保持します。図をいったんスクリーンショット化して貼り直すと画質やベクター情報を失うため、まず元ページを直接活用します。キャプションも初期段階では保全を優先し、本文との判別が安定してから翻訳を検討します。

PyMuPDFの文字除去機能は、指定範囲に重なる画像や線にも影響し得ます。本文と図が接する場合は、その領域の置換を見送り、図を壊さないことを優先します。原文を安全に除去できない箇所や、訳文が収まらない箇所の扱いは実験で決めます。元レイアウトの完全再現はMVPの保証に含めません。見た目が読めないPDFを正常な翻訳結果として返さないため、レイアウト破綻の扱いも検証します。

## 開発ロードマップ

1. **Phase 0 — 技術検証：** 公開されているOSS向けローカル認証フローで固定英文の翻訳完了を確認する。並行してサンプル論文の一部を日本語PDFとして書き出す実験をする。
2. **Phase 1 — 初期構築：** 作成済みのPython CLIの骨組みに、ローカルPDFの入力・出力先を指定する操作を追加する。
3. **Phase 2 — AI連携：** Phase 0の検証を製品内に組み込み、認証、トークン更新・保護、固定英文の翻訳、認証・利用制限・通信エラーを扱う。
4. **Phase 3 — PDF解析：** PyMuPDFでテキスト・位置・フォント情報を抽出し、本文段落、複数カラムの読み順、図・表・数式・キャプションなど翻訳対象外領域を検証する。
5. **Phase 4 — PDF生成：** 元ページを活用し、日本語フォントの埋め込み、訳文の配置・改行・保存を実装する。まず翻訳済みの固定文で検証する。
6. **Phase 5 — PDF翻訳：** 抽出した本文をページ単位で翻訳し、原文との対応を保って日本語版PDFを出力する。ここでコア機能を完成させる。
7. **Phase 6 — 品質改善・配布：** 端末内キャッシュ、進捗・キャンセル・再試行、言語設定、macOSの一行インストールとWindowsの`.exe`インストーラーの整備、両OSのクリーン環境での動作確認。配布可能になった段階をMVPの完成とする。
8. **Phase 7 — 拡張：** 公式の利用条件が整えばWebサービス化を検討する。Chrome拡張機能化とブラウザPDF統合、Web PDFの取り込み、画面上の訳文切り替え・並列表示、選択翻訳、要約・用語解説・PDFチャット、Googleなどの追加プロバイダー。

## MVPの完成条件

Windows/macOSのクリーン環境に導入し、Python・uv・Gitなしで`pshift`を起動できること。手元の英語テキストPDFを指定し、ユーザー自身のChatGPT認証と承認済みプランで本文を翻訳した**日本語版PDFを保存できること**。図・表・数式とその内部の文字を翻訳せず、元の位置・大きさで保持し、出力したPDFを一般的なPDFビューアで読めること。**開発者負担のAI推論費用を発生させないこと。** Webサービス、Chrome拡張機能、画面上での原文・訳文切り替えはMVPの必須条件に含めません。

## 次に着手すること

Phase 0では、公開されているローカル向け認証フローで実際に翻訳が完了するか確かめます。並行して、サンプルPDFの本文を日本語に差し替えたPDFを保存できるか試します。両方成立したら、作成済みのCLIに入力・出力と翻訳機能を追加します。リモート運用への関心は残し、必要になったときに公式の提供条件を確認します。

## 参照した公式資料

- [OpenAI — Sign in with ChatGPT Quickstart](https://developers.openai.com/siwc/quickstart)
- [OpenAI — OSS向けChatGPTプラン利用：概要](https://developers.openai.com/siwc/token-sharing-open-source)
- [OpenAI — OSS向け登録・サインイン（ループバックの要件）](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)
- [OpenAI — モデル・推論の要件](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference)
- [PyMuPDF — PDFページの編集・文字除去](https://pymupdf.readthedocs.io/en/latest/page.html)
- [PyMuPDF — ライセンス](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright)
- [Chrome Extensions — `chrome.identity`](https://developer.chrome.com/docs/extensions/reference/api/identity)
- [Chrome Extensions — `chrome.mimeHandler`](https://developer.chrome.com/docs/extensions/reference/api/mimeHandler)

記載内容は2026年11月26日時点の公式資料に基づく整理であり、実機での動作確認はまだ行っていません。
