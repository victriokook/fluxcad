param([string]$FreeCADPath)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
if (-not $FreeCADPath) {
    $candidates = @()
    if ($env:ProgramFiles) {
        $candidates += @(Get-ChildItem (Join-Path $env:ProgramFiles 'FreeCAD*\bin\FreeCAD.exe') -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending | ForEach-Object FullName)
    }
    $candidates += (Join-Path $root 'runtime\bin\FreeCAD.exe')
    $FreeCADPath = $candidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
}
if (-not $FreeCADPath -or -not (Test-Path -LiteralPath $FreeCADPath -PathType Leaf)) {
    Write-Host 'FreeCAD not found. Install FreeCAD or run:'
    Write-Host '.\Start-FluxCAD.ps1 -FreeCADPath "C:\path\to\FreeCAD\bin\FreeCAD.exe"'
    Read-Host 'Press Enter to close'
    exit 1
}
$configDir = Join-Path $root 'config'
New-Item -ItemType Directory -Force -Path $configDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $configDir 'temp') | Out-Null
$env:FREECAD_USER_HOME = $configDir
$env:FREECAD_USER_DATA = $configDir
$env:FREECAD_USER_CONFIG = $configDir
$env:FREECAD_USER_TEMP = Join-Path $configDir 'temp'
$macro = Join-Path $root 'FluxCAD.FCMacro'
$config = Join-Path $configDir 'user.cfg'
Start-Process -FilePath $FreeCADPath -WindowStyle Normal -ArgumentList @('--user-cfg', ('"'+$config+'"'), ('"'+$macro+'"'))
