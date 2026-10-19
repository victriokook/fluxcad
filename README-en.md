# FluxCAD

A Japanese/English Windows workspace for FreeCAD with compact ribbon and modeling tools.

[日本語](README.md) · [User guide](docs/User-guide-en.md) · [Changelog](CHANGELOG.md)

**0.2.122-alpha — 2026-10-19. A fresh public package of the currently accepted implementation**, replacing the old 0.1 preview as the development baseline. This remains an alpha, not a claim that every feature or workflow is complete.

## Start

Install FreeCAD separately (tested here on Windows / FreeCAD 1.1.4). Download `FluxCAD-v0.2.122-alpha-windows.zip` from [Releases](https://github.com/victriokook/fluxcad/releases), extract into a new writable directory, then run `Start-FluxCAD.cmd`. Use `Start-FluxCAD.ps1 -FreeCADPath "C:\path\to\FreeCAD\bin\FreeCAD.exe"` to choose a runtime. Open an example working copy from File, or try `samples/Sample.FCStd`. Save work separately.

FreeCAD/Python/OpenCASCADE are not bundled. The source ZIP omits the 149 MB cadmpeg executable; the Windows distribution includes its pinned, locally executed decoder for the experimental native SolidWorks path.

## Implemented scope

Sketch curves/constraints, numeric ellipse tools, snapping and nested/crossing profiles; solid extrusion/revolve/sweep/loft, holes, edge features, shell, booleans, scale and alignment; plastic ribs/bosses/gussets/snap hooks/draft and hollow domes; SheetMetal base/flange/unfold; surfaces, meshes, drawings/exports; parameters/CSV, assemblies, interference, animation/image sequences and example working copies.

**SolidWorks import is experimental and incomplete.** Saved display meshes and a constrained native-solid path are implemented, but arbitrary files/configurations, colors and feature history are not certified. Keep source documents unchanged and verify imported results independently. Shipping code does not certify full compatibility.

See [validation scope and limits](docs/releases/0.2.122-alpha.md) and [third-party notices](THIRD_PARTY_NOTICES.md). SheetMetal native dialogs may retain English. Complex sheet metal, all feature combinations and all selection failures are not certified.

This package includes the accepted missing-cell and tiny-area feedback fixes. Unaccepted browser.py/fluxcad.py performance candidates, machine-reconstruction/reference CAD, personal settings and caches are excluded. The 99 application modules are checked against accepted hashes. Native API checks and physical UI evidence are explicitly distinguished.

For developers: `python scripts/check_source.py`; isolated FreeCAD smoke tests via `tests/Run-Smoke.ps1`. ZIPs include file manifests and SHA256SUMS.txt. FluxCAD is independent of Autodesk and the FreeCAD project.
