<#
.SYNOPSIS
    Uploads media organized by Rename-ByGPS.ps1 to your personal Instagram
    account, grouped by country / city, with flag titles, town names, and
    exact GPS coordinates in each caption.

.DESCRIPTION
    Expects the folder layout produced by Rename-ByGPS.ps1, for example:

        E:\DCIM\100MEDIA\Spain\Andalucia\Manilva\36.318189,-5.245317.JPG

    Instagram has no albums-by-country folders, so organization is done via:
      - grouping posts (per-city albums by default)
      - country flag + title in the caption
      - town / state / coordinates in the caption
      - optional Instagram location tag from GPS

    This launcher calls upload_by_gps.py (instagrapi). Always start with
    -DryRun to preview captions before publishing.

.USAGE
    Edit the CONFIG block below, then:

        powershell -ExecutionPolicy Bypass -File .\Upload-ByGPS.ps1

    Preview only (recommended first run):

        powershell -ExecutionPolicy Bypass -File .\Upload-ByGPS.ps1 -DryRun

    Publish for real:

        powershell -ExecutionPolicy Bypass -File .\Upload-ByGPS.ps1 -Upload

    Only one country:

        powershell -ExecutionPolicy Bypass -File .\Upload-ByGPS.ps1 -Upload -OnlyCountry Spain

.NOTES
    - Requires Python 3.11+ and:  pip install -r requirements.txt
    - Prefer env vars IG_USERNAME / IG_PASSWORD over putting secrets in files.
    - Unofficial Instagram automation can trigger security checks; go slowly
      (DelaySeconds), reuse the session file, and complete any challenge in
      the official Instagram app if asked.
    - Already-uploaded files are tracked in upload_state.json so re-runs are safe.
#>

param(
    [switch]$DryRun,
    [switch]$Upload,
    [ValidateSet("per-photo", "per-city", "per-country")]
    [string]$Mode = "",
    [string[]]$OnlyCountry = @(),
    [string[]]$SkipCountry = @(),
    [int]$Limit = -1,
    [switch]$NoLocation
)

# ---- CONFIG -----------------------------------------------------------
$Python      = "python"                       # or full path to python.exe
$Folder      = "E:\DCIM\100MEDIA"             # same root used by Rename-ByGPS.ps1
$Username    = $env:IG_USERNAME               # prefer environment variables
$Password    = $env:IG_PASSWORD
$SessionFile = Join-Path $PSScriptRoot "instagram_session.json"
$StateFile   = Join-Path $PSScriptRoot "upload_state.json"
$ConfigFile  = Join-Path $PSScriptRoot "config.json"

# per-city (recommended) | per-photo | per-country
$DefaultMode     = "per-city"
$DelaySeconds    = 90                         # pause between posts
$MaxAlbumSize    = 10                         # Instagram album hard max is 10
$DefaultDryRun   = $true                      # safety: preview unless -Upload
# ------------------------------------------------------------------------

$ErrorActionPreference = "Stop"
$scriptPy = Join-Path $PSScriptRoot "upload_by_gps.py"

if (-not (Test-Path $scriptPy)) {
    Write-Error "upload_by_gps.py not found next to this script: $scriptPy"
    exit 1
}
if (-not (Test-Path $Folder)) {
    Write-Error "Folder not found: $Folder"
    exit 1
}

# Create a starter config.json from the example if missing
$example = Join-Path $PSScriptRoot "config.example.json"
if (-not (Test-Path $ConfigFile) -and (Test-Path $example)) {
    Copy-Item $example $ConfigFile
    Write-Host "Created $ConfigFile from config.example.json — edit credentials if needed."
}

$effectiveMode = if ($Mode) { $Mode } else { $DefaultMode }

$pyArgs = @(
    $scriptPy,
    "--config", $ConfigFile,
    "--folder", $Folder,
    "--session-file", $SessionFile,
    "--state-file", $StateFile,
    "--mode", $effectiveMode,
    "--delay-seconds", $DelaySeconds,
    "--max-album-size", $MaxAlbumSize
)

if ($Username) { $pyArgs += @("--username", $Username) }
if ($Password) { $pyArgs += @("--password", $Password) }

if ($Upload) {
    $pyArgs += "--upload"
} elseif ($DryRun -or $DefaultDryRun) {
    $pyArgs += "--dry-run"
}

if ($Limit -ge 0) { $pyArgs += @("--limit", $Limit) }
if ($NoLocation) { $pyArgs += "--no-location" }

foreach ($c in $OnlyCountry) { $pyArgs += @("--only-country", $c) }
foreach ($c in $SkipCountry) { $pyArgs += @("--skip-country", $c) }

Write-Host "Running: $Python $($pyArgs -join ' ')"
& $Python @pyArgs
exit $LASTEXITCODE
