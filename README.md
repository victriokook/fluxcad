# FluxCAD

FreeCADに日本語・英語のリボンとモデリング操作を加えるWindows向けワークスペースです。

[English](README-en.md) · [操作ガイド](docs/User-guide-ja.md) · [変更履歴](CHANGELOG.md)

**0.2.122-alpha — 2026-10-19。現在の採用済み実装をまとめ直した新公開版です。** 旧0.1.0-alpha用の差分パッチではありません。完成保証のある製品ではなく、試用・検証向けアルファ版です。

## 起動

1. FreeCADを別途インストールします。今回の検証環境はWindows / FreeCAD 1.1.4です。
2. [Releases](https://github.com/victriokook/fluxcad/releases)から `FluxCAD-v0.2.122-alpha-windows.zip` を取得し、書き込み可能な新しいフォルダへ展開します。旧版フォルダへの上書きは避けてください。
3. `Start-FluxCAD.cmd` を実行します。必要なら `Start-FluxCAD.ps1 -FreeCADPath "C:\path\to\FreeCAD\bin\FreeCAD.exe"` で指定できます。
4. ファイル → 使用例を作業コピーで開く、または `samples/Sample.FCStd` から試せます。作業文書は別名で保存してください。

FreeCAD本体・Python・OpenCASCADEは同梱しません。専用設定は展開先のconfigに保存します。ソースZIPには149 MBのcadmpeg実行ファイルを含めません。実験的なSolidWorks厳密読込も試す場合はWindows配布ZIPを利用してください。

## 含まれる実装

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
