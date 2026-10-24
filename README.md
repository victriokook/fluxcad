# FullArcCAD

## 最新Windows版 — FullArcCAD 0.2.242-alpha

[Windows ZIPをダウンロード](https://github.com/victriokook/fluxcad/releases/download/v0.2.242-alpha/FullArcCAD-0.2.242-windows.zip) · [リリース・チェックサム](https://github.com/victriokook/fluxcad/releases/tag/v0.2.242-alpha) · [Windows起動手順](docs/FullArcCAD-Windows-ja.md) · [Linux版](https://github.com/victriokook/fluxcad/releases/tag/v0.2.242-linux-preview1)

Windows版も旧FluxCAD0.2.122から最新採用版0.2.242へ更新して公開しました。**新しいフォルダーへ展開して`Start-FullArcCAD.cmd`を実行**してください。FreeCADは別途必要で、パッケージ試験はWindows/FreeCAD1.1.4で実行しています。旧Start-FluxCAD起動ファイルと設定の互換性は保持しました。

採用済み343モジュールから作成し、日本語・空白パスでnative19項目＋拒否6項目、日英Qt合計46項目（実QAction18回）、新旧起動スクリプトの引用・ZIP全payloadハッシュ・展開が合格。**物理GUI入力と全機能網羅は未確認です。** Windows ZIPには固定版cadmpeg変換器と必要なworker・通知を含みますが、SolidWorks厳密BRep変換は実験的で、今回ユーザーの新しいSolidWorksファイルでは試験していません。

リリース添付のWindows ZIP・source ZIPが最新実装です。ソースZIPはdecoder実行ファイルを除外しています。GitHub自動生成Source codeアーカイブは旧リポジトリ基点で別物です。Linux版・紹介動画・旧配布物は保持しています。


旧FluxCAD。FreeCADに日本語・英語のリボンとモデリング操作を加えるワークスペースです。製品表示名をFullArcCADに変更しました。

[YouTubeで紹介動画を見る](https://www.youtube.com/watch?v=yTPC997dG_Y)（@koyo1217・怪人ビクトリオの遊び）

## 最新Linux版 — 0.2.242-linux-preview1

[Linux版をダウンロード](https://github.com/victriokook/fluxcad/releases/tag/v0.2.242-linux-preview1) · [日本語起動手順](docs/FullArcCAD-Linux-ja.md) · [English](README-en.md) · [72秒の紹介動画MP4](https://github.com/victriokook/fluxcad/releases/download/v0.2.242-linux-preview1/FullArcCAD-Linux-Introduction-ja.mp4)

Linux x86_64用の試作版です。FullArcCADロゴ修正、座標で構築点、座標と方向で構築軸、CADからメッシュ作成・検査・細分化・成分除去・面削除など、採用済み0.2.242-alphaの実ファイル343 Pythonモジュールを基に作成しています。

```sh
tar -xzf FullArcCAD-0.2.242-linux-preview1.tar.gz
cd FullArcCAD-0.2.242-linux-preview1
sh Start-FullArcCAD.sh --freecad /absolute/path/to/FreeCAD.AppImage --language ja
```

FreeCAD・Python3・フォントは別途必要です。公式FreeCAD1.1.3 / Ubuntu24.04コンテナ + Xvfb + Mesaで、native・連携199項目＋拒否76項目、日英Qt合計78項目（実QAction38回）、起動処理18試験が合格。**物理GUI入力・Wayland・実GPU・高DPI・他ディストリビューションは未確認。全機能網羅・Windows/Linux完全同等性は保証しません。** SolidWorks厳密BRep変換はLinux未対応で明示拒否します。

動画はLinux仮想画面をAPIで操作した自動デモと日本語字幕です。物理操作の録画ではありません。ユーザーCAD・個人データ・外部音楽は含みません。

**添付`FullArcCAD-0.2.242-linux-preview1.tar.gz`が最新Linux実装ソース一式です。GitHubの自動生成Source codeアーカイブとmainのアプリコードは旧Windows公開基点であり、最新Linux配布とは別です。** Windows公開版0.2.122-alpha、旧Linux0.2.234の配布物は保持しています。旧設定・保存形式・環境変数のFluxCAD識別子は互換性のため維持。

## 従来のWindows公開版

### Windows版の起動

1. FreeCADを別途インストールします。今回の検証環境はWindows / FreeCAD 1.1.4です。
2. [Releases](https://github.com/victriokook/fluxcad/releases)から `FluxCAD-v0.2.122-alpha-windows.zip` を取得し、書き込み可能な新しいフォルダへ展開します。旧版フォルダへの上書きは避けてください。
3. `Start-FluxCAD.cmd` を実行します。必要なら `Start-FluxCAD.ps1 -FreeCADPath "C:\path\to\FreeCAD\bin\FreeCAD.exe"` で指定できます。
4. ファイル → 使用例を作業コピーで開く、または `samples/Sample.FCStd` から試せます。作業文書は別名で保存してください。

FreeCAD本体・Python・OpenCASCADEは同梱しません。専用設定は展開先のconfigに保存します。ソースZIPには149 MBのcadmpeg実行ファイルを含めません。実験的なSolidWorks厳密読込も試す場合はWindows配布ZIPを利用してください。

## Windows公開版の実装概要

| 分野 | 内容 |
|---|---|
| スケッチ | 線・円弧・接線・寸法拘束、数値楕円、スナップ、入れ子/交差領域の選択 |
| ソリッド | 押し出し、回転、スイープ、ロフト、穴、フィレット、面取り、シェル、結合/切削、尺度、位置合わせ、配置パターン |
| 樹脂 | リブ、ボス、三角リブ、スナップ爪、抜き勾配、寸法連動ケース、中空ドーム |
| 板金 | 同梱SheetMetalによるベース板、辺のフランジ、展開。複雑な全板金形状への対応保証はありません |
| 面・メッシュ・図面 | サーフェス操作、断面、メッシュ処理、図面/出力、画像保存 |
| 文書・組立 | パラメータ/CSV、部品配置、干渉確認、アニメーション/連番画像、使用例作業コピー、履歴/ブラウザー操作 |
| SolidWorks（実験・未完成） | 保存表示メッシュ読込と制限付き厳密ソリッド読込。一般ファイルの互換性、構成・色・加工履歴の再現は保証しません |

この表は実装の一覧であり、全操作・全組合せの合格証明ではありません。詳しい対象・制限は[公開版の検証範囲](docs/releases/0.2.122-alpha.md)と[第三者ライセンス](THIRD_PARTY_NOTICES.md)を参照してください。

## 今回の選択修正

入れ子と交差輪郭の欠落領域、および微小領域が0.00 mm²になる表示を修正した採用済み実装を含みます。全選択不具合の解消は主張しません。未採用のbrowser.py/fluxcad.py性能案、大量の機械比較モデル、元STEP/BRep、個人設定・キャッシュは含みません。

実行コードはローカル採用済み99モジュールと照合しています。日英起動・基本加工・Undo/Redo・保存再読込・同梱モデルの再計算を段階検証します。物理UIの記録とAPIの補助試験は区別しています。

## 開発

`python scripts/check_source.py` で静的検査、`tests/Run-Smoke.ps1` で隔離FreeCAD試験を実行できます。配布ZIPのハッシュはSHA256SUMS.txtに記録します。[Contributing](CONTRIBUTING.md)も参照してください。

FluxCADはFreeCAD/Autodeskの公式製品ではありません。
