# FullArcCAD

Formerly FluxCAD. A Japanese/English FreeCAD workspace inspired by Fusion-style workflows.

[Watch the introduction on YouTube](https://www.youtube.com/watch?v=yTPC997dG_Y) (@koyo1217)

## Current Linux preview — 0.2.242-linux-preview1

[Download Linux package](https://github.com/victriokook/fluxcad/releases/tag/v0.2.242-linux-preview1) · [English setup](docs/FullArcCAD-Linux-en.md) · [Japanese](README.md) · [72-second captioned introduction](https://github.com/victriokook/fluxcad/releases/download/v0.2.242-linux-preview1/FullArcCAD-Linux-Introduction-ja.mp4)

Linux x86_64 preview built from actual accepted0.2.242-alpha files (343 Python modules). Includes FullArcCAD branding, coordinate construction points/axes and current mesh tools. Requires separately installed official FreeCAD (tested1.1.3),Python3 and local fonts.

```sh
tar -xzf FullArcCAD-0.2.242-linux-preview1.tar.gz
cd FullArcCAD-0.2.242-linux-preview1
sh Start-FullArcCAD.sh --freecad /absolute/path/to/FreeCAD.AppImage --language en
```

Ubuntu24.04+Xvfb+Mesa: native/integration199+76 guards,JA/EN Qt78 total (38 actual QAction launches),launcher18 PASS. **Physical GUI input,Wayland,real GPU,high DPI,other distributions and full feature coverage NOT TESTED.** Exact SolidWorks BRep conversion is explicitly unavailable on Linux. No full Windows/Linux parity claim.

The video uses actual Linux virtual-display screenshots/API-driven synthetic model frames with Japanese captions,not physical interaction. No user CAD/private data/external music included.

**The attached `FullArcCAD-0.2.242-linux-preview1.tar.gz` contains the complete latest Linux implementation. GitHub automatic Source code archives/main app code remain the old Windows public baseline and are separate.** Existing Windows0.2.122 and Linux0.2.234 assets are retained. Legacy FluxCAD preference/serialization/environment identifiers remain compatible.

## Previous Windows public release

### Windows start

Install FreeCAD separately (tested here on Windows / FreeCAD 1.1.4). Download `FluxCAD-v0.2.122-alpha-windows.zip` from [Releases](https://github.com/victriokook/fluxcad/releases), extract into a new writable directory, then run `Start-FluxCAD.cmd`. Use `Start-FluxCAD.ps1 -FreeCADPath "C:\path\to\FreeCAD\bin\FreeCAD.exe"` to choose a runtime. Open an example working copy from File, or try `samples/Sample.FCStd`. Save work separately.

FreeCAD/Python/OpenCASCADE are not bundled. The source ZIP omits the 149 MB cadmpeg executable; the Windows distribution includes its pinned, locally executed decoder for the experimental native SolidWorks path.

## Windows public-release scope

Sketch curves/constraints, numeric ellipse tools, snapping and nested/crossing profiles; solid extrusion/revolve/sweep/loft, holes, edge features, shell, booleans, scale and alignment; plastic ribs/bosses/gussets/snap hooks/draft and hollow domes; SheetMetal base/flange/unfold; surfaces, meshes, drawings/exports; parameters/CSV, assemblies, interference, animation/image sequences and example working copies.

**SolidWorks import is experimental and incomplete.** Saved display meshes and a constrained native-solid path are implemented, but arbitrary files/configurations, colors and feature history are not certified. Keep source documents unchanged and verify imported results independently. Shipping code does not certify full compatibility.

See [validation scope and limits](docs/releases/0.2.122-alpha.md) and [third-party notices](THIRD_PARTY_NOTICES.md). SheetMetal native dialogs may retain English. Complex sheet metal, all feature combinations and all selection failures are not certified.

This package includes the accepted missing-cell and tiny-area feedback fixes. Unaccepted browser.py/fluxcad.py performance candidates, machine-reconstruction/reference CAD, personal settings and caches are excluded. The 99 application modules are checked against accepted hashes. Native API checks and physical UI evidence are explicitly distinguished.

For developers: `python scripts/check_source.py`; isolated FreeCAD smoke tests via `tests/Run-Smoke.ps1`. ZIPs include file manifests and SHA256SUMS.txt. FluxCAD is independent of Autodesk and the FreeCAD project.
