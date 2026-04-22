#!/usr/bin/env python3
"""
EchoRepo Maintenance Script
Scans addon folders, generates addons.xml, creates zips in zips/{addon_id}/

Usage:
    python3 update_repo.py              # Full update + git commit/push
    python3 update_repo.py --no-commit  # Generate files only, no git operations
    python3 update_repo.py --validate   # Validate addon.xml files only
"""
import os
import sys
import hashlib
import zipfile
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from decimal import Decimal, InvalidOperation, getcontext

# === Configuration ===
REPO_ROOT = Path(__file__).parent.resolve()
ZIPS_DIR = REPO_ROOT / "zips"
ADDONS_XML = ZIPS_DIR / "addons.xml"
ADDONS_XML_MD5 = ZIPS_DIR / "addons.xml.md5"

EXCLUDED_DIRS = {
    ".git", "__pycache__", "zips", ".vscode", ".idea",
    "venv", "env", "node_modules"
}

EXCLUDED_FILES = {
    ".gitignore", ".gitattributes", "desktop.ini", "Thumbs.db", ".DS_Store"
}

# Set Decimal precision
getcontext().prec = 6

# === Helper Functions ===

def find_addon_folders():
    """Find all valid addon folders (directories containing addon.xml)."""
    addons = []
    for item in REPO_ROOT.iterdir():
        if item.is_dir() and item.name not in EXCLUDED_DIRS:
            addon_xml = item / "addon.xml"
            if addon_xml.exists():
                addons.append(item)
    return sorted(addons, key=lambda p: p.name)

def parse_addon_xml(addon_path):
    """Parse addon.xml and return (id, version, name, root_element)."""
    addon_xml = addon_path / "addon.xml"
    tree = ET.parse(addon_xml)
    root = tree.getroot()

    addon_id = root.get("id")
    version = root.get("version")
    name = root.get("name")

    if not addon_id or not version:
        raise ValueError(f"Missing id or version in {addon_xml}")

    return addon_id, version, name or addon_id, root

def create_addon_zip(addon_path, addon_id, version):
    """
    Create zip for addon in zips/{addon_id}/ folder.
    Also copies addon.xml, icon.png, fanart.jpg to the zip folder for Kodi browsing.
    """
    zip_dir = ZIPS_DIR / addon_id
    zip_dir.mkdir(parents=True, exist_ok=True)

    zip_name = f"{addon_id}-{version}.zip"
    zip_path = zip_dir / zip_name

    # Remove any existing zips for this addon (old versions)
    for old_zip in zip_dir.glob(f"{addon_id}-*.zip"):
        try:
            old_zip.unlink()
            print(f"    Removed old: {old_zip.name}")
        except Exception:
            pass

    # Create the zip
    print(f"    Creating {zip_name}...")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root_dir, dirs, files in os.walk(addon_path):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]

            for filename in files:
                # Skip excluded files
                if filename in EXCLUDED_FILES:
                    continue
                if filename.endswith(('.pyc', '.pyo', '.tmp', '.bak', '~')):
                    continue

                file_path = Path(root_dir) / filename
                rel_path = file_path.relative_to(addon_path)
                archive_path = f"{addon_id}/{rel_path}"
                zipf.write(file_path, archive_path)

    # Copy assets to zip folder for Kodi addon browser display
    for asset in ["addon.xml", "icon.png", "fanart.jpg"]:
        src = addon_path / asset
        if src.exists():
            dst = zip_dir / asset
            dst.write_bytes(src.read_bytes())

    size_kb = zip_path.stat().st_size / 1024
    print(f"    Created {zip_name} ({size_kb:.1f} KB)")
    return zip_path

def generate_addons_xml(addon_elements):
    """Generate addons.xml from list of addon root elements."""
    root = ET.Element("addons")
    for elem in addon_elements:
        # Append a deep copy of the element to avoid altering original trees
        root.append(elem)

    # Pretty-print (Python 3.9+)
    try:
        ET.indent(root, space="    ")
    except AttributeError:
        pass  # older Python versions: skip indentation

    tree = ET.ElementTree(root)
    ZIPS_DIR.mkdir(parents=True, exist_ok=True)
    tree.write(ADDONS_XML, encoding="UTF-8", xml_declaration=True)

    print(f"\n✓ Generated {ADDONS_XML.relative_to(REPO_ROOT)}")

def generate_md5():
    """Generate MD5 checksum for addons.xml."""
    if not ADDONS_XML.exists():
        raise FileNotFoundError(f"{ADDONS_XML} not found")

    md5_hash = hashlib.md5()
    with open(ADDONS_XML, "rb") as f:
        md5_hash.update(f.read())
    checksum = md5_hash.hexdigest()
    ADDONS_XML_MD5.write_text(checksum)

    print(f"✓ Generated {ADDONS_XML_MD5.relative_to(REPO_ROOT)}")
    print(f"  MD5: {checksum}")

def bump_repo_version(increment=Decimal("0.1")):
    """
    Find repository addon folder (repository.echostorm), bump its addon.xml version by increment,
    and write the updated addon.xml back.
    """
    repo_folder = REPO_ROOT / "repository.echostorm"
    addon_xml = repo_folder / "addon.xml"
    if not addon_xml.exists():
        print("No repository addon found to bump version.")
        return None

    tree = ET.parse(addon_xml)
    root = tree.getroot()
    current_version = root.get("version")
    if not current_version:
        print("Repository addon has no version attribute.")
        return None

    # Try to parse as Decimal; if it fails, attempt to handle dotted versions by using the last numeric part
    try:
        new_version = (Decimal(current_version) + increment).normalize()
        # Remove any trailing zeros and possible exponent
        new_version_str = format(new_version, 'f')
    except (InvalidOperation, ValueError):
        # Fallback: handle dotted versions like "1.2.3" -> increment last numeric segment by 1 in tenths
        parts = current_version.split(".")
        try:
            # Try to treat last part as integer and add 1 to the last decimal digit (i.e., +0.1)
            # Convert whole version to Decimal by joining with '.' and adding increment
            joined = ".".join(parts)
            new_version = (Decimal(joined) + increment).normalize()
            new_version_str = format(new_version, 'f')
        except Exception:
            # As a last resort, append .1
            new_version_str = current_version + ".1"

    root.set("version", new_version_str)
    # Write back with declaration
    try:
        ET.indent(root, space="    ")
    except AttributeError:
        pass
    tree.write(addon_xml, encoding="UTF-8", xml_declaration=True)
    print(f"✓ Bumped repository version: {current_version} -> {new_version_str}")
    return new_version_str

def git_commit_and_push():
    """Commit all changes and push to GitHub."""
    print("\n=== Git Operations ===")
    # Check if in a git repo
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        cwd=REPO_ROOT, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(" Not a git repository. Skipping commit.")
        return

    # Stage all changes
    subprocess.run(["git", "add", "-A"], cwd=REPO_ROOT, check=True)

    # Check if there are staged changes
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=REPO_ROOT, capture_output=True
    )
    if result.returncode == 0:
        print("✓ No changes to commit")
        return

    # Commit
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    commit_msg = f"Update repository - {timestamp}"
    subprocess.run(["git", "commit", "-m", commit_msg], cwd=REPO_ROOT, check=True)
    print(f"✓ Committed: {commit_msg}")

    # Push
    try:
        subprocess.run(
            ["git", "push"],
            cwd=REPO_ROOT, check=True, capture_output=True, text=True, timeout=30
        )
        print("✓ Pushed to GitHub")
    except subprocess.CalledProcessError as e:
        print(f" Push failed: {e.stderr}")
        print("  Run 'git push' manually")
    except subprocess.TimeoutExpired:
        print(" Push timed out - check your connection")

def validate_only():
    """Validate addon.xml files without making changes."""
    print("=== Validation Mode ===\n")
    addon_folders = find_addon_folders()
    if not addon_folders:
        print("✗ No addon folders found")
        return False

    all_valid = True
    for addon_path in addon_folders:
        try:
            addon_id, version, name, _ = parse_addon_xml(addon_path)

            # Check directory name matches addon ID
            if addon_path.name != addon_id:
                print(f" {addon_path.name}: folder name != addon ID '{addon_id}'")

            # Check for required assets
            missing = []
            for asset in ["icon.png", "fanart.jpg"]:
                if not (addon_path / asset).exists():
                    missing.append(asset)

            if missing:
                print(f" {addon_id} v{version}: missing {', '.join(missing)}")
            else:
                print(f"✓ {addon_id} v{version} ({name})")

        except Exception as e:
            print(f"✗ {addon_path.name}: {e}")
            all_valid = False

    print(f"\n{'✓ All addons valid' if all_valid else '✗ Validation failed'}")
    return all_valid

# === Main ===

def main():
    no_commit = "--no-commit" in sys.argv
    validate = "--validate" in sys.argv

    if validate:
        success = validate_only()
        sys.exit(0 if success else 1)

    print("=" * 60)
    print("EchoRepo Maintenance Script")
    print("=" * 60 + "\n")

    # Ensure zips directory exists
    ZIPS_DIR.mkdir(exist_ok=True)

    # Find addon folders
    addon_folders = find_addon_folders()
    if not addon_folders:
        print("✗ No addon folders found (directories with addon.xml)")
        sys.exit(1)

    print(f"Found {len(addon_folders)} addon(s):\n")

    addon_elements = []
    for addon_path in addon_folders:
        addon_id, version, name, root_elem = parse_addon_xml(addon_path)
        print(f"• {addon_id} v{version}")

        # Create zip
        create_addon_zip(addon_path, addon_id, version)

        # Collect element for addons.xml
        addon_elements.append(root_elem)

    # Bump repository version (if repository addon exists)
    bumped = bump_repo_version(Decimal("0.1"))

    # Generate addons.xml and checksum
    generate_addons_xml(addon_elements)
    generate_md5()

    # Git operations
    if no_commit:
        print("\n✓ Skipped git operations (--no-commit)")
    else:
        git_commit_and_push()

    print("\n" + "=" * 60)
    print("Repository update complete!")
    print("=" * 60)

    # Show install URL (if repository addon zip exists)
    repo_addon = ZIPS_DIR / "repository.echostorm"
    if repo_addon.exists():
        zips = list(repo_addon.glob("repository.echostorm-*.zip"))
        if zips:
            zip_name = zips[0].name
            print(f"\nInstall URL:")
            print(f"https://raw.githubusercontent.com/Echo-Storm/EchoRepo/main/zips/repository.echostorm/{zip_name}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nAborted.")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        sys.exit(1)
