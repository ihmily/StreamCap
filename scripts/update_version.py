#!/usr/bin/env python3
"""
Version update script for StreamCap
Usage: python scripts/update_version.py <new_version> [--kernel-version <kernel_version>] [--updates-zh <updates>] [--updates-en <updates>]
"""

import argparse
import json
import re
import sys
from pathlib import Path


def update_pyproject_toml(version: str, project_root: Path) -> bool:
    """Update version in pyproject.toml"""
    pyproject_path = project_root / "pyproject.toml"
    
    if not pyproject_path.exists():
        print(f"Error: {pyproject_path} not found")
        return False
    
    try:
        content = pyproject_path.read_text(encoding='utf-8')
        
        # Update version line
        pattern = r'^version = "[^"]*"'
        replacement = f'version = "{version}"'
        new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
        
        if content == new_content:
            print("Warning: No version found in pyproject.toml to update")
            return False
            
        pyproject_path.write_text(new_content, encoding='utf-8')
        print(f"✅ Updated pyproject.toml version to {version}")
        return True
        
    except Exception as e:
        print(f"Error updating pyproject.toml: {e}")
        return False


def update_version_json(version: str, kernel_version: str = None, 
                       updates_zh: list = None, updates_en: list = None, 
                       project_root: Path = None) -> bool:
    """Update version in config/version.json"""
    version_path = project_root / "config" / "version.json"
    
    if not version_path.exists():
        print(f"Error: {version_path} not found")
        return False
    
    try:
        with open(version_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Prepare new version entry
        new_entry = {
            "version": version,
            "kernel_version": kernel_version or "4.0.5",
            "updates": {
                "en": updates_en or ["Bug fixes and improvements"],
                "zh_CN": updates_zh or ["错误修复和改进"]
            }
        }
        
        # Check if this version already exists
        existing_versions = [entry["version"] for entry in data["version_updates"]]
        if version in existing_versions:
            # Update existing entry
            for i, entry in enumerate(data["version_updates"]):
                if entry["version"] == version:
                    data["version_updates"][i] = new_entry
                    break
            print(f"✅ Updated existing version {version} in version.json")
        else:
            # Add new entry at the beginning
            data["version_updates"].insert(0, new_entry)
            print(f"✅ Added new version {version} to version.json")
        
        # Write back to file
        with open(version_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return True
        
    except Exception as e:
        print(f"Error updating version.json: {e}")
        return False


def validate_version(version: str) -> bool:
    """Validate version format (semantic versioning)"""
    pattern = r'^\d+\.\d+\.\d+(?:-[a-zA-Z0-9]+(?:\.[a-zA-Z0-9]+)*)?$'
    return bool(re.match(pattern, version))


def main():
    parser = argparse.ArgumentParser(description='Update StreamCap version')
    parser.add_argument('version', help='New version (e.g., 1.0.2)')
    parser.add_argument('--kernel-version', help='Kernel version (default: 4.0.5)')
    parser.add_argument('--updates-zh', nargs='+', help='Chinese update descriptions')
    parser.add_argument('--updates-en', nargs='+', help='English update descriptions')
    parser.add_argument('--project-root', type=Path, default=Path.cwd(), 
                       help='Project root directory (default: current directory)')
    
    args = parser.parse_args()
    
    # Validate version format
    if not validate_version(args.version):
        print(f"Error: Invalid version format '{args.version}'. Use semantic versioning (e.g., 1.0.2)")
        sys.exit(1)
    
    # Ensure project root exists and contains expected files
    project_root = args.project_root.resolve()
    if not (project_root / "pyproject.toml").exists():
        print(f"Error: {project_root} doesn't appear to be the StreamCap project root")
        sys.exit(1)
    
    print(f"Updating StreamCap version to {args.version}")
    print(f"Project root: {project_root}")
    
    success = True
    
    # Update pyproject.toml
    if not update_pyproject_toml(args.version, project_root):
        success = False
    
    # Update version.json
    if not update_version_json(
        args.version, 
        args.kernel_version, 
        args.updates_zh, 
        args.updates_en, 
        project_root
    ):
        success = False
    
    if success:
        print(f"\n🎉 Successfully updated version to {args.version}")
        print("\nNext steps:")
        print("1. Review the changes")
        print("2. Commit the changes: git add . && git commit -m 'chore: bump version to {}'".format(args.version))
        print("3. Push to trigger auto-release: git push")
        print("4. Or create a tag manually: git tag v{} && git push origin v{}".format(args.version, args.version))
    else:
        print("\n❌ Failed to update version")
        sys.exit(1)


if __name__ == "__main__":
    main()