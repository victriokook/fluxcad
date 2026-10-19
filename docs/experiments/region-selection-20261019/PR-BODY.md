# Fix nested/crossing region selection and tiny-area feedback

Nested and crossing rectangle contours could omit two bounded cells from the picker. Preserve the existing four region dictionaries/keys and append only uncovered exact planar cells. Also show positive areas below 0.01 mm² with six significant digits instead of rounding them to 0.00 in the selection status and Extrude list.

## Validation

- Physical Windows UI: drew the original 16-line sketch from an empty document, reproduced the missing upper cell, then selected the same saved cell at the same pixel and confirmed a 12 mm extrusion after the fix. Toolbar Undo/Redo and Save passed.
- Extended physical UI: arcs, tangent slot, circle intersections, tiny cells and two face-attached sketches. Three sketches / 34 geometries, initial extrusion plus three Cuts and one Join. Tiny selection/list feedback showed 0.00146432 mm²; reverse 0.02 mm Cut, Undo/Redo and Save passed.
- Supplemental native inspection: six-cell profile persistence and curved regressions; final complex file full recompute, valid single-solid results, expected placements and volume. These API checks do not substitute for physical UI selection.
- No new unselectable cell was reproduced during the complex extension. This does not establish that all selection failures are fixed. English labels have static fallback coverage only.

## Scope

Only three runtime modules are included. browser.py/fluxcad.py performance candidates, mass machine reconstruction, source STEP/BRep reference data, temporary native homes, backups and raw logs are excluded. Four small experiment-created FCStd documents are included (about 125 KiB total).

The source helpers were generated locally with localQwen, reviewed by Codex, and wired into the existing picker/labels. Exact proposals are included. Source baselines and SHA256 checks are in MANIFEST.json. selection-fixes.patch targets the local accepted pre-fix baseline; compare against the destination repository before applying.

The full workspace release index is intentionally omitted because it contains unrelated working-tree candidate hashes. No repository-wide release version is changed by this payload.
