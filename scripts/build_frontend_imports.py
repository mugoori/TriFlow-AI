#!/usr/bin/env python
"""
Frontend Import Map Builder
모듈 매니페스트를 스캔하여 프론트엔드 동적 임포트 맵을 생성합니다.

사용법:
    python scripts/build_frontend_imports.py
"""
import json
import sys
from datetime import datetime
from pathlib import Path


def build_import_map():
    """프론트엔드 동적 임포트 맵 생성"""
    # 프로젝트 루트 찾기
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    modules_dir = project_root / "modules"
    frontend_dir = project_root / "frontend" / "src" / "modules"

    if not modules_dir.exists():
        print(f"Error: modules directory not found at {modules_dir}")
        sys.exit(1)

    # frontend/src/modules 디렉토리 생성
    frontend_dir.mkdir(parents=True, exist_ok=True)

    imports = []
    module_list = []

    for module_dir in sorted(modules_dir.iterdir()):
        if not module_dir.is_dir() or module_dir.name.startswith("_"):
            continue

        manifest_path = module_dir / "manifest.json"
        if not manifest_path.exists():
            continue

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            frontend_config = manifest.get("frontend", {})
            component = frontend_config.get("page_component")

            if component:
                module_code = manifest["module_code"]
                # 모듈 경로 결정: modules 폴더 또는 기존 pages 폴더
                module_path = f"@/modules/{module_code}/frontend/{component}"

                imports.append(
                    f"  {component}: lazy(() => import('{module_path}')),"
                )
                module_list.append({
                    "module_code": module_code,
                    "component": component,
                    "path": module_path
                })

                print(f"  [OK] {module_code} -> {component}")

        except Exception as e:
            print(f"  [ERROR] {module_dir.name}: {e}")

    # TypeScript 파일 생성
    output_content = f"""// AUTO-GENERATED - DO NOT EDIT
// Generated at: {datetime.utcnow().isoformat()}Z
// Run: python scripts/build_frontend_imports.py

import {{ lazy }} from 'react';

/**
 * 동적으로 로드되는 모듈 페이지 컴포넌트 맵
 * 빌드 시 자동 생성됩니다.
 */
export const PAGE_COMPONENTS: Record<string, React.LazyExoticComponent<React.ComponentType<any>>> = {{
{chr(10).join(imports)}
}};

/**
 * 모듈 코드로 페이지 컴포넌트를 가져옵니다.
 */
export function getPageComponent(moduleCode: string): React.LazyExoticComponent<React.ComponentType<any>> | null {{
  const component = Object.entries(PAGE_COMPONENTS).find(
    ([name, _]) => name.toLowerCase().replace('page', '') === moduleCode.toLowerCase()
  );
  return component ? component[1] : null;
}}

/**
 * 등록된 모든 모듈 코드 목록
 */
export const REGISTERED_MODULES = {json.dumps([m['module_code'] for m in module_list], indent=2)};
"""

    output_path = frontend_dir / "_imports.ts"
    output_path.write_text(output_content, encoding="utf-8")

    print(f"\n{'='*50}")
    print(f"Import map generated: {output_path}")
    print(f"Total components: {len(imports)}")


def main():
    print("="*50)
    print("TriFlow AI - Frontend Import Map Builder")
    print("="*50)
    print()

    build_import_map()


if __name__ == "__main__":
    main()
