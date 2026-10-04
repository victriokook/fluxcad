param(
    [Parameter(Mandatory=$true)][string]$FreeCADPath,
    [ValidateSet('ja','en')][string]$Language = 'ja',
    [string]$OutputDirectory,
    [int]$TimeoutSeconds = 180
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path -LiteralPath $FreeCADPath -PathType Leaf)) { throw 'FreeCAD executable was not found.' }
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $root ('test-results/smoke-'+$Language) }
$testOutput = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $testOutput | Out-Null
$testConfig = Join-Path $testOutput 'config'
New-Item -ItemType Directory -Force -Path $testConfig | Out-Null
$names = @('FREECAD_USER_HOME','FREECAD_USER_DATA','FREECAD_USER_CONFIG','FREECAD_USER_TEMP','TEMP','TMP','FLUXCAD_TEST_OUTPUT','FLUXCAD_TEST_LANGUAGE')
$previous = @{}
foreach($name in $names){$previous[$name]=[Environment]::GetEnvironmentVariable($name,'Process')}
try {
    foreach($name in @('FREECAD_USER_HOME','FREECAD_USER_DATA','FREECAD_USER_CONFIG','FREECAD_USER_TEMP','TEMP','TMP')) {
        [Environment]::SetEnvironmentVariable($name,$testConfig,'Process')
    }
    $env:FLUXCAD_TEST_OUTPUT=$testOutput
    $env:FLUXCAD_TEST_LANGUAGE=$Language
    $reportPath=Join-Path $testOutput 'report.json'
    if(Test-Path -LiteralPath $reportPath){Remove-Item -LiteralPath $reportPath}
    $macro=Join-Path $PSScriptRoot 'smoke.FCMacro'
    $process=Start-Process -FilePath $FreeCADPath -WindowStyle Hidden -ArgumentList @('--user-cfg',('"'+$testConfig+'/user.cfg"'),('"'+$macro+'"')) -RedirectStandardError (Join-Path $testOutput 'stderr.log') -RedirectStandardOutput (Join-Path $testOutput 'stdout.log') -PassThru
    if(-not $process.WaitForExit($TimeoutSeconds*1000)){throw ('Smoke test timeout; isolated FreeCAD PID: '+$process.Id)}
    $report=Get-Content -LiteralPath $reportPath -Raw -Encoding UTF8 | ConvertFrom-Json
    @{status=$report.status;language=$Language;checks=$report.checks.Count;error=$report.error} | ConvertTo-Json -Compress
    if($report.status -ne 'PASS'){throw 'FreeCAD smoke test failed. See report.json.'}
} finally {
    foreach($name in $names){[Environment]::SetEnvironmentVariable($name,$previous[$name],'Process')}
}
