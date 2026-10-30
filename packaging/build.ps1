param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$OutputsRoot = Split-Path -Parent $ProjectRoot
$WorkspaceRoot = Split-Path -Parent $OutputsRoot
$BuildRoot = Join-Path $WorkspaceRoot 'work/photo-manager-build'
Push-Location $ProjectRoot
try {
  & $Python packaging/collect_licenses.py licenses
  if ($LASTEXITCODE -ne 0) { throw 'License collection failed' }
  & $Python -m pip freeze | Out-File -Encoding utf8 requirements-lock.txt
  & $Python -m PyInstaller --noconfirm --distpath $OutputsRoot --workpath $BuildRoot packaging/pianji.spec
  if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
  $BundleRoot = Join-Path $OutputsRoot '片集-Windows'
  Copy-Item -LiteralPath README.md -Destination (Join-Path $BundleRoot '使用说明.md') -Force
  Copy-Item -LiteralPath docs -Destination $BundleRoot -Recurse -Force
} finally { Pop-Location }
