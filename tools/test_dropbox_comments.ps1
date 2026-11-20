# Asks Dropbox's undocumented comments2/list_comments route for the comments
# of one file and saves the raw answer, to see whether Backdrop could fetch
# comments by itself. The request body is the one used by
# github.com/rpeyron/dropbox-comments-downloader (2019).
#
# The access token is read from the DROPBOX_TOKEN environment variable, so it
# never ends up in a file or in the command line:
#
#   $env:DROPBOX_TOKEN = Read-Host "Dropbox access token"
#   .\test_dropbox_comments.ps1 -File "/Project/04_JPG/Scene_3/SK100-30_FC-2840BB_Angle01.jpg"
#
# -File is the path inside Dropbox (starts with "/") or a file id ("id:...").
param(
    [Parameter(Mandatory = $true)][string]$File,
    [string]$Out = (Join-Path $PSScriptRoot "dropbox_comments_answer.json")
)

if (-not $env:DROPBOX_TOKEN) { "Set DROPBOX_TOKEN first (see the header of this script)."; exit 1 }

$body = @{
    stream = @{
        type       = @{ ".tag" = "file" }
        identifier = @{ ".tag" = "file_path_or_id"; file_path_or_id = $File }
    }
    include_permissions = $true
} | ConvertTo-Json -Depth 5 -Compress

$response = Invoke-WebRequest -Method Post -SkipHttpErrorCheck `
    -Uri "https://api.dropboxapi.com/2/comments2/list_comments" `
    -Headers @{ Authorization = "Bearer $env:DROPBOX_TOKEN" } `
    -ContentType "application/json" -Body $body

"HTTP {0}" -f $response.StatusCode
[System.IO.File]::WriteAllText($Out, $response.Content)
"Answer saved to $Out"
$text = $response.Content
if ($text.Length -gt 600) { $text = $text.Substring(0, 600) + " ..." }
$text
