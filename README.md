# Echo-Storm Kodi Repository

Personal Kodi addon repository hosted on GitHub.  
GitHub Pages landing page: [echo-storm.github.io/EchoRepo](https://echo-storm.github.io/EchoRepo/)

---

## Installing the Repository in Kodi

**Step 1 — Enable Unknown Sources** (first time only)  
`Settings -> System -> Add-ons -> Unknown sources -> On`

**Step 2 — Install the repository addon from zip**  
`Settings -> Add-ons -> Install from zip file`  
Enter this URL directly when prompted:
```
https://raw.githubusercontent.com/Echo-Storm/EchoRepo/main/zips/repository.echostorm/repository.echostorm-1.0.3.zip
```

> Note: `raw.githubusercontent.com` always returns "400: Invalid request" in a browser — that is normal.
> It only serves individual files, not directory listings. Kodi handles it fine.

**Step 3 — Install addons from the repository**  
`Add-ons -> Install from repository -> Echo-Storm Repository`

After the repository addon is installed, Kodi checks for addon updates automatically on its normal schedule.

---

## Repo Structure

```
/repository.echostorm/       <- Repository addon source
    addon.xml
    icon.png                 (512x512)
    fanart.jpg               (1920x1080)

/your-other-addon/           <- Other addon sources (one folder per addon)
    addon.xml
    icon.png
    fanart.jpg
    ...

/zips/                       <- AUTO-GENERATED — do not edit manually
    addons.xml               (master addon index)
    addons.xml.md5           (checksum for Kodi)
    /repository.echostorm/   (repo addon zip + assets)
    /your-other-addon/       (addon zips + assets)

/update_repo.py              <- Maintenance script (CLI)
/echo_repo_gui.py            <- Maintenance GUI (PyQt6)
/echo_repo_gui.bat           <- GUI launcher (Windows)
/index.html                  <- GitHub Pages landing page
/.nojekyll                   <- Disables Jekyll on GitHub Pages
/.github/workflows/pages.yml <- Auto-deploys Pages on every push to main
```

---

## Updating the Repo (GUI — recommended)

Double-click `echo_repo_gui.bat` or run:
```
python echo_repo_gui.py
```

The GUI auto-detects the repo if launched from the same folder.

| Button | What it does |
|---|---|
| [R] Refresh | Re-scans addon folders, updates the display |
| Validate | Checks all addon.xml files — no files changed |
| Build Only | Rebuilds zips and addons.xml — no git, no version bump |
| Bump Repo Ver | Increments repository.echostorm version, rebuilds, commits, pushes — see note below |
| [^] Update && Push | Rebuilds zips, regenerates addons.xml, commits, pushes — no version bump |

**When to use Bump Repo Ver:**  
Only when you have edited `repository.echostorm/addon.xml` itself — i.e. changed the repo URLs, name, summary, or description. Do not use it for normal addon updates. Kodi tracks addon updates by each addon's own version number, not the repository addon version.

**Normal workflow for updating an addon:**  
1. Edit the addon code in its folder  
2. Bump `version` in that addon's `addon.xml`  
3. Hit **[^] Update && Push**  

Kodi will see the new version in `addons.xml` and auto-update.

---

## Updating the Repo (CLI)

```bat
:: Normal update — rebuild zips, commit, push (no version bump)
python update_repo.py

:: Build only — no git operations, no version bump
python update_repo.py --no-commit

:: Bump repository.echostorm version, then full update + push
python update_repo.py --bump-repo

:: Validate addon.xml files only — no changes made
python update_repo.py --validate
```

---

## Adding a New Addon

1. Create a folder in the repo root: e.g. `/plugin.video.myaddon/`
2. Add the required files:
   - `addon.xml` — Kodi manifest (must have `id` and `version` attributes)
   - `icon.png` — 512x512
   - `fanart.jpg` — 1920x1080
   - Your addon code
3. Hit **[^] Update && Push** in the GUI (or run `python update_repo.py`)

The folder name must match the `id` attribute in `addon.xml`.

---

## What the Maintenance Script Does

1. Optionally bumps `repository.echostorm` version (`--bump-repo` only)
2. Scans root for all folders containing `addon.xml`
3. Creates `zips/{addon_id}/{addon_id}-{version}.zip` for each addon
4. Copies `addon.xml`, `icon.png`, `fanart.jpg` into each zip folder
5. Generates `zips/addons.xml` listing all addons at their current versions
6. Generates `zips/addons.xml.md5` checksum
7. Commits everything and pushes to GitHub

---

## Verification URLs

| Resource | URL |
|---|---|
| Addon index | `https://raw.githubusercontent.com/Echo-Storm/EchoRepo/main/zips/addons.xml` |
| Checksum | `https://raw.githubusercontent.com/Echo-Storm/EchoRepo/main/zips/addons.xml.md5` |
| Repo zip | `https://raw.githubusercontent.com/Echo-Storm/EchoRepo/main/zips/repository.echostorm/repository.echostorm-1.0.3.zip` |
| Pages site | `https://echo-storm.github.io/EchoRepo/` |

---

## Requirements

- Python 3.10+
- PyQt6 (`pip install PyQt6`) — GUI only
- Git configured with push access to this repo
- GitHub Pages source set to **GitHub Actions** in repo Settings -> Pages
