param(
  [string]$Python = 'python',
  [string]$Version = '0.12.1',
  [string]$OutputsRoot = '',
  [string]$BuildRoot = ''
)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
if (!$OutputsRoot) { $OutputsRoot = Join-Path $ProjectRoot 'dist' }
if (!$BuildRoot) { $BuildRoot = Join-Path $ProjectRoot 'build/photo-manager' }
$OutputsRoot = [System.IO.Path]::GetFullPath($OutputsRoot)
$BuildRoot = [System.IO.Path]::GetFullPath($BuildRoot)
$BundleName = '洗衣机管理器-Windows-' + $Version
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
