#!/usr/bin/env python
"""
Module Registry Builder
모듈 매니페스트를 스캔하여 레지스트리 JSON 파일을 생성합니다.

사용법:
    python scripts/build_module_registry.py
"""
import json
import sys
from datetime import datetime
from pathlib import Path


def validate_manifest(manifest: dict, manifest_path: Path) -> list[str]:
    """매니페스트 기본 검증"""
    errors = []

    required_fields = ["module_code", "name", "category", "version"]
    for field in required_fields:
        if field not in manifest:
            errors.append(f"Missing required field: {field}")

    if "category" in manifest:
        valid_categories = ["core", "feature", "industry", "integration"]
        if manifest["category"] not in valid_categories:
            errors.append(f"Invalid category: {manifest['category']}")

    if "version" in manifest:
        import re
        if not re.match(r"^\d+\.\d+\.\d+$", manifest["version"]):
            errors.append(f"Invalid version format: {manifest['version']}")

    return errors


def build_registry():
    """모듈 매니페스트를 스캔하여 레지스트리 생성"""
    # 프로젝트 루트 찾기
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    modules_dir = project_root / "modules"

    if not modules_dir.exists():
        print(f"Error: modules directory not found at {modules_dir}")
        sys.exit(1)

    registry = {
        "version": "1.0.0",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "modules": []
    }

    errors_found = False

    for module_dir in sorted(modules_dir.iterdir()):
        # 디렉토리가 아니거나 _로 시작하면 스킵
        if not module_dir.is_dir() or module_dir.name.startswith("_"):
            continue

        manifest_path = module_dir / "manifest.json"
        if not manifest_path.exists():
            print(f"  [SKIP] {module_dir.name}: No manifest.json found")
            continue

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

            # 검증
            validation_errors = validate_manifest(manifest, manifest_path)
            if validation_errors:
                print(f"  [ERROR] {module_dir.name}:")
                for err in validation_errors:
                    print(f"    - {err}")
                errors_found = True
                continue

            registry["modules"].append(manifest)
            print(f"  [OK] {manifest['module_code']}: {manifest['name']}")

        except json.JSONDecodeError as e:
            print(f"  [ERROR] {module_dir.name}: Invalid JSON - {e}")
            errors_found = True
        except Exception as e:
            print(f"  [ERROR] {module_dir.name}: {e}")
            errors_found = True

    # display_order로 정렬
    registry["modules"].sort(key=lambda m: m.get("display_order", 999))

    # 레지스트리 저장
    output_path = modules_dir / "_registry.json"
    output_path.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print(f"\n{'='*50}")
    print(f"Registry generated: {output_path}")
    print(f"Total modules: {len(registry['modules'])}")
    print(f"Generated at: {registry['generated_at']}")

    if errors_found:
        print("\n[WARNING] Some modules had errors and were skipped.")
        sys.exit(1)


def main():
    print("="*50)
    print("TriFlow AI - Module Registry Builder")
    print("="*50)
    print()

    build_registry()


if __name__ == "__main__":
    main()
