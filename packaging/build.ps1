param([string]$Python = 'python', [string]$Version = '0.5')
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$OutputsRoot = Split-Path -Parent $ProjectRoot
$WorkspaceRoot = Split-Path -Parent $OutputsRoot
$BuildRoot = Join-Path $WorkspaceRoot 'work/photo-manager-build'
$BundleName = '片集-Windows-' + $Version
$PreviousBundleName = $env:PIANJI_BUNDLE_NAME
$env:PIANJI_BUNDLE_NAME = $BundleName
Push-Location $ProjectRoot
try {
  & $Python packaging/collect_licenses.py licenses
  if ($LASTEXITCODE -ne 0) { throw 'License collection failed' }
  & $Python -m pip freeze | Out-File -Encoding utf8 requirements-lock.txt
  & $Python -m PyInstaller --noconfirm --distpath $OutputsRoot --workpath $BuildRoot packaging/pianji.spec
  if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
  $BundleRoot = Join-Path $OutputsRoot $BundleName
  Copy-Item -LiteralPath README.md -Destination (Join-Path $BundleRoot '使用说明.md') -Force
  Copy-Item -LiteralPath docs -Destination $BundleRoot -Recurse -Force
} finally { $env:PIANJI_BUNDLE_NAME = $PreviousBundleName; Pop-Location }
