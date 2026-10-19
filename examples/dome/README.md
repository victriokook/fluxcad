# 中空ドームの使用例

FluxCADを起動してから `Hollow-dome-demo.FCStd` を開き、作業用に名前を付けて保存してください。初期寸法は底面30 × 42 mm、高さ12 mm、肉厚1 mmです。底面は開口しています。

「パラメータを変更」で `BaseX`（底面の横幅）、`BaseY`（底面の縦高さ）、`DomeRise`（高さ）、`Wall`（肉厚）を変更して適用します。寸法はmmで入力できます。`Wall` を0 mmにすると中実になります。

ドームの寸法編集画面では、連動中の欄はグレーになります。個別に編集する場合は「パラメータを変更」→「寸法への割り当て」で該当寸法を「固定値（式なし）」にして適用します。解除時には現在値を保持します。

プレビュー下部の「材料体積」は、実際に生成した形状の体積（mm³）です。中空の場合は空洞を除きます。密度を使った重量ではありません。肉厚・外寸を変更すると体積も更新されます。形状が成立しない入力では表示されません。肉厚上限の案内を確認して寸法を調整してください。

位置X/Y/Zはドームの底面中心を配置します。既存モデルの編集では軸の回転を保ちます。親Partに含まれる場合の位置は親の座標系に従います。「取消」ではプレビューを除去して元の表示に戻ります。

# Hollow dome example

Start FluxCAD before opening `Hollow-dome-demo.FCStd` and save a working copy. Initial dimensions are a 30 × 42 mm base, 12 mm height and 1 mm wall, with an open bottom.

Change `BaseX`, `BaseY`, `DomeRise` and `Wall` in Change Parameters. Set Wall to 0 mm for a solid dome. Linked fields are disabled in the dimension editor. To edit one independently, choose Fixed Value (No Expression) in Dimension Assignments and apply; its current value is retained.

Material volume is measured from the actual preview shape in mm³, excluding the hollow cavity. It is not weight. It updates with dimensions and disappears for invalid previews. Use the displayed wall limit when adjusting dimensions.

Position X/Y/Z places the base center; editing preserves the existing rotation. Position inside a parent Part uses its coordinate system. Cancel removes the preview and restores source visibility.
