# 樹脂ケースの編集から出力まで

FluxCADを起動してから使用例を開き、名前を付けて作業用コピーを保存してください。

| 使用例 | 確認できる内容 |
|---|---|
| Parametric-enclosure.FCStd | ケース・ボス・貫通穴・三角リブ・爪の寸法連動 |
| Drafted-enclosure.FCStd | ボスの抜き勾配とCSVパラメータ |
| Instanced-enclosures.FCStd | 同じケースを共有する2部品の位置・角度と連動 |
| Tapered-rib-demo.FCStd | リブ・ボスの抜き勾配と爪高さの連動 |

## 操作例

1. `Parametric-enclosure.FCStd` の作業用コピーを開きます。
2. 「管理」→「パラメータを変更」で `BossHeight` を18 mmにして適用します。ボスの高さと、それに連動する爪の高さ（20 mm）が変わります。Undo/Redoで一括して戻せます。
3. 保存して再読込します。寸法と式はモデルに保存されています。
4. 「管理」からSTEP/STLの書き出しを開きます。対象は表示中の形状です。履歴の途中形状を表示している場合は、出力したい最終形状の表示を確認してください。
5. 「デザイン ▼」→「レンダリング」で等角投影・白背景などを選び、プレビューしてPNGを保存します。寸法変更後の形状を画像にできます。

この操作例では、保存再読込、STEP再読込の体積・外形寸法、PNG生成前後の視点・選択・表示・履歴保持を検証しています。プラスチック加工の寸法編集は下部の履歴から開けます。式で連動する欄がグレーの場合は「パラメータを変更」で調整します。

# Plastic case: editing through export

Start FluxCAD before opening an example, then save a working copy. `Parametric-enclosure.FCStd` demonstrates linked boss, through-hole, gusset and snap dimensions. `Drafted-enclosure.FCStd` adds boss draft; `Instanced-enclosures.FCStd` shares a case between two placed components; `Tapered-rib-demo.FCStd` demonstrates rib/boss draft and linked snap height.

In Change Parameters, set BossHeight to 18 mm in the parametric example. The dependent snap height becomes 20 mm. Undo/Redo restores both together. Save and reopen to retain dimensions and expressions.

Use Manage to export STEP/STL; export includes visible geometry, so check final-feature visibility when inspecting historical features. Use Design → Rendering for an isometric PNG. The verified workflow preserves camera, selection, visibility and history during image generation. STEP reimport matches the edited material volume and bounds. Edit plastic features from the history; linked fields are adjusted through Change Parameters.
