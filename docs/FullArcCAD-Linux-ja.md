# FullArcCAD Linux版 0.2.242-preview1

旧FluxCADの最新採用版0.2.242-alphaを基にしたLinux x86_64向け試作版です。リボン左上ロゴ、ウィンドウ名、日英メニューはFullArcCAD。構築点・座標と方向による構築軸、CADメッシュ作成・検査・細分化・成分除去・面削除を含む採用済み343 Pythonモジュールから作成しました。全機能互換・完成品ではありません。

## 起動

FreeCAD本体とフォントは同梱しません。公式FreeCAD Linux 1.1.x、Python3を別途用意してください。検証済みはFreeCAD1.1.3です。

```sh
sha256sum -c FullArcCAD-0.2.242-linux-preview1.tar.gz.sha256
tar -xzf FullArcCAD-0.2.242-linux-preview1.tar.gz
cd FullArcCAD-0.2.242-linux-preview1
sh Start-FullArcCAD.sh --freecad /absolute/path/to/FreeCAD.AppImage --language ja
```

AppImageを実行可能にしてください。FUSEがない環境ではFreeCAD公式手順でAppImageを展開し、`--freecad /absolute/path/to/squashfs-root/AppRun`を指定します。FreeCADバイナリの自動ダウンロードはしません。

`--language en`で英語表示。`--check`は起動経路の読取確認だけで設定を作りません。`--state-dir /absolute/private/path`で保存先を分離できます。既定はXDG_STATE_HOME/fluxcadまたは~/.local/state/fluxcad。旧FluxCADの環境変数FLUXCAD_FREECAD/FLUXCAD_STATE_DIR/FLUXCAD_FONT・設定キー・旧Start-FluxCAD.shは互換性維持のため残しています。

## 検証と制限

実Linux Ubuntu24.04 / Xvfb / Mesaでnative 199項目＋拒否76項目、日英Qt合計78項目（実QAction合計38回）、起動処理18試験が合格。詳細はLINUX-VALIDATION.jsonとlinux-tests/resultsを参照してください。選択した試験のみであり、全機能網羅ではありません。

**物理GUI入力、Wayland、実GPU、高DPI、他ディストリビューションは未確認です。** 仮想画面上のnative/Qt自動試験を物理GUI確認とは扱いません。未採用の性能候補は混入していません。

SolidWorks厳密BRep変換はWindows専用のためLinuxでは実行前に明示拒否します。STEP取込とは別の制限です。保存表示メッシュ取込は残っていますがLinux未検証。日本語文字にはローカルNoto CJK等が必要で、Windowsフォントを参照する文書の文字再生成時にはLinux上の対応フォントを指定してください。

MITライセンス。サードパーティの既存ライセンスを同梱しています。Autodesk/Fusionの製品・公式互換品ではありません。
