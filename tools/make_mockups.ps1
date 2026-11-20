# Paints the design mock-ups of the panel (tools/mockups/make_mockups.py)
# inside 3ds Max through 3dsmaxbatch and writes them to docs/mockups.
#
#   pwsh tools/make_mockups.ps1 -Images "D:\...\04_JPG\Scene_3"
param(
    [int]$Year = 2024,
    [string]$Images = ""                    # folder with renders for the thumbnails
)

$root = Split-Path -Parent $PSScriptRoot
$out = Join-Path $root "docs\mockups"
New-Item -ItemType Directory -Force $out | Out-Null
Remove-Item (Join-Path $out "done.txt"), (Join-Path $out "error.txt") -ErrorAction SilentlyContinue

$env:BD_SRC = Join-Path $root "src\backdrop.py"
$env:BD_TEST = Join-Path $root "tools\mockups\make_mockups.py"
$env:BD_MOCK_OUT = $out
$env:BD_MOCK_IMAGES = $Images
$env:BACKDROP_SETTINGS = "BackdropTests"    # keep the user's saved window, theme and folders
$exe = "C:\Program Files\Autodesk\3ds Max $Year\3dsmaxbatch.exe"
& $exe (Join-Path $root "tests\run_in_max.ms") -log (Join-Path $out "max.log") 2>&1 | Out-Null

if (Test-Path (Join-Path $out "error.txt")) { Get-Content (Join-Path $out "error.txt"); exit 1 }
if (-not (Test-Path (Join-Path $out "done.txt"))) { "no result - see docs\mockups\max.log"; exit 1 }
Get-ChildItem $out -Filter *.png | Select-Object -ExpandProperty Name
