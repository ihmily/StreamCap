#!/usr/bin/env python3
"""
Test script for version update functionality
"""

import json
import tempfile
import shutil
from pathlib import Path
from update_version import update_pyproject_toml, update_version_json, validate_version


def test_validate_version():
    """Test version validation"""
    print("Testing version validation...")
    
    valid_versions = ["1.0.0", "1.2.3", "2.0.0-beta", "1.0.0-alpha.1"]
    invalid_versions = ["1.0", "1.0.0.0", "v1.0.0", "1.0.0-", "abc"]
    
    for version in valid_versions:
        assert validate_version(version), f"Valid version {version} failed validation"
        print(f"✅ {version} - valid")
    
    for version in invalid_versions:
        assert not validate_version(version), f"Invalid version {version} passed validation"
        print(f"❌ {version} - invalid (as expected)")
    
    print("Version validation tests passed!\n")


def test_pyproject_update():
    """Test pyproject.toml update"""
    print("Testing pyproject.toml update...")
    
    # Create temporary pyproject.toml
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        pyproject_path = temp_path / "pyproject.toml"
        
        # Create test content
        test_content = '''[project]
name = "StreamCap"
version = "1.0.0"
description = "Live Stream Recorder"
'''
        pyproject_path.write_text(test_content)
        
        # Test update
        result = update_pyproject_toml("1.0.1", temp_path)
        assert result, "Failed to update pyproject.toml"
        
        # Verify update
        updated_content = pyproject_path.read_text()
        assert 'version = "1.0.1"' in updated_content, "Version not updated correctly"
        assert 'version = "1.0.0"' not in updated_content, "Old version still present"
        
        print("✅ pyproject.toml update test passed!\n")


def test_version_json_update():
    """Test version.json update"""
    print("Testing version.json update...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        config_dir = temp_path / "config"
        config_dir.mkdir()
        version_path = config_dir / "version.json"
        
        # Create test content
        test_data = {
            "introduction": {"en": "Test", "zh_CN": "测试"},
            "open_source_license": "Apache License 2.0",
            "version_updates": [
                {
                    "version": "1.0.0",
                    "kernel_version": "4.0.5",
                    "updates": {
                        "en": ["Initial release"],
                        "zh_CN": ["初始版本"]
                    }
                }
            ]
        }
        
        with open(version_path, 'w', encoding='utf-8') as f:
            json.dump(test_data, f, indent=2, ensure_ascii=False)
        
        # Test adding new version
        result = update_version_json(
            "1.0.1", 
            "4.0.6", 
            ["修复bug"], 
            ["Bug fixes"], 
            temp_path
        )
        assert result, "Failed to update version.json"
        
        # Verify update
        with open(version_path, 'r', encoding='utf-8') as f:
            updated_data = json.load(f)
        
        assert len(updated_data["version_updates"]) == 2, "New version not added"
        assert updated_data["version_updates"][0]["version"] == "1.0.1", "New version not at top"
        assert updated_data["version_updates"][0]["kernel_version"] == "4.0.6", "Kernel version not updated"
        
        print("✅ version.json update test passed!\n")


def main():
    """Run all tests"""
    print("🧪 Running version update tests...\n")
    
    try:
        test_validate_version()
        test_pyproject_update()
        test_version_json_update()
        
        print("🎉 All tests passed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())