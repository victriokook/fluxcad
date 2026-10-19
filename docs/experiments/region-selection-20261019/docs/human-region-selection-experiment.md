# 画面操作による領域選択実験

大量の機械複製は停止し、自動継続もPAUSEDのままです。評価対象は、人間と同じ描画・クリック選択・加工確定で作れるかです。APIやQtTestによる選択は画面操作合格の代わりにしません。

2026-10-19の最初の実験では、空の文書から長方形ツールで三重の入れ子を描き、第四の長方形で内側二つを横切りました。16本の線と交点で構成される6領域のうち、最小長方形の上半分は選択できず、下半分は選択できました。

交差輪郭の既存領域に`inputs`がある場合、入れ子セル追加を省く分岐が原因でした。既存4領域の辞書とキーを維持し、全輪郭の厳密な平面分割から未被覆の2領域だけを追加しました。部分重複はエラーとし、推測で選択対象を置き換えません。

修正後、同じ保存スケッチの同じ画面座標をクリックすると上半分だけが選択され、押し出しパネルから12mmの加工を確定できました。ツールバーのUndo／Redo、他の凹形・細い領域のクリック、保存、別プロセスでの全再計算を確認しました。

実操作記録：`test-results/human-region-selection/physical-ui-review.json`。再現例と修正後結果は同フォルダの`Nested-Crossing-UI-Repro.FCStd`、`Nested-Crossing-UI-Fixed.FCStd`です。6領域すべての押し出しと曲線回帰はAPIによる補助試験であり、物理UI試験と区別しています。

今後は、円弧・接線・微小領域・開いた線による分割・面上スケッチ・複数加工を画面から追加して複雑にします。失敗した段階の文書とクリックを保存し、修正前後に同じ操作を繰り返します。部品数を成果指標にはしません。今回の修正を全選択不具合の解決とは扱いません。


0.2.121：実画面だけで円弧・接線スロット・微小領域・2段の面上スケッチを追加し、3スケッチ34要素、初回押し出し＋追加4加工を保存。新たな選択不能は未再現。正の微小面積が0.00 mm²になる表示を修正し、選択表示と加工一覧の0.00146432 mm²、切削確定、Undo/Redo、保存を実操作確認。保存再読込のnative検査は補助証拠。browser.py/fluxcad.pyは未採用のまま。


0.2.121: Physical UI drawing extended the experiment to arcs, a tangent slot, tiny cells and two face-attached sketches: 3 sketches, 34 geometries, initial extrusion plus four operations. No new unselectable cell was reproduced. Fixed positive tiny areas appearing as 0.00 mm²; physical selection/status/list showed 0.00146432 mm², followed by Cut confirmation, toolbar Undo/Redo and Save. Native saved-model inspection is supplemental. Prior browser.py/fluxcad.py changes remain unadopted.
