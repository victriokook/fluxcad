param([string]$FreeCADPath)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
if (-not $FreeCADPath) {
    $candidates = @(Get-ChildItem 'C:\Program Files\FreeCAD*\bin\FreeCAD.exe' -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | ForEach-Object FullName)
    $candidates += @(
        (Join-Path $root 'runtime\bin\FreeCAD.exe'),
        (Join-Path $root '..\..\work\runtime\FreeCAD_1.1.3-Windows-x86_64-py311\bin\FreeCAD.exe')
    )
    $FreeCADPath = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $FreeCADPath) {
    Write-Host 'FreeCAD not found. Run: .\Start-FluxCAD.ps1 -FreeCADPath "C:\path\bin\FreeCAD.exe"'
    Read-Host 'Press Enter to close'
    exit 1
}
$configDir = Join-Path $root 'config'
New-Item -ItemType Directory -Force -Path $configDir | Out-Null
$env:FREECAD_USER_HOME = $configDir
$env:FREECAD_USER_DATA = $configDir
$env:FREECAD_USER_CONFIG = $configDir
$env:FREECAD_USER_TEMP = Join-Path $configDir 'temp'
$macro = Join-Path $root 'FluxCAD.FCMacro'
$config = Join-Path $configDir 'user.cfg'
Start-Process -FilePath $FreeCADPath -WindowStyle Normal -ArgumentList @('--user-cfg', ('"'+$config+'"'), ('"'+$macro+'"'))
