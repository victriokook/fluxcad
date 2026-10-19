# 数値楕円の編集例

FluxCADを起動してから `Positioned-ellipses-demo.FCStd` を開き、まず「名前を付けて保存」で作業用コピーを作ります。

この例は横幅40 mm・縦高さ20 mmの楕円を2つ、厚さ8 mmで押し出しています。中心は初期状態でXが−35/+35 mm、Yが10 mmです。

## 2つを連動して変更する

「パラメータを変更」で `Gap` を70 mmから100 mmに変更して適用すると、中心Xが−50/+50 mmへ移動します。`Width` と `Height` は2つの楕円に共通です。`CenterY` は両方の中心Yです。幅・高さは半径ではなく全長です。

## 左だけを移動・拡大する

1. 「パラメータを変更」の寸法割当一覧で、左楕円の `EllipseCenterX` と `EllipseWidth` を「固定値（式なし）」にして適用します。解除した直後は現在値を保ちます。末尾番号が異なる場合は対象の寸法名と現在値で確認します。
2. スケッチを編集し、「修正」→「楕円の中心位置を変更」を開きます。左楕円を選び、中心Xを−50 mmにして確定します。中心Yは連動中なので変更できません。
3. 「修正」→「楕円の横幅・縦高さを変更」で左楕円を選び、横幅を50 mmにします。縦高さは連動中の20 mmを保ちます。
4. スケッチ編集を終了します。既存の押し出しが追従し、右楕円は元の幅のままです。その後 `Gap` を変更すると右中心だけが追従します。

連動中の欄がグレーになるのは、パラメータで制御しているためです。両座標の連動を解除すれば「原点に戻す」も使用できます。中心座標はスケッチ内のXY座標です。長軸と短軸を入れ替える変更や同じ幅・高さにする変更は再作成してください。

上記の連動解除・独立編集・Undo/Redo・保存再読込は、使用例のコピーで検証しています。元のFCStdとCSVは変更していません。

# Editing the numeric ellipse example

Start FluxCAD before opening `Positioned-ellipses-demo.FCStd`, then save a working copy. The example contains two 40 × 20 mm ellipses extruded 8 mm, initially centered at X −35/+35 mm and Y 10 mm.

In Change Parameters, changing `Gap` from 70 to 100 mm moves the centers to −50/+50 mm. `Width`, `Height` and `CenterY` control both ellipses. Width and height are full lengths.

To edit only the left ellipse, set its `EllipseCenterX` and `EllipseWidth` assignments to **Fixed Value (No Expression)** and apply. This keeps their current values. Enter sketch editing, use **Move Ellipse Center** to set left X to −50 mm, then **Resize Ellipse** to set its width to 50 mm. Leave the linked Y and height unchanged. Existing extrusions update; the right ellipse retains its width. Later Gap edits affect only the still-linked right center.

Linked fields are disabled. Remove both coordinate bindings to enable Set to Origin. Coordinates are local to the sketch. Recreate an ellipse to swap major/minor axes or use equal dimensions. Independent edits, Undo/Redo and save/reload were verified on a copy; shipped originals remain unchanged.


複数楕円では、スケッチ編集中に対象の輪郭を1つ選んでから編集を開くと、その楕円が初期対象になります。補助軸や通常楕円は数値楕円の選択として扱いません。対応する楕円を複数選んだ場合は一覧の先頭を表示します。

With multiple ellipses, select one supported outline in sketch editing before opening an editor to initialize that target. Construction axes and ordinary ellipses do not count as numeric ellipse selection. Multiple supported outlines fall back to the first list item.
