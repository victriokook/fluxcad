# GitHubへの初回公開

このフォルダはGitHub公開用のソースです。実行環境、個人設定、開発ログは含めていません。初回バージョンは `0.1.0-alpha`、タグは `v0.1.0-alpha` とします。

## 1. 公開先を作成

GitHubへログインし、New repositoryでリポジトリを作成します。名前の例は `fluxcad`、説明文の例は次のとおりです。

> A compact Japanese/English workspace for FreeCAD, with modeling workflows inspired by Fusion.

公開する場合はPublicを選びます。README・LICENSE・.gitignoreはこのフォルダに用意してあるため、GitHub側では追加しません。

## 2. ソースを登録

この公開用フォルダで端末を開いて実行します。`YOUR_ACCOUNT` は自分のアカウント名へ置き換えてください。

```powershell
git init -b main
git add .
git commit -m "Prepare FluxCAD 0.1.0-alpha"
git remote add origin https://github.com/YOUR_ACCOUNT/fluxcad.git
git push -u origin main
```

ローカルGitが初期化済みなら最初の行は不要です。Gitが名前・メールアドレスを要求する場合は、自分の公開用の名前とメールアドレスを、このリポジトリに設定してからcommitします。署名やアカウント認証は利用者の設定に従ってください。

## 3. 配布ZIPを作成

開発者用Python 3.11以上で以下を実行します。通常のFluxCAD利用者にはPythonの追加インストールは不要です。

```powershell
python scripts/check_source.py
python scripts/build_release.py
```

`dist/` に次の3ファイルを生成します。

- `FluxCAD-v0.1.0-alpha-windows.zip` — 利用者向け。FreeCADは別途必要。
- `FluxCAD-v0.1.0-alpha-source.zip` — 開発・検証スクリプトを含むソース一式。
- `SHA256SUMS.txt` — ZIPのチェックサム。

## 4. Pre-releaseを公開

GitHubのReleasesから新しいリリースを作り、タグ `v0.1.0-alpha`、対象ブランチmain、タイトル `FluxCAD 0.1.0-alpha` を指定します。**Pre-release** を有効にし、上記ファイルを添付します。ZIP自体をソース履歴へcommitする必要はありません。

リリース本文には、以下を使用できます。

> FluxCADの初回試用版です。Windows／FreeCAD 1.1.3で動作を検証しています。FreeCAD本体は含まれていません。
>
> 日本語・英語のリボン、スケッチと領域選択、ソリッド加工、メッシュ操作、基本ジョイント、サーフェスと製図操作を利用できます。グリッドスナップの強化と間隔入力の修正を含みます。
>
> 利用する場合はwindows.zipを展開し、Start-FluxCAD.cmdを起動してください。既知の制限はREADMEと操作ガイドに記載しています。不具合は再現手順を添えてIssuesへお願いします。

## 公式資料

- [リポジトリの作成](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository)
- [リリースの作成・管理](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)
- [Issueの作成](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/creating-an-issue)

この文書や公開用ZIPの生成自体は、GitHubへのアップロードを行いません。
