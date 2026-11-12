<#
.SYNOPSIS
    Organizes images/videos into Country\State\City subfolders based on their
    embedded GPS EXIF data (via exiftool + OpenStreetMap Nominatim reverse
    geocoding), and names each file after its exact coordinates.

    Example result:
        DroneFolder\Spain\Andalucia\Manilva\36.318189,-5.245317.JPG

.USAGE
    Edit the CONFIG block below, then run:

        powershell -ExecutionPolicy Bypass -File .\Rename-ByGPS.ps1

    Or right-click the .ps1 file -> "Run with PowerShell".

.NOTES
    - Requires internet access (calls nominatim.openstreetmap.org).
    - Nominatim's usage policy caps requests at 1/second and requires a
      descriptive User-Agent, both respected here.
      https://operations.osmfoundation.org/policies/nominatim/
    - Files with no GPS data are left untouched (a warning is printed).
    - Files whose coordinates can't be geocoded land in an "Unknown Location"
      subfolder, still named after their coordinates, so nothing is lost.
    - Repeated coordinates are geocoded once and cached, to stay under the
      rate limit and speed things up on large batches.
    - If two files share the exact same rounded coordinates (e.g. burst
      shots), a "(2)", "(3)", ... suffix is appended so nothing is overwritten.
#>

# ---- CONFIG -----------------------------------------------------------
$ExifTool   = "C:\Users\34634\Downloads\exiftool\exiftool.exe"
$Folder     = "E:\DCIM\100MEDIA"          # <-- change this to your folder
$Extensions = @("*.jpg", "*.jpeg", "*.png", "*.mp4", "*.mov", "*.dng")
$Recurse    = $false                       # $true to also process subfolders

# Folder hierarchy levels, in order. Any level missing from the geocoding
# result for a given photo is simply skipped (so you don't get empty folders).
#   "country", "state", "city"
$FolderLevels = @("country", "state", "city")
# ------------------------------------------------------------------------

if (-not (Test-Path $ExifTool)) {
    Write-Error "exiftool.exe not found at: $ExifTool"
    exit 1
}
if (-not (Test-Path $Folder)) {
    Write-Error "Folder not found: $Folder"
    exit 1
}

$files = foreach ($ext in $Extensions) {
    Get-ChildItem -Path $Folder -Filter $ext -File -Recurse:$Recurse
}

$geocodeCache = @{}
$usedNames    = @{}   # key = full destination path (lowercase) -> count

function Get-SafeFileName {
    param([string]$Name)
    $invalid = [IO.Path]::GetInvalidFileNameChars()
    -join ($Name.ToCharArray() | ForEach-Object { if ($invalid -contains $_) { "_" } else { $_ } })
}

function Get-AddressParts {
    param([double]$Lat, [double]$Lon)

    # Round to 4 decimals (~11m) for cache-key purposes only, so shots taken
    # a few meters apart in the same spot reuse one lookup.
    $cacheKey = "{0:F4},{1:F4}" -f $Lat, $Lon
    if ($geocodeCache.ContainsKey($cacheKey)) {
        return $geocodeCache[$cacheKey]
    }

    $url = "https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=$Lat&lon=$Lon&zoom=14&addressdetails=1"

    $result = $null
    try {
        $response = Invoke-RestMethod -Uri $url -Headers @{ "User-Agent" = "DroneFileRenamer/1.0 (personal script)" } -Method Get
        $addr = $response.address
        if ($addr) {
            $locality = $addr.city
            if (-not $locality) { $locality = $addr.town }
            if (-not $locality) { $locality = $addr.village }
            if (-not $locality) { $locality = $addr.hamlet }
            if (-not $locality) { $locality = $addr.municipality }
            if (-not $locality) { $locality = $addr.county }

            $result = @{
                country = $addr.country
                state   = $addr.state
                city    = $locality
            }
        }
    } catch {
        Write-Warning "Geocoding failed for $Lat,$Lon : $_"
    }

    Start-Sleep -Milliseconds 1000   # respect Nominatim's 1 req/sec limit

    $geocodeCache[$cacheKey] = $result
    return $result
}

foreach ($file in $files) {

    # -n : plain signed decimal GPS values, -T : tab-separated, no field names
    $raw = & $ExifTool -n -T -GPSLatitude -GPSLongitude -- "$($file.FullName)" 2>$null

    if ([string]::IsNullOrWhiteSpace($raw)) {
        Write-Warning "No exiftool output for: $($file.Name)"
        continue
    }

    $parts = $raw -split "`t"
    $lat = $parts[0].Trim()
    $lon = if ($parts.Count -gt 1) { $parts[1].Trim() } else { "" }

    if ($lat -eq "-" -or $lon -eq "-" -or [string]::IsNullOrWhiteSpace($lat) -or [string]::IsNullOrWhiteSpace($lon)) {
        Write-Warning "No GPS data, skipping: $($file.Name)"
        continue
    }

    $latRounded = [math]::Round([double]$lat, 6)
    $lonRounded = [math]::Round([double]$lon, 6)

    $addr = Get-AddressParts -Lat $latRounded -Lon $lonRounded

    # Build folder path from whichever levels have data
    $pathSegments = @()
    if ($addr) {
        foreach ($level in $FolderLevels) {
            $value = $addr[$level]
            if ($value) { $pathSegments += (Get-SafeFileName $value) }
        }
    }
    if ($pathSegments.Count -eq 0) {
        $pathSegments = @("Unknown Location")
    }

    $destDir = Join-Path $Folder ($pathSegments -join "\")
    if (-not (Test-Path $destDir)) {
        New-Item -ItemType Directory -Path $destDir -Force | Out-Null
    }

    $baseName = "$latRounded,$lonRounded"
    $newName  = "$baseName$($file.Extension)"
    $destPath = Join-Path $destDir $newName

    # Handle collisions (e.g. burst shots at the exact same rounded coords)
    $key = $destPath.ToLower()
    if ($usedNames.ContainsKey($key)) {
        $usedNames[$key]++
        $newName  = "$baseName ($($usedNames[$key]))$($file.Extension)"
        $destPath = Join-Path $destDir $newName
    } else {
        $usedNames[$key] = 1
    }

    try {
        Move-Item -LiteralPath $file.FullName -Destination $destPath -ErrorAction Stop
        Write-Host "Moved: $($file.Name)  ->  $($destPath.Substring($Folder.Length + 1))"
    } catch {
        Write-Warning "Failed to move $($file.Name): $_"
    }
}

Write-Host "`nDone."
