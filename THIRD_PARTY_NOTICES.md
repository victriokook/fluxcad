# Third-party software / 第三者ソフトウェア

The MIT license in this repository applies to FluxCAD's original code and assets. It does not change the license of FreeCAD, its code, its artwork or its dependencies.

## FreeCAD

FluxCAD runs inside a separately installed FreeCAD. It uses the public Python/GUI interfaces, native modeling objects, Sketcher, Part, TechDraw and modules such as FreeCAD's bundled BOPTools. Native command icons are loaded from the installed FreeCAD resource system at runtime.

- Project and source: https://github.com/FreeCAD/FreeCAD
- Licensing information: https://www.freecad.org/contributing.php?lang=eng
- License: GNU Lesser General Public License (LGPL), as specified by the FreeCAD version being used.

This package does not redistribute FreeCAD binaries, Python, OpenCASCADE, Qt/PySide, Coin/pivy or copies of FreeCAD's native icon resources. They come from the user's FreeCAD installation and retain their respective licenses and notices. If a distributor later bundles a FreeCAD runtime, they must separately retain and satisfy its applicable license and source-distribution requirements; this document is not a substitute for those notices.

## FluxCAD assets

The SVG files under `icons/` and `templates/` are the project's own vector assets. The examples under `samples/` are project-generated demonstration models. The drawing-detail development sample, which embeds native hatch resources, is not included in this initial package. Screenshots document FluxCAD running inside FreeCAD and may show FreeCAD's native interface.

FreeCAD, Autodesk and Fusion are names of their respective projects or owners. Naming them describes the runtime dependency and workflow inspiration; no affiliation or endorsement is claimed.

日本語: FluxCADのMITライセンスはFreeCADや依存ライブラリへ適用されるものではありません。FreeCAD本体は同梱していません。将来ポータブル版などを同梱する場合は、その版に含まれるライセンス・表示・ソース提供条件を別途確認してください。
