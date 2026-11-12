# Instagram uploader for GPS-organized media

Companion to `Rename-ByGPS.ps1`. After your drone/phone files are sorted into:

```text
<Folder>\Spain\Andalucia\Manilva\36.318189,-5.245317.JPG
```

this tool publishes them to your **personal Instagram** feed in a country-aware way.

Instagram has no real country folders, so organization is done with:

| Mechanism | What you get |
| --- | --- |
| **Group mode** (`per-city` default) | Album posts per town (max 10 media each) |
| **Caption title + flag** | e.g. `🇪🇸 Spain — Manilva` |
| **Place line** | `📍 Manilva · Andalucia · Spain` |
| **Exact coordinates** | `🗺️ 36.318189, -5.245317` (from the filename) |
| **Location tag** | Nearest Instagram place from GPS (optional) |
| **Hashtags** | Country / state / city / travel tags |
| **Upload state** | `upload_state.json` so re-runs skip finished files |

## Setup

1. Install Python 3.11+ on Windows.
2. In this folder:

```powershell
pip install -r requirements.txt
copy config.example.json config.json
```

3. Set credentials (preferred — avoid storing the password in `config.json`):

```powershell
$env:IG_USERNAME = "your_username"
$env:IG_PASSWORD = "your_password"
```

4. Point `$Folder` in `Upload-ByGPS.ps1` (or `folder` in `config.json`) at the same root you used in `Rename-ByGPS.ps1`.

## Preview first (dry run)

```powershell
powershell -ExecutionPolicy Bypass -File .\Upload-ByGPS.ps1 -DryRun
```

Or:

```powershell
python upload_by_gps.py --config config.json --folder "E:\DCIM\100MEDIA" --dry-run
```

You will see each planned post with the full caption (flag, town, coordinates) before anything is published.

## Publish

```powershell
powershell -ExecutionPolicy Bypass -File .\Upload-ByGPS.ps1 -Upload
```

Useful filters:

```powershell
# Only Spain, max 3 posts this run
.\Upload-ByGPS.ps1 -Upload -OnlyCountry Spain -Limit 3

# One Instagram post per file
.\Upload-ByGPS.ps1 -Upload -Mode per-photo

# Group by country (split into albums of 10)
.\Upload-ByGPS.ps1 -Upload -Mode per-country
```

## Modes

- **`per-city`** (recommended): one album per `Country/State/City` folder. Best “organized by place” look in the feed.
- **`per-country`**: albums per country (chunked to 10). Good for a travel dump day.
- **`per-photo`**: every file is its own post with full place metadata.

## Safety notes

- Default is **dry run**. Nothing is uploaded until `-Upload` / `--upload`.
- Reuse `instagram_session.json` so Instagram sees a stable device fingerprint.
- Keep `DelaySeconds` high (60–120+) on large batches.
- Unofficial private API automation (`instagrapi`) can trigger Instagram security challenges. If that happens, open the official app, complete the check, then retry.
- Do not commit `config.json`, `instagram_session.json`, or `upload_state.json` if they contain secrets or account data (they are gitignored).

## Workflow

1. Run `Rename-ByGPS.ps1` to build `Country\State\City\lat,lon.ext`.
2. Dry-run `Upload-ByGPS.ps1` and check captions.
3. Upload country by country with `-OnlyCountry` if you want a clean, paced feed.
4. Optionally create Instagram **Highlights** named per country in the app (Highlights require Stories; this script focuses on feed posts with clear country separation).
