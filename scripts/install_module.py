#!/usr/bin/env python
"""
Module Installation Script
Install TriFlow modules from ZIP files

Usage:
    python scripts/install_module.py module.zip
    python scripts/install_module.py module.zip --dry-run
    python scripts/install_module.py module.zip --force
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List


class SecurityError(Exception):
    """Security violation exception"""
    pass


class ValidationError(Exception):
    """Validation error exception"""
    pass


class InstallationError(Exception):
    """Installation failed exception"""
    pass


class ModuleInstaller:
    """Module installation manager"""

    MAX_ZIP_SIZE = 100 * 1024 * 1024  # 100MB
    MAX_EXTRACTED_SIZE = 500 * 1024 * 1024  # 500MB
    FORBIDDEN_EXTENSIONS = ['.exe', '.dll', '.so', '.dylib', '.sh', '.bat', '.cmd']
    SUSPICIOUS_PATTERNS = ['eval(', 'exec(', '__import__', 'subprocess.call', 'os.system']

    def __init__(self, zip_path: str, dry_run: bool = False, force: bool = False):
        self.zip_path = Path(zip_path)
        self.dry_run = dry_run
        self.force = force

        # Project paths
        self.project_root = Path(__file__).parent.parent
        self.modules_dir = self.project_root / 'modules'
        self.backups_dir = self.project_root / 'backups'
        self.backups_dir.mkdir(exist_ok=True)

        # Installation state
        self.temp_dir: Optional[Path] = None
        self.module_code: Optional[str] = None
        self.manifest: Optional[Dict] = None
        self.backup_path: Optional[Path] = None

    def install(self):
        """Main installation process"""
        print("\n" + "=" * 60)
        print("📦 TriFlow Module Installer")
        print("=" * 60)

        if self.dry_run:
            print("🔍 DRY RUN MODE - No changes will be made")

        try:
            # Step 1: Validate ZIP file
            self.step(1, 13, "📂 Loading ZIP file")
            self.validate_zip_file()

            # Step 2: Parse manifest
            self.step(2, 13, "📋 Parsing manifest.json")
            self.parse_manifest()

            # Step 3: Security scan
            self.step(3, 13, "🔍 Security scan")
            self.security_scan()

            # Step 4: Version conflict check
            self.step(4, 13, "🔄 Version conflict check")
            self.check_version_conflict()

            # Step 5: Dependency check
            self.step(5, 13, "📦 Dependency check")
            self.check_dependencies()

            # Step 6: Backup existing module
            self.step(6, 13, "💾 Backup existing module")
            self.backup_existing()

            # Step 7: Extract files
            self.step(7, 13, "📂 Extracting files")
            self.extract_files()

            # Step 8: Install Python dependencies
            self.step(8, 13, "📦 Installing Python dependencies")
            self.install_python_dependencies()

            # Step 9: Install Node.js dependencies
            self.step(9, 13, "📦 Installing Node.js dependencies")
            self.install_node_dependencies()

            # Step 10: Copy module files
            self.step(10, 13, "📁 Copying module files")
            self.copy_module_files()

            # Step 11: Build registry
            self.step(11, 13, "🔨 Building module registry")
            self.build_registry()

            # Step 12: Build frontend imports
            self.step(12, 13, "🔨 Building frontend imports")
            self.build_frontend_imports()

            # Step 13: Sync to database
            self.step(13, 13, "💾 Syncing to database")
            self.sync_to_database()

            # Success!
            self.print_success()

        except (SecurityError, ValidationError, InstallationError) as e:
            self.print_error(str(e))
            self.rollback()
            sys.exit(1)

        except Exception as e:
            self.print_error(f"Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            self.rollback()
            sys.exit(1)

        finally:
            self.cleanup()

    def step(self, current: int, total: int, message: str):
        """Print step progress"""
        print(f"\n[{current}/{total}] {message}...")

    def validate_zip_file(self):
        """Validate ZIP file"""
        # Check file exists
        if not self.zip_path.exists():
            raise ValidationError(f"File not found: {self.zip_path}")

        # Check file size
        file_size = self.zip_path.stat().st_size
        print(f"  File: {self.zip_path.name}")
        print(f"  Size: {file_size / 1024 / 1024:.2f} MB")

        if file_size > self.MAX_ZIP_SIZE:
            raise ValidationError(f"ZIP file too large (max {self.MAX_ZIP_SIZE / 1024 / 1024}MB)")

        # Validate ZIP integrity
        try:
            with zipfile.ZipFile(self.zip_path, 'r') as zf:
                # Check for manifest.json
                if 'manifest.json' not in zf.namelist():
                    raise ValidationError("manifest.json not found in ZIP")

                # Check total extracted size
                total_size = sum(info.file_size for info in zf.infolist())
                if total_size > self.MAX_EXTRACTED_SIZE:
                    raise ValidationError(f"Extracted size too large (max {self.MAX_EXTRACTED_SIZE / 1024 / 1024}MB)")

        except zipfile.BadZipFile:
            raise ValidationError("Invalid or corrupted ZIP file")

        print("  ✅ Valid ZIP file")

    def parse_manifest(self):
        """Parse and validate manifest.json"""
        with zipfile.ZipFile(self.zip_path, 'r') as zf:
            manifest_data = zf.read('manifest.json')
            self.manifest = json.loads(manifest_data)

        # Validate required fields
        required_fields = ['module_code', 'version', 'name', 'category']
        for field in required_fields:
            if field not in self.manifest:
                raise ValidationError(f"Missing required field in manifest: {field}")

        self.module_code = self.manifest['module_code']

        # Validate module_code format
        if not re.match(r'^[a-z][a-z0-9_]*$', self.module_code):
            raise ValidationError(f"Invalid module_code format: {self.module_code}")

        # Validate version (semver)
        if not re.match(r'^\d+\.\d+\.\d+$', self.manifest['version']):
            raise ValidationError(f"Invalid version format: {self.manifest['version']}")

        # Validate category
        valid_categories = ['core', 'feature', 'industry', 'integration']
        if self.manifest['category'] not in valid_categories:
            raise ValidationError(f"Invalid category: {self.manifest['category']}")

        print(f"  Module: {self.module_code}")
        print(f"  Version: {self.manifest['version']}")
        print(f"  Name: {self.manifest['name']}")
        print(f"  Author: {self.manifest.get('author', 'Unknown')}")
        print(f"  Category: {self.manifest['category']}")
        print("  ✅ Manifest valid")

    def security_scan(self):
        """Perform security scan"""
        print("  Checking for malicious files...")

        with zipfile.ZipFile(self.zip_path, 'r') as zf:
            for member in zf.namelist():
                # Check for path traversal
                if member.startswith('/') or '..' in member:
                    raise SecurityError(f"Path traversal detected: {member}")

                # Check for forbidden extensions
                ext = os.path.splitext(member)[1].lower()
                if ext in self.FORBIDDEN_EXTENSIONS:
                    raise SecurityError(f"Forbidden file type: {member} ({ext})")

                # Warn about suspicious Python code
                if ext == '.py':
                    content = zf.read(member).decode('utf-8', errors='ignore')
                    for pattern in self.SUSPICIOUS_PATTERNS:
                        if pattern in content:
                            print(f"  ⚠️  Warning: Suspicious pattern '{pattern}' in {member}")

        print("  ✅ Security check passed")

    def check_version_conflict(self):
        """Check for version conflicts"""
        module_dir = self.modules_dir / self.module_code

        if not module_dir.exists():
            print(f"  Module '{self.module_code}' not found")
            print("  ✅ Clean install")
            return

        # Load existing manifest
        existing_manifest_path = module_dir / 'manifest.json'
        if not existing_manifest_path.exists():
            print("  ⚠️  Existing module has no manifest.json")
            if not self.force:
                raise ValidationError("Cannot determine existing version. Use --force to override")
            return

        with open(existing_manifest_path, 'r', encoding='utf-8') as f:
            existing_manifest = json.load(f)

        existing_version = existing_manifest.get('version', '0.0.0')
        new_version = self.manifest['version']

        print(f"  Existing version: {existing_version}")
        print(f"  New version: {new_version}")

        # Parse versions
        existing_parts = list(map(int, existing_version.split('.')))
        new_parts = list(map(int, new_version.split('.')))

        if new_parts > existing_parts:
            print("  ✅ Upgrade detected")
        elif new_parts < existing_parts:
            if not self.force:
                raise ValidationError(
                    f"Downgrade not allowed (use --force)\n"
                    f"  Current: {existing_version}, New: {new_version}"
                )
            print("  ⚠️  Downgrade detected (forced)")
        else:
            print("  ⚠️  Same version (will reinstall)")

    def check_dependencies(self):
        """Check module dependencies"""
        # Check depends_on modules
        depends_on = self.manifest.get('depends_on', [])
        if depends_on:
            print(f"  Required modules: {depends_on}")

            # Load registry to check installed modules
            registry_path = self.modules_dir / '_registry.json'
            if registry_path.exists():
                with open(registry_path, 'r', encoding='utf-8') as f:
                    registry = json.load(f)

                installed_modules = [m['module_code'] for m in registry.get('modules', [])]
                missing = [m for m in depends_on if m not in installed_modules]

                if missing:
                    raise ValidationError(
                        f"Missing required modules: {', '.join(missing)}\n"
                        f"  Please install them first"
                    )

                for dep in depends_on:
                    print(f"  ✅ {dep}: installed")

        # Check subscription requirement
        requires_sub = self.manifest.get('requires_subscription')
        if requires_sub:
            print(f"  Subscription required: {requires_sub}")
            # TODO: Check tenant subscription plan
            print("  ⚠️  Subscription check skipped (not implemented)")

        # Check platform version
        min_version = self.manifest.get('min_triflow_version')
        if min_version:
            print(f"  Platform version: >= {min_version}")
            # TODO: Check current TriFlow version
            print("  ⚠️  Version check skipped (not implemented)")

        if not depends_on and not requires_sub:
            print("  ✅ No dependencies")

    def backup_existing(self):
        """Backup existing module"""
        module_dir = self.modules_dir / self.module_code

        if not module_dir.exists():
            print("  ⏭️  Skipped (no existing module)")
            return

        if self.dry_run:
            print("  🔍 Would create backup (dry run)")
            return

        # Create backup
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.backup_path = self.backups_dir / f"{self.module_code}_{timestamp}"

        shutil.copytree(module_dir, self.backup_path)
        print(f"  ✅ Backup created: {self.backup_path.name}")

    def extract_files(self):
        """Extract ZIP to temporary directory"""
        if self.dry_run:
            print("  🔍 Would extract files (dry run)")
            return

        # Create temp directory
        self.temp_dir = Path(tempfile.mkdtemp(prefix='triflow_install_'))

        with zipfile.ZipFile(self.zip_path, 'r') as zf:
            zf.extractall(self.temp_dir)

        file_count = sum(1 for _ in self.temp_dir.rglob('*') if _.is_file())
        print(f"  Extracting to: {self.temp_dir}")
        print(f"  Files extracted: {file_count}")
        print("  ✅ Extraction complete")

    def install_python_dependencies(self):
        """Install Python dependencies"""
        # Check for requirements.txt
        if self.temp_dir:
            req_file = self.temp_dir / 'requirements.txt'
        else:
            req_file = None

        python_deps = self.manifest.get('python_dependencies', [])

        if not req_file or not req_file.exists():
            req_file = None

        if not req_file and not python_deps:
            print("  ⏭️  No Python dependencies")
            return

        if self.dry_run:
            print("  🔍 Would install Python dependencies (dry run)")
            if req_file:
                print(f"     From: requirements.txt")
            if python_deps:
                print(f"     Packages: {', '.join(python_deps)}")
            return

        try:
            if req_file:
                print(f"  Found: requirements.txt")
                print(f"  $ pip install -r requirements.txt")

                subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', '-r', str(req_file)],
                    check=True,
                    capture_output=True,
                    text=True
                )
            elif python_deps:
                print(f"  Installing: {', '.join(python_deps)}")
                subprocess.run(
                    [sys.executable, '-m', 'pip', 'install'] + python_deps,
                    check=True,
                    capture_output=True,
                    text=True
                )

            print("  ✅ Python dependencies installed")

        except subprocess.CalledProcessError as e:
            raise InstallationError(f"Failed to install Python dependencies:\n{e.stderr}")

    def install_node_dependencies(self):
        """Install Node.js dependencies"""
        node_deps = self.manifest.get('node_dependencies', {})

        if not node_deps:
            print("  ⏭️  No Node.js dependencies")
            return

        if self.dry_run:
            print("  🔍 Would install Node.js dependencies (dry run)")
            print(f"     Packages: {', '.join(node_deps.keys())}")
            return

        try:
            frontend_dir = self.project_root / 'frontend'

            # Add to package.json
            package_json_path = frontend_dir / 'package.json'
            with open(package_json_path, 'r', encoding='utf-8') as f:
                package_json = json.load(f)

            print(f"  Adding to frontend/package.json:")
            for pkg, version in node_deps.items():
                package_json['dependencies'][pkg] = version
                print(f"    - {pkg}: {version}")

            with open(package_json_path, 'w', encoding='utf-8') as f:
                json.dump(package_json, f, indent=2, ensure_ascii=False)

            # Run npm install
            print("  $ npm install")
            subprocess.run(
                ['npm', 'install'],
                cwd=str(frontend_dir),
                check=True,
                capture_output=True,
                text=True
            )

            print("  ✅ Node.js dependencies installed")

        except subprocess.CalledProcessError as e:
            raise InstallationError(f"Failed to install Node.js dependencies:\n{e.stderr}")

    def copy_module_files(self):
        """Copy module files to modules directory"""
        if self.dry_run:
            print("  🔍 Would copy files (dry run)")
            print(f"     Target: modules/{self.module_code}/")
            return

        target_dir = self.modules_dir / self.module_code

        # Remove existing module
        if target_dir.exists():
            shutil.rmtree(target_dir)

        # Copy from temp
        shutil.copytree(self.temp_dir, target_dir)

        file_count = sum(1 for _ in target_dir.rglob('*') if _.is_file())
        print(f"  Source: {self.temp_dir}")
        print(f"  Target: {target_dir}")
        print(f"  Files copied: {file_count}")
        print("  ✅ Files copied")

    def build_registry(self):
        """Build module registry"""
        if self.dry_run:
            print("  🔍 Would build registry (dry run)")
            return

        try:
            subprocess.run(
                [sys.executable, 'scripts/build_module_registry.py'],
                cwd=str(self.project_root),
                check=True,
                capture_output=True,
                text=True
            )
            print("  ✅ Registry built")

        except subprocess.CalledProcessError as e:
            print(f"  ⚠️  Warning: Registry build failed: {e.stderr}")

    def build_frontend_imports(self):
        """Build frontend imports"""
        if self.dry_run:
            print("  🔍 Would build frontend imports (dry run)")
            return

        try:
            subprocess.run(
                [sys.executable, 'scripts/build_frontend_imports.py'],
                cwd=str(self.project_root),
                check=True,
                capture_output=True,
                text=True
            )
            print("  ✅ Frontend imports updated")

        except subprocess.CalledProcessError as e:
            print(f"  ⚠️  Warning: Frontend build failed: {e.stderr}")

    def sync_to_database(self):
        """Sync module to database"""
        if self.dry_run:
            print("  🔍 Would sync to database (dry run)")
            return

        # TODO: Call module_loader.sync_modules_to_db()
        print("  ⚠️  Database sync skipped (manual sync required)")
        print("     Run: from app.module_loader import sync_modules_to_db; sync_modules_to_db()")

    def rollback(self):
        """Rollback on failure"""
        print("\n🔄 Rolling back...")

        # Restore from backup
        if self.backup_path and self.backup_path.exists():
            target_dir = self.modules_dir / self.module_code
            if target_dir.exists():
                shutil.rmtree(target_dir)
            shutil.copytree(self.backup_path, target_dir)
            print("  ✅ Restored from backup")

        # Clean up temp
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
            print("  ✅ Removed temporary files")

        print("\n❌ Installation failed. System restored to previous state.")

    def cleanup(self):
        """Clean up temporary files"""
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def print_success(self):
        """Print success message"""
        print("\n" + "=" * 60)
        print("✅ Installation Complete!")
        print("=" * 60)

        print(f"\n📦 Module: {self.module_code} v{self.manifest['version']}")
        print(f"📁 Location: {self.modules_dir / self.module_code}")

        if not self.dry_run:
            print("\n📝 Next Steps:")
            print("  1. Restart backend server:")
            print("     uvicorn app.main:app --reload")
            print("")
            print("  2. Restart frontend dev server:")
            print("     npm run dev --prefix frontend")
            print("")
            print("  3. Enable module (Admin only):")
            print(f"     Settings → Tenant Modules → Enable '{self.module_code}'")

            # API info
            if 'backend' in self.manifest:
                api_prefix = self.manifest['backend'].get('api_prefix', '')
                print(f"\n💡 Module Info:")
                print(f"   - API Endpoints: {api_prefix}/*")

            if 'frontend' in self.manifest:
                page_component = self.manifest['frontend'].get('page_component', '')
                print(f"   - Page Component: {page_component}")

    def print_error(self, message: str):
        """Print error message"""
        print(f"\n❌ ERROR: {message}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Install TriFlow module from ZIP file"
    )
    parser.add_argument(
        'zip_file',
        help="Path to module ZIP file"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Validate only, do not install"
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help="Force installation (overwrite existing, allow downgrade)"
    )

    args = parser.parse_args()

    installer = ModuleInstaller(
        zip_path=args.zip_file,
        dry_run=args.dry_run,
        force=args.force
    )

    installer.install()


if __name__ == "__main__":
    main()
