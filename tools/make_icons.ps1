# Draws the toolbar icons (installer\icons) and docs\icon-256.png by running
# tools/icons/make_icons.py inside 3ds Max (3dsmaxbatch, nothing is shown).
#
#   pwsh tools/make_icons.ps1
param([int]$Year = 2026)

$root = Split-Path -Parent $PSScriptRoot
$env:BD_ROOT = $root
$env:BD_TEST = Join-Path $root "tools\icons\make_icons.py"
$exe = "C:\Program Files\Autodesk\3ds Max $Year\3dsmaxbatch.exe"
New-Item -ItemType Directory -Force (Join-Path $root "tests\out") | Out-Null
& $exe (Join-Path $root "tests\run_in_max.ms") -log (Join-Path $root "tests\out\icons_$Year.log") 2>&1 | Out-Null

Get-Content (Join-Path $root "tests\out\make_icons.log")
