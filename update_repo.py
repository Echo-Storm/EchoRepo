#!/usr/bin/env python3
"""
EchoRepo Maintenance Script
Automatically updates addons.xml, creates zip files, and maintains the repository
"""

import os
import sys
import hashlib
import zipfile
import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path
from datetime import datetime
import shutil

class RepoMaintenance:
    def __init__(self, base_path):
        self.base_path = Path(base_path)
        self.addons = []
        self.excluded_dirs = {
            '.git', '__pycache__', '.vscode', '.idea',
            'venv', 'env', 'node_modules'
        }
        
    def find_addons(self):
        """Find all addon directories with addon.xml files"""
        print("Scanning for addons...")
        
        for item in self.base_path.iterdir():
            if not item.is_dir():
                continue
            
            if item.name in self.excluded_dirs:
                continue
            
            addon_xml = item / "addon.xml"
            if addon_xml.exists():
                self.addons.append(item)
                print(f"  ✓ Found: {item.name}")
        
        if not self.addons:
            print("  ⚠ No addons found!")
        
        print(f"\nTotal addons: {len(self.addons)}\n")
        return self.addons
    
    def create_addon_zip(self, addon_path):
        """Create a zip file for an addon"""
        addon_id = addon_path.name
        
        # Parse addon.xml to get version
        tree = ET.parse(addon_path / "addon.xml")
        root = tree.getroot()
        version = root.get('version', '0.0.0')
        
        zip_filename = f"{addon_id}-{version}.zip"
        zip_path = self.base_path / zip_filename
        
        print(f"Creating {zip_filename}...")
        
        # Remove old zip if exists
        if zip_path.exists():
            zip_path.unlink()
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(addon_path):
                # Remove excluded directories from walk
                dirs[:] = [d for d in dirs if d not in self.excluded_dirs]
                
                for file in files:
                    file_path = Path(root) / file
                    
                    # Skip certain files
                    if file in ['.gitignore', '.gitattributes', 'desktop.ini', 'Thumbs.db']:
                        continue
                    if file.endswith(('.pyc', '.pyo', '.tmp', '.bak', '~')):
                        continue
                    
                    # Calculate archive path
                    rel_path = file_path.relative_to(addon_path)
                    archive_path = f"{addon_id}/{rel_path}"
                    
                    zipf.write(file_path, archive_path)
        
        # Get zip file size
        size_mb = zip_path.stat().st_size / (1024 * 1024)
        print(f"  ✓ Created {zip_filename} ({size_mb:.2f} MB)")
        
        return zip_path, version
    
    def generate_addons_xml(self):
        """Generate the addons.xml file"""
        print("\nGenerating addons.xml...")
        
        # Create root element
        addons_root = ET.Element("addons")
        
        for addon_path in self.addons:
            # Parse the addon's addon.xml
            tree = ET.parse(addon_path / "addon.xml")
            addon_element = tree.getroot()
            
            # Append to addons.xml
            addons_root.append(addon_element)
        
        # Pretty print
        xml_str = minidom.parseString(ET.tostring(addons_root)).toprettyxml(indent="  ")
        # Remove extra blank lines and XML declaration
        lines = [line for line in xml_str.split('\n') if line.strip()]
        xml_str = '\n'.join(lines[1:])  # Skip XML declaration
        
        # Add proper XML header
        final_xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + xml_str
        
        # Write to file
        addons_xml_path = self.base_path / "addons.xml"
        with open(addons_xml_path, 'w', encoding='utf-8') as f:
            f.write(final_xml)
        
        print(f"  ✓ {addons_xml_path}")
        return addons_xml_path
    
    def generate_md5(self, file_path):
        """Generate MD5 checksum for a file"""
        print(f"\nGenerating MD5 checksum for {file_path.name}...")
        
        md5_hash = hashlib.md5()
        with open(file_path, 'rb') as f:
            md5_hash.update(f.read())
        
        md5_value = md5_hash.hexdigest()
        
        # Write to .md5 file
        md5_path = file_path.with_suffix('.xml.md5')
        with open(md5_path, 'w') as f:
            f.write(md5_value)
        
        print(f"  ✓ {md5_path}")
        print(f"  MD5: {md5_value}")
        return md5_path
    
    def cleanup_old_zips(self):
        """Remove old zip files for addons that have been updated"""
        print("\nCleaning up old zip files...")
        
        # Get current addon versions
        current_zips = set()
        for addon_path in self.addons:
            addon_id = addon_path.name
            tree = ET.parse(addon_path / "addon.xml")
            root = tree.getroot()
            version = root.get('version', '0.0.0')
            current_zips.add(f"{addon_id}-{version}.zip")
        
        # Find and remove old zips
        removed_count = 0
        for zip_file in self.base_path.glob("*.zip"):
            if zip_file.name not in current_zips:
                # Check if it's an addon zip (not repo zip)
                if zip_file.name.count('-') >= 1:  # Has version number
                    print(f"  Removing old: {zip_file.name}")
                    zip_file.unlink()
                    removed_count += 1
        
        if removed_count == 0:
            print("  No old zips to remove")
        else:
            print(f"  ✓ Removed {removed_count} old zip(s)")
    
    def generate_report(self):
        """Generate a maintenance report"""
        print("\n" + "="*60)
        print("Maintenance Report")
        print("="*60 + "\n")
        
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Repository path: {self.base_path}")
        print(f"Total addons: {len(self.addons)}\n")
        
        print("Addon Versions:")
        for addon_path in sorted(self.addons, key=lambda x: x.name):
            tree = ET.parse(addon_path / "addon.xml")
            root = tree.getroot()
            addon_id = root.get('id')
            version = root.get('version')
            name = root.get('name')
            print(f"  • {name} ({addon_id}) - v{version}")
        
        print("\n" + "="*60)
    
    def validate_addons(self):
        """Validate addon.xml files"""
        print("\nValidating addon.xml files...")
        
        valid = True
        for addon_path in self.addons:
            addon_xml = addon_path / "addon.xml"
            
            try:
                tree = ET.parse(addon_xml)
                root = tree.getroot()
                
                # Check required attributes
                addon_id = root.get('id')
                version = root.get('version')
                name = root.get('name')
                
                if not addon_id or not version or not name:
                    print(f"  ✗ {addon_path.name}: Missing required attributes")
                    valid = False
                    continue
                
                # Check if directory name matches addon ID
                if addon_path.name != addon_id:
                    print(f"  ⚠ {addon_path.name}: Directory name doesn't match addon ID ({addon_id})")
                
                print(f"  ✓ {addon_id} v{version}")
                
            except ET.ParseError as e:
                print(f"  ✗ {addon_path.name}: XML parse error - {e}")
                valid = False
        
        return valid
    
    def run(self, skip_zips=False):
        """Run the complete maintenance cycle"""
        print("="*60)
        print("EchoRepo Maintenance - Starting Update Cycle")
        print("="*60 + "\n")
        
        # Find all addons
        if not self.find_addons():
            print("\n⚠ No addons found. Nothing to do.")
            return False
        
        # Validate addons
        if not self.validate_addons():
            print("\n✗ Validation failed. Please fix errors before continuing.")
            return False
        
        # Create zip files for each addon
        if not skip_zips:
            print("\nCreating addon zip files...")
            for addon_path in self.addons:
                self.create_addon_zip(addon_path)
            
            # Cleanup old zips
            self.cleanup_old_zips()
        else:
            print("\nSkipping zip file creation (--skip-zips)")
        
        # Generate addons.xml
        addons_xml_path = self.generate_addons_xml()
        
        # Generate MD5
        self.generate_md5(addons_xml_path)
        
        # Generate report
        self.generate_report()
        
        print("\n✓ Maintenance cycle complete!")
        print("\nNext steps:")
        print("1. Review the changes")
        print("2. Test installation in Kodi")
        print("3. Commit and push to GitHub:")
        print("   git add .")
        print(f"   git commit -m \"Update repository - {datetime.now().strftime('%Y-%m-%d')}\"")
        print("   git push origin main")
        
        return True


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Maintain Kodi repository - update addons.xml and create zips"
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=r"E:\EchoRepo",
        help="Path to repository root (default: E:\\EchoRepo)"
    )
    parser.add_argument(
        "--skip-zips",
        action="store_true",
        help="Skip creating zip files (only update addons.xml)"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate addon.xml files without making changes"
    )
    
    args = parser.parse_args()
    
    maintenance = RepoMaintenance(args.path)
    
    if args.validate_only:
        print("="*60)
        print("Validation Mode")
        print("="*60 + "\n")
        maintenance.find_addons()
        is_valid = maintenance.validate_addons()
        print("\n" + ("✓ All addons valid" if is_valid else "✗ Validation failed"))
        sys.exit(0 if is_valid else 1)
    
    success = maintenance.run(skip_zips=args.skip_zips)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
