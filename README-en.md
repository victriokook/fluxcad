# FluxCAD

A Japanese/English workspace for FreeCAD with compact ribbon and modeling tools. Available as a Windows alpha and an experimental Linux x86_64 preview.

[日本語](README.md) · [User guide](docs/User-guide-en.md) · [Changelog](CHANGELOG.md)

**Windows public release: 0.2.122-alpha (2026-10-19). Linux preview: 0.2.234-linux-preview1 (2026-10-22).** The Windows release is a public baseline, replacing the old 0.1 preview as the development baseline. This remains an alpha, not a claim that every feature or workflow is complete.

## Linux preview

[Download Linux preview](https://github.com/victriokook/fluxcad/releases/tag/v0.2.234-linux-preview1) · [Linux setup](docs/Linux-preview-en.md)

Tested on Linux x86_64 / FreeCAD 1.1.3 in an Ubuntu 24.04 container with Xvfb and Mesa: 18 launcher tests, 66 native cases + 12 guards, 15 CAD integration/save cases + 6 guards, and 16 Japanese/English Qt cases each (10 actual QAction launches per language). **Physical GUI input, Wayland/GPU/high-DPI, full feature coverage and other distributions remain untested.**

| Distribution | Version and launch | Validation and limits |
|---|---|---|
| Windows | [0.2.122-alpha](https://github.com/victriokook/fluxcad/releases/tag/v0.2.122-alpha), `Start-FluxCAD.cmd` | Existing public release; see its scoped evidence below |
| Linux preview | [0.2.234-linux-preview1](https://github.com/victriokook/fluxcad/releases/tag/v0.2.234-linux-preview1), `sh Start-FluxCAD.sh --freecad /path/to/FreeCAD.AppImage --language en` | Selected native and Japanese/English Qt tests passed; physical GUI untested; exact SolidWorks BRep import unavailable |

The Linux package is based on the actual accepted 0.2.234-alpha snapshot of 321 Python modules. A local-Qwen-generated launcher was reviewed, with local font detection and isolated settings added. FreeCAD and fonts are separate. **The attached tar.gz contains the complete Linux implementation source. GitHub's automatic Source code archives and main's Windows launch instructions are separate.** Full Windows/Linux feature parity is not claimed.

## Windows start

Install FreeCAD separately (tested here on Windows / FreeCAD 1.1.4). Download `FluxCAD-v0.2.122-alpha-windows.zip` from [Releases](https://github.com/victriokook/fluxcad/releases), extract into a new writable directory, then run `Start-FluxCAD.cmd`. Use `Start-FluxCAD.ps1 -FreeCADPath "C:\path\to\FreeCAD\bin\FreeCAD.exe"` to choose a runtime. Open an example working copy from File, or try `samples/Sample.FCStd`. Save work separately.

FreeCAD/Python/OpenCASCADE are not bundled. The source ZIP omits the 149 MB cadmpeg executable; the Windows distribution includes its pinned, locally executed decoder for the experimental native SolidWorks path.

## Windows public-release scope

Sketch curves/constraints, numeric ellipse tools, snapping and nested/crossing profiles; solid extrusion/revolve/sweep/loft, holes, edge features, shell, booleans, scale and alignment; plastic ribs/bosses/gussets/snap hooks/draft and hollow domes; SheetMetal base/flange/unfold; surfaces, meshes, drawings/exports; parameters/CSV, assemblies, interference, animation/image sequences and example working copies.

**SolidWorks import is experimental and incomplete.** Saved display meshes and a constrained native-solid path are implemented, but arbitrary files/configurations, colors and feature history are not certified. Keep source documents unchanged and verify imported results independently. Shipping code does not certify full compatibility.

See [validation scope and limits](docs/releases/0.2.122-alpha.md) and [third-party notices](THIRD_PARTY_NOTICES.md). SheetMetal native dialogs may retain English. Complex sheet metal, all feature combinations and all selection failures are not certified.

This package includes the accepted missing-cell and tiny-area feedback fixes. Unaccepted browser.py/fluxcad.py performance candidates, machine-reconstruction/reference CAD, personal settings and caches are excluded. The 99 application modules are checked against accepted hashes. Native API checks and physical UI evidence are explicitly distinguished.

For developers: `python scripts/check_source.py`; isolated FreeCAD smoke tests via `tests/Run-Smoke.ps1`. ZIPs include file manifests and SHA256SUMS.txt. FluxCAD is independent of Autodesk and the FreeCAD project.
