# FluxCAD 0.2.234 Linux preview1

採用済みWindows版0.2.234-alphaの実ファイルを基にしたLinux試作版です。Linux用FreeCADは別途必要です。このアーカイブにはFreeCAD本体・フォント・ユーザー設定・CAD作業ファイルを含めません。

## 入手

[Linux試作版リリース](https://github.com/victriokook/fluxcad/releases/tag/v0.2.234-linux-preview1)から`FluxCAD-0.2.234-linux-preview1.tar.gz`と同名`.sha256`を取得します。

## 起動

対象はLinux x86_64、FreeCAD 1.1.x、システムのPython 3です。FreeCAD本体のPython/Qtを使うため、システムPythonへFreeCADやPySideをpipで入れる必要はありません。

1. [公式FreeCAD配布](https://github.com/FreeCAD/FreeCAD/releases)からLinux用AppImageを取得し、実行権限を付けます。
2. FluxCADのtar.gzを展開します。
3. 展開先で次を実行します（AppImageのパスは手元のファイルへ変更）。

```sh
chmod +x "$HOME/Downloads/FreeCAD_1.1.3-Linux-x86_64-py311.AppImage"
sh Start-FluxCAD.sh --freecad "$HOME/Downloads/FreeCAD_1.1.3-Linux-x86_64-py311.AppImage" --language ja
```

インストール済みの`FreeCAD`/`freecad`がPATHにある場合は、`sh Start-FluxCAD.sh --language ja`でも起動できます。AppImageを`runtime/FreeCAD.AppImage`として置く方法、展開済みAppImageの`AppRun`を`--freecad`で指定する方法にも対応します。AppImageをFUSEなしで使う方法は[公式説明](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/AppImage.md)を参照してください。

起動せずに設定を確認するには、同じコマンドへ`--check`を付けます。実行ファイルパスをシェル式として解釈しません。

## 設定と日本語フォント

- 設定・データ・一時ファイルは`$XDG_STATE_HOME/fluxcad`、未設定なら`~/.local/state/fluxcad`へ分離します。通常のFreeCAD設定を流用しません。
- `--state-dir /absolute/path`で変更できます。相対パスは拒否します。
- `--language en`で英語表示になります。保存した言語設定は次回にも残ります。
- 文字ソリッド／文字スケッチの初期フォントはローカルのNoto CJK等から検出します。日本語を使う場合はNoto Sans CJK JP等をLinux側へ用意してください。フォントは同梱・自動取得しません。
- `FLUXCAD_FONT=/absolute/path/font.ttc`で初期フォントを指定できます。個々の字形が有効なCAD曲線／面になるかは、既存のnative検証に従います。
- フォントが異なると文字形状も異なります。Windows版で作成した文字ソリッドの再生成には、その文書で参照したフォントが必要です。

## この試作版の範囲

基準は`test-results/navigation-guard-candidate`にある採用済み321 Pythonモジュールです。未採用の性能候補は混ぜていません。Linux専用の変更は起動処理、初期フォント検出、Windows専用SolidWorks変換の明示拒否です。Windows製品ファイルは変更しません。

**SolidWorksの厳密BRep取込は未対応です。** Windows専用decoder/workerは同梱せず、実行前に説明付きで拒否します。STEP/FCStd等の標準形式とは別の制限です。SolidWorksの保存表示メッシュ取込機能は残しますが、この試作版ではLinuxでの取込試験は未実施です。例題メニュー用の作業サンプルも同梱していません。

Linuxでの機能確認は選択したnative・Qt回帰試験の範囲に限られます。全321モジュールの機能網羅、実Linuxデスクトップでのマウス・キーボード操作、Wayland/GPU/高DPI、各Linuxディストリビューションは別途確認が必要です。XvfbでのQt描画・自動操作を物理GUI確認とは扱いません。

## 自動試験

```sh
python3 linux-tests/run-portable-tests.py /tmp/fluxcad-launcher-report.json
sh Start-FluxCAD.sh --freecad /path/to/FreeCAD.AppImage --smoke native --report-dir /tmp/fluxcad-native
sh Start-FluxCAD.sh --freecad /path/to/FreeCAD.AppImage --smoke integration --report-dir /tmp/fluxcad-integration
sh Start-FluxCAD.sh --freecad /path/to/FreeCAD.AppImage --smoke ja --report-dir /tmp/fluxcad-ja
sh Start-FluxCAD.sh --freecad /path/to/FreeCAD.AppImage --smoke en --report-dir /tmp/fluxcad-en
```

各`--smoke`は専用の合成文書を作り、そのFreeCADプロセスを閉じます。開いている通常セッションへマクロを読み込まず、専用起動で実行してください。ヘッドレス環境では`xvfb-run -a`等の仮想ディスプレイが必要です。

試験結果は`LINUX-VALIDATION.json` (inside the downloaded Linux package)、生成元とLinux差分は`LINUX-BUILD.json` (inside the downloaded Linux package)、ファイル検証は`SHA256SUMS`に記録します。

## ライセンス

FluxCAD独自コードはMIT（`LICENSE`）。同梱SheetMetal、networkx、SolidWorks表示メッシュ読取コードには各フォルダのライセンス・出典が適用されます。FreeCAD自体は別配布で、そのライセンスが適用されます。Autodesk/Fusionの公式製品ではありません。
