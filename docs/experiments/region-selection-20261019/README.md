# Region selection experiment — 2026-10-19

**Draft integration evidence. This directory does not modify the public application's runtime.**

The public repository is 0.1.0-alpha (base `53c8d98`); the physically verified local workspace is 0.2.121-alpha. The nested-cell fix depends on local baseline helpers (`nested_regions`, `_geometry`, `_cells`, `_reference_error`) that do not exist in the public base. Replacing the public runtime with these three snapshots would therefore be unsafe. Import/review the prerequisite runtime changes or backport and revalidate before merging a runtime fix. The local physical results are not acceptance evidence for this older public application.

Contents:

- `selection-fixes.patch`: exact scoped diff against the recorded local pre-fix sources.
- Three Python snapshots: reviewed implementation context, not installed modules.
- `qwen-generation/plastic/`: the two exact locally generated helper proposals.
- `test-results/human-region-selection/`: physical UI records, separately identified supplemental native checks, and four small experiment-created models. No machine/reference STEP or BRep data.
- `MANIFEST.json`: baseline hashes and payload integrity hashes.
- [Experiment narrative](docs/human-region-selection-experiment.md).
- [Validation and limits](PR-BODY.md).

The complex model uses three sketches / 34 geometries and the original extrusion plus four further operations. No new missing selection was reproduced in the complex extension; the additional fix corrects misleading zero-area feedback only. English fallback was not physically exercised. Some records retain local workspace paths as historical provenance, not portable execution commands. Their `visible: false` fields come from a headless inspection without GUI view objects, not from observed UI invisibility.

Public source validation: `python scripts/check_source.py` from the repository root. Run `python docs/experiments/region-selection-20261019/check_payload.py` for payload hashes, patch scope and pure numeric formatting checks. Neither command simulates physical mouse selection.

Before a runtime integration is accepted, rerun the documented physical draw → click → Extrude → Confirm sequence on the integrated public source in an isolated profile, including save/reopen and Undo/Redo. Do not use API selection as a substitute.
