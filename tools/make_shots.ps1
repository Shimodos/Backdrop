# Renders the README screenshots into docs\shots by running
# tools/shots/make_shots.py inside 3ds Max (3dsmaxbatch, nothing is shown).
#
#   pwsh tools/make_shots.ps1            # 3ds Max 2026
#   pwsh tools/make_shots.ps1 -Year 2024
param([int]$Year = 2026)

$root = Split-Path -Parent $PSScriptRoot
$env:BD_ROOT = $root
$env:BD_TEST = Join-Path $root "tools\shots\make_shots.py"
$exe = "C:\Program Files\Autodesk\3ds Max $Year\3dsmaxbatch.exe"
New-Item -ItemType Directory -Force (Join-Path $root "tests\out") | Out-Null
& $exe (Join-Path $root "tests\run_in_max.ms") -log (Join-Path $root "tests\out\shots_$Year.log") 2>&1 | Out-Null

Get-Content (Join-Path $root "tests\out\make_shots.log")
