# Echo-Storm Kodi Repository

Personal Kodi addon repository.

## Installation

**Install from zip URL:**
```
https://raw.githubusercontent.com/Echo-Storm/EchoRepo/main/zips/repository.echostorm/repository.echostorm-1.0.2.zip
```

In Kodi: **Settings → Add-ons → Install from zip file → Enter URL**

## Repository Structure

```
/repository.echostorm/       # Repository addon source
    addon.xml
    icon.png                 # 512x512
    fanart.jpg               # 1920x1080
    
/your-other-addon/           # Other addon sources (one folder per addon)
    addon.xml
    icon.png
    fanart.jpg
    resources/
    lib/
    ...

/zips/                       # Auto-generated (DO NOT edit manually)
    addons.xml               # Master index
    addons.xml.md5           # Checksum
    /repository.echostorm/   # Repo addon zip + assets
    /your-other-addon/       # Other addon zips + assets

/update_repo.py              # Maintenance script
/README.md
```

## Adding a New Addon

1. Create a folder in repo root: `/plugin.video.myaddon/`
2. Add required files:
   - `addon.xml` (manifest)
   - `icon.png` (512×512)
   - `fanart.jpg` (1920×1080)
   - Your addon code
3. Run the update script:
   ```bash
   python3 update_repo.py
   ```

## Updating an Existing Addon

1. Edit the addon code in its folder
2. Bump the `version` in `addon.xml`
3. Run:
   ```bash
   python3 update_repo.py
   ```

## Script Options

```bash
# Full update: generate zips, commit, push
python3 update_repo.py

# Generate files only, no git operations
python3 update_repo.py --no-commit

# Validate addon.xml files only
python3 update_repo.py --validate
```

## What the Script Does

1. Scans repo root for folders containing `addon.xml`
2. Parses each `addon.xml` to extract ID and version
3. Creates zip at `zips/{addon_id}/{addon_id}-{version}.zip`
4. Copies assets (addon.xml, icon.png, fanart.jpg) to zip folder
5. Generates `zips/addons.xml` with all found addons
6. Generates `zips/addons.xml.md5` checksum
7. Commits and pushes to GitHub (unless `--no-commit`)

## Verification URLs

After pushing, these should all be accessible:

- **Install zip:** `https://raw.githubusercontent.com/Echo-Storm/EchoRepo/main/zips/repository.echostorm/repository.echostorm-1.0.2.zip`
- **Addons index:** `https://raw.githubusercontent.com/Echo-Storm/EchoRepo/main/zips/addons.xml`
- **Checksum:** `https://raw.githubusercontent.com/Echo-Storm/EchoRepo/main/zips/addons.xml.md5`
