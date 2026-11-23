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

# docs\shots\sources.gif from the frames make_shots.py left: one palette for
# the whole clip, then the frames at the durations of frames.txt.
$frames = Join-Path $root "tests\out\shots\frames"
if ((Test-Path (Join-Path $frames "frames.txt")) -and (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Push-Location $frames
    & ffmpeg -y -loglevel error -f concat -safe 0 -i frames.txt `
        -vf "split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5" `
        -loop 0 (Join-Path $root "docs\shots\sources.gif")
    Pop-Location
}
