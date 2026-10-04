# Contributing

Bug reports and focused pull requests are welcome. Include the FluxCAD version, FreeCAD version, Windows version, reproduction steps and expected behavior. Remove personal or confidential information from attached models and screenshots.

FluxCAD runs inside FreeCAD's Python environment. Keep Japanese and English UI strings together through `i18n.tr()`. Modeling changes should preserve selection, Undo/Redo, parameter dependencies and saved-document reopening where applicable. Test UI changes in an isolated FreeCAD profile so that existing documents and preferences remain untouched.

Run `python scripts/check_source.py` for static checks. To run the isolated application smoke test on Windows:

```powershell
.\tests\Run-Smoke.ps1 -FreeCADPath "C:\path\to\FreeCAD\bin\FreeCAD.exe" -Language ja
.\tests\Run-Smoke.ps1 -FreeCADPath "C:\path\to\FreeCAD\bin\FreeCAD.exe" -Language en
```

The test launches its own nonactivating FreeCAD window and writes only to `test-results/` by default. It does not attach to an existing FreeCAD session. A timeout reports the exact test PID; inspect that process before stopping it. Never close all FreeCAD processes to clean up a test.

`python scripts/build_release.py` builds application and source ZIPs, excluding local configuration, runtime, caches, test output and distribution folders. Developer tools are included only in the source ZIP. Review the selected files when adding new file categories. Do not add credentials, user settings, development logs, runtime binaries or unrelated models to the repository.

日本語での不具合報告・提案も受け付けます。変更は小さくまとめ、確認した操作と残る制限を記載してください。
