# FullArcCAD 0.2.242-alpha — Windows版

旧FluxCAD。採用済み343モジュールを基にしたWindows x86_64向け開発版です。リボン左上・タイトル・日英メニューはFullArcCAD。構築点・構築軸と現在のメッシュ/ソリッド/サーフェス等の採用済み機能を含みます。旧版への差分パッチではありません。

## 起動

1. Windows用FreeCADを別途インストールしてください。今回のパッケージ試験はFreeCAD1.1.4で実行しました。FreeCAD本体・そのPython・フォントは同梱しません。
2. `FullArcCAD-0.2.242-windows.zip`を、書き込み可能な新しいフォルダーへ展開します。旧版への上書きは避けてください。
3. `Start-FullArcCAD.cmd`を実行します。必要なら次のようにFreeCAD実行ファイルを指定できます。

```powershell
.\Start-FullArcCAD.ps1 -FreeCADPath "C:\Program Files\FreeCAD 1.1in\FreeCAD.exe"
```

設定は展開先のconfigに作られます。旧Start-FluxCAD.cmd/ps1、FCStd保存形式・FluxCADの設定識別子は互換性のため残しています。使用例は「ファイル→使用例を作業コピーで開く」から別名コピーで利用してください。55件の使用例/サンプルは既存公開版からGit blob照合のうえ同梱しました。

## 検証と制限

実パッケージのコードを日本語・空白を含むパスへ複製し、Windows/FreeCAD1.1.4でnative19項目＋拒否6項目、日英Qt合計46項目（実QAction18回）、新旧ランチャーのPowerShell構文・引数引用を確認。構築点/軸、円形パターン、CADメッシュ作成/検査/細分化、Undo/Redo、保存再読込、日英ロゴの実QLabel文字と表示幅等が合格。ZIPの全payloadハッシュと展開も確認しました。

**物理GUI入力は未確認です。全343モジュールの機能網羅・完成保証・全FreeCADバージョン互換は主張しません。** 操作自動試験と物理GUI確認は区別しています。原本追従・形状種別など各機能の個別制限は引き続きあります。

SolidWorks厳密BRep変換は実験的です。Windows ZIPには既存の固定版cadmpeg.exeと必要なworker・ライセンスを同梱しましたが、今回新しいユーザーSolidWorksファイルでの変換は試験していません。ソースZIPはdecoder実行ファイルを含みません。この機能が必要ならWindows ZIPを利用してください。FreeCADの通常STEP取込とは別の制限です。

同梱WINDOWS-BUILD.json / WINDOWS-VALIDATION.json / validationに検証範囲を記録しています。未採用のroot性能候補は含めず、ユーザーCAD・個人設定・研究用キャッシュは同梱していません。

MITライセンス。cadmpegはApache-2.0、付属文書はCC-BY-4.0（vendor/cadmpegの通知を参照）。その他サードパーティのライセンスを保持しています。Autodesk/Fusionの公式製品ではありません。
