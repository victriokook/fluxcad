# FullArcCAD Linux preview 0.2.242-preview1

Formerly FluxCAD. A separate Linux x86_64 preview from the actual accepted0.2.242-alpha runtime (343 Python modules). Includes FullArcCAD branding, coordinate construction points/axes and the current mesh tools. Not a finished product or a full feature-parity guarantee.

Install official FreeCAD Linux separately (tested1.1.3) and Python3. No runtime or fonts bundled.

```sh
sha256sum -c FullArcCAD-0.2.242-linux-preview1.tar.gz.sha256
tar -xzf FullArcCAD-0.2.242-linux-preview1.tar.gz
cd FullArcCAD-0.2.242-linux-preview1
sh Start-FullArcCAD.sh --freecad /absolute/path/to/FreeCAD.AppImage --language en
```

Make the AppImage executable. Without FUSE, extract it using FreeCAD's official procedure and pass the extracted squashfs-root/AppRun. No automatic runtime download. `--language ja` selects Japanese, `--check` checks paths without writing settings, `--state-dir /absolute/private/path` isolates state. Legacy fluxcad state paths, FLUXCAD_* environment variables, preferences and Start-FluxCAD.sh are retained for compatibility.

Linux Ubuntu24.04+Xvfb+Mesa: native199+76 guards, JA/EN Qt78 total (38 actual QAction launches), launcher18 PASS. See LINUX-VALIDATION.json and linux-tests/results. Selected tests only. **Physical GUI input,Wayland,real GPU,high DPI and other distributions NOT TESTED.** Unadopted root performance branches excluded. Exact SolidWorks BRep conversion is explicitly unavailable on Linux;use STEP. Saved display-mesh import exists but is untested on Linux. Local Japanese-capable fonts such as Noto CJK are required;replace Windows-only font references when regenerating text.

The attached tar.gz is the complete current Linux source distribution. GitHub's automatic source archives refer to the repository baseline and are separate. MIT;third-party notices retained. Not an Autodesk/Fusion product.
