# FluxCAD Linux preview

Download the attached `FluxCAD-0.2.234-linux-preview1.tar.gz` and `.sha256` from the [Linux preview release](https://github.com/victriokook/fluxcad/releases/tag/v0.2.234-linux-preview1).

See [Linux setup in Japanese](Linux-preview-ja.md) for Japanese installation instructions, scope and limitations.

Extract the archive, install/download official Linux FreeCAD 1.1.x, then run:

```sh
sh Start-FluxCAD.sh --freecad /absolute/path/to/FreeCAD.AppImage --language en
```

Requires Linux and system Python 3. FreeCAD, fonts and user CAD files are not bundled. The launcher discovers an explicit `--freecad` or `FLUXCAD_FREECAD`, then `runtime/FreeCAD.AppImage`, `runtime/AppRun`, or `FreeCAD`/`freecad` on PATH. Use `--check` for a side-effect-free launch-path check.

Settings are isolated under `$XDG_STATE_HOME/fluxcad` or `~/.local/state/fluxcad`; `--state-dir` accepts an absolute override. The launch environment removes PYTHONHOME/PYTHONPATH to avoid embedded-Python ABI conflicts. Local CJK fonts are detected; use `FLUXCAD_FONT` or the font picker to choose a font. Saved text may still refer to Windows fonts and need a local replacement for regeneration.

This is a preview based on the actual accepted 0.2.234 runtime, not the root's unadopted performance candidates. Exact SolidWorks BRep import depends on Windows-only decoder/workers and is explicitly unavailable; use standard STEP imports. Saved-display-mesh import remains separate and untested on Linux. Example CAD documents are not included.

`LINUX-VALIDATION.json` (inside the downloaded Linux package) distinguishes actual Linux native and Japanese/English Qt test results from physical desktop verification. Virtual-display rendering is not physical GUI input. Full feature parity, physical mouse/keyboard navigation, Wayland/GPU/high-DPI and other distributions are not certified by the selected smoke tests.

For synthetic tests use `--smoke native`, `--smoke integration`, `--smoke ja`, or `--smoke en`, with an absolute `--report-dir`. Each launches a dedicated process, creates only synthetic documents and closes that process; never load the smoke macro in your existing FreeCAD session. A headless system needs Xvfb or another display.

FluxCAD is MIT-licensed. Retained addon and reader licenses are included. FreeCAD and fonts have their own licenses. This is not an Autodesk/Fusion product.
