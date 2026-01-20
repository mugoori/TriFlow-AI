#!/usr/bin/env python
"""
Module Uninstallation Script

Usage:
    python scripts/uninstall_module.py <module_code>
    python scripts/uninstall_module.py <module_code> --yes
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def uninstall_module(module_code: str, auto_yes: bool = False):
    """Uninstall a module"""
    project_root = Path(__file__).parent.parent
    modules_dir = project_root / 'modules'
    module_dir = modules_dir / module_code

    # Check if module exists
    if not module_dir.exists():
        print(f"❌ Module '{module_code}' not found")
        sys.exit(1)

    # Load manifest
    manifest_path = module_dir / 'manifest.json'
    if manifest_path.exists():
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        name = manifest.get('name', module_code)
        category = manifest.get('category', 'unknown')
    else:
        name = module_code
        category = 'unknown'

    # Confirm
    if not auto_yes:
        print(f"\n⚠️  Are you sure you want to uninstall '{name}' ({module_code})?")
        print(f"   Category: {category}")
        print(f"   Location: {module_dir}")
        confirm = input("\nType module code to confirm: ").strip()

        if confirm != module_code:
            print("❌ Cancelled")
            sys.exit(0)

    # Check if it's a core module
    if category == 'core':
        print("❌ Cannot uninstall core modules")
        sys.exit(1)

    print(f"\n🗑️  Uninstalling module '{module_code}'...")

    # Remove module directory
    try:
        shutil.rmtree(module_dir)
        print(f"  ✅ Removed: {module_dir}")
    except Exception as e:
        print(f"  ❌ Failed to remove directory: {e}")
        sys.exit(1)

    # Rebuild registry
    print("\n🔨 Rebuilding registry...")
    try:
        subprocess.run(
            [sys.executable, 'scripts/build_module_registry.py'],
            cwd=str(project_root),
            check=True,
            capture_output=True
        )
        print("  ✅ Registry updated")

        subprocess.run(
            [sys.executable, 'scripts/build_frontend_imports.py'],
            cwd=str(project_root),
            check=True,
            capture_output=True
        )
        print("  ✅ Frontend imports updated")

    except subprocess.CalledProcessError as e:
        print(f"  ⚠️  Warning: Build failed: {e}")

    print(f"\n✅ Module '{module_code}' uninstalled successfully!")
    print("\n📝 Next Steps:")
    print("  1. Restart backend server")
    print("  2. Restart frontend dev server")
    print("  3. Refresh browser")


def main():
    parser = argparse.ArgumentParser(description="Uninstall TriFlow module")
    parser.add_argument('module_code', help="Module code to uninstall")
    parser.add_argument('--yes', '-y', action='store_true', help="Skip confirmation")

    args = parser.parse_args()
    uninstall_module(args.module_code, args.yes)


if __name__ == "__main__":
    main()
