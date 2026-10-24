# Changelog

## 0.2.242-alpha Windows — 2026-10-24

Published the current accepted343-module Windows/source ZIPs with FullArcCAD branding,compatible launchers,pinned decoder/licenses and55 public examples. WindowsFreeCAD1.1.4 selected package tests native19+6/JAENQt46total/18actualQAction,launcher quoting,ZIP hashes and extraction PASS. Physical GUI/full feature coverage untested. Linux0.2.242 and previousWindows releases retained. See [Windows scope](docs/releases/0.2.242-alpha-windows.md).


## 0.2.242-linux-preview1 — 2026-10-24

Renamed display to FullArcCAD;new current Linux preview with343 accepted modules,coordinate points/axes and mesh tools. RealLinux selected native199+76/JAENQt78 total/launcher18 PASS;physical GUI untested. Includes new72-second Japanese-caption introduction. Previous public assets retained;current implementation is in attached tar.gz. See [release scope](docs/releases/0.2.242-linux-preview1.md).


## 0.2.234-linux-preview1 — 2026-10-22

Experimental Linux x86_64 package based on accepted 0.2.234-alpha, separately from the Windows 0.2.122 public baseline. Local-Qwen launcher, isolated settings, local font discovery, explicit refusal of Windows-only exact SolidWorks BRep conversion. Linux FreeCAD1.1.3: launcher18/native66+12/integration15+6/JAENQt16each PASS under Ubuntu24.04+Xvfb+Mesa. Physical desktop/GPU/Wayland/high-DPI and full feature parity untested. See [Linux release scope](docs/releases/0.2.234-linux-preview1.md).


## 0.2.122-alpha — 2026-10-19

Fresh public package of accepted current functionality: 99 runtime modules; plastic/dome/ellipse, sheet metal and example dependencies, document/assembly/visualization tools, and scoped region-selection fixes. SolidWorks paths are explicitly experimental and incomplete. Prior unaccepted performance candidates and machine/reference CAD are excluded. Entry macro prioritizes its own workspace. See docs/releases/0.2.122-alpha.md for exact validation.


## 0.1.0-alpha — 2026-10-04

Initial public-preview package for Windows and a separately installed FreeCAD 1.1.3.

- Compact Japanese/English ribbon, browser, history and movable panels.
- Sketch and solid modeling, mesh operations, construction geometry, basic components/joints, native surface and drawing workflows.
- Region selection for rectangle/arc/B-spline boundaries with linked extrusion.
- Stronger sketch grid snapping with existing-geometry priority.
- Editable grid spacing in automatic mode, decimal-entry preservation and fixed 0.1/0.5/1 mm presets.
- Public documentation, issue templates, isolated smoke tests and reproducible ZIP packaging.

This is an alpha release. The feature-specific limitations in the user guides still apply. The package excludes development logs, user settings, private working models, unfinished BlendCurve integration and the FreeCAD runtime.
