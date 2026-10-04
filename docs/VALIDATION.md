# Validation / 公開版の検証

Environment: Windows, FreeCAD 1.1.3R20260725. Package: 0.1.0-alpha. Date: 2026-10-04.

| Run | Result |
| --- | --- |
| Public source, Japanese | PASS: 26 checks |
| Public source, English | PASS: 26 checks |
| Source ZIP extracted into a separate path containing spaces, Japanese | PASS: 26 checks |

The 26 checks include one reopen/recompute check for each of the 20 sample documents. Japanese and English sample PNGs were also visually inspected.

## Scope

The public package was tested with separate FreeCAD settings and temporary documents, without changing the user's running FreeCAD session. The included smoke test exercises the following in Japanese and English:

- Start `FluxCAD.FCMacro` and confirm imports come from this package.
- Build a solid box and through hole; compare the resulting volume with the calculated value.
- Extrude a constrained rectangle, change its width and check the updated volume.
- Undo and redo a modeling operation.
- Save, reopen and recompute an FCStd document.
- Open and recompute each of the 20 included sample documents; check object state, shape validity and sample license metadata.
- In sketch editing, enter 0.5 mm while automatic spacing is 5 mm, across workspace refreshes; confirm fixed spacing, native Sketcher grid spacing and translated controls.
- Render the included sample using FreeCAD's offscreen image renderer.

See [CONTRIBUTING](../CONTRIBUTING.md) to repeat the checks. `scripts/check_source.py` checks Python syntax, relative documentation links, SVG syntax, sample archive integrity and metadata, and common personal-path or credential patterns. `scripts/build_release.py` validates ZIP contents against SHA-256 manifests.

This is an initial alpha, not an exhaustive certification of every modeling command or every possible shape. Other operating systems and FreeCAD versions are unverified. Rendering a sample does not verify every window layout, display scale or graphics driver. Files containing custom dependencies should be opened after starting FluxCAD.

## 日本語

公開用フォルダを独立したFreeCAD設定で検証しています。日本語・英語それぞれで、起動、形状と体積、寸法変更への追従、Undo/Redo、保存・再読込、同梱サンプル20点の再計算、5 mm自動グリッドから0.5 mm固定への変更、サンプル画像の出力を確認します。

全機能・全形状や、すべての画面倍率・GPU環境を網羅した検証ではありません。初回試用版として、利用する機能を保存済みのモデルのコピーで確認してください。
