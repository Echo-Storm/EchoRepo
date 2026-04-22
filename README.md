# Echo-Storm Kodi Repository

Personal Kodi addon repository hosted on GitHub.  
GitHub Pages landing page: [echo-storm.github.io/EchoRepo](https://echo-storm.github.io/EchoRepo/)

---

## Installing the Repository in Kodi

**Step 1 — Enable Unknown Sources** (first time only)  
`Settings → System → Add-ons → Unknown sources → On`

**Step 2 — Add the repo as a file source in Kodi File Manager**  
`Settings → File Manager → Add source`  
Enter this URL:
```
https://raw.githubusercontent.com/Echo-Storm/EchoRepo/main/zips/
```
Name it `EchoRepo` or anything you like.

**Step 3 — Install the repository addon from zip**  
`Settings → Add-ons → Install from zip file → EchoRepo → repository.echostorm-X.X.X.zip`

**Step 4 — Install addons from the repository**  
`Add-ons → Install from repository → Echo-Storm Repository`

After the repository addon is installed, Kodi checks for updates automatically on its normal schedule.

---

## Repo Structure

```
/repository.echostorm/       ← Repository addon source
    addon.xml
    icon.png                 (512×512)
    fanart.jpg               (1920×1080)

/your-other-addon/           ← Other addon sources (one folder per addon)
    addon.xml
    icon.png
    fanart.jpg
    ...

/zips/                       ← AUTO-GENERATED — do not edit manually
    addons.xml               (master addon index)
    addons.xml.md5           (checksum for Kodi)
    /repository.echostorm/   (repo addon zip + assets)
    /your-other-addon/       (addon zips + assets)

/update_repo.py              ← Maintenance script (CLI)
/echo_repo_gui.py            ← Maintenance GUI (PyQt6)
/echo_repo_gui.bat           ← GUI launcher (Windows)
/index.html                  ← GitHub Pages landing page (auto-generated content)
/.nojekyll                   ← Disables Jekyll on GitHub Pages
/.github/workflows/pages.yml ← Auto-deploys Pages on every push to main
```

---

## Updating the Repo (GUI — recommended)

Double-click **`echo_repo_gui.bat`** or run:
```
python echo_repo_gui.py
```

The GUI auto-detects the repo if launched from the same folder.

| Button | What it does |
|---|---|
| ↺ Refresh | Re-scans addon folders, updates the display |
| Validate | Checks all addon.xml files — no files changed |
| Build Only | Bumps version, rebuilds zips + addons.xml — no git |
| ⬆ Update & Push | Full cycle: bump, build, commit, push to GitHub |

After **Update & Push**, GitHub Actions deploys the Pages site automatically (~30 seconds).

---

## Updating the Repo (CLI)

```bat
REM Full update — bump version, build, commit, push
python update_repo.py

REM Build only — no git operations
python update_repo.py --no-commit

REM Validate addon.xml files only
python update_repo.py --validate
```

The legacy `update_repo.bat` wraps the CLI script if you prefer it over the GUI.

---

## Adding a New Addon

1. Create a folder in the repo root: e.g. `/plugin.video.myaddon/`
2. Add the required files:
   - `addon.xml` — Kodi addon manifest (must have `id` and `version` attributes)
   - `icon.png` — 512×512
   - `fanart.jpg` — 1920×1080
   - Your addon code
3. Run the GUI or script — it will pick up the new folder automatically.

The folder name must match the `id` attribute in `addon.xml`.

---

## What the Maintenance Script Does

1. Bumps the `repository.echostorm` version (last segment +1)
2. Scans root for all folders containing `addon.xml`
3. Creates `zips/{addon_id}/{addon_id}-{version}.zip` for each addon
4. Copies `addon.xml`, `icon.png`, `fanart.jpg` into each zip folder (for Kodi's browser)
5. Generates `zips/addons.xml` listing all addons at their current versions
6. Generates `zips/addons.xml.md5` checksum
7. Commits everything and pushes to GitHub

---

## Verification URLs

After pushing, these should all return valid content:

| Resource | URL |
|---|---|
| Addon index | `https://raw.githubusercontent.com/Echo-Storm/EchoRepo/main/zips/addons.xml` |
| Checksum | `https://raw.githubusercontent.com/Echo-Storm/EchoRepo/main/zips/addons.xml.md5` |
| Repo zip | `https://raw.githubusercontent.com/Echo-Storm/EchoRepo/main/zips/repository.echostorm/repository.echostorm-X.X.X.zip` |
| Pages site | `https://echo-storm.github.io/EchoRepo/` |

---

## Requirements

- Python 3.10+
- PyQt6 (`pip install PyQt6`) — GUI only
- Git configured with push access to this repo
- GitHub Pages source set to **GitHub Actions** in repo Settings → Pages
