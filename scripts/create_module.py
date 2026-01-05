#!/usr/bin/env python
"""
Module Scaffolding Tool
새 모듈의 기본 구조를 자동으로 생성합니다.

사용법:
    python scripts/create_module.py <module_code> --name "모듈 이름" [옵션]

예시:
    python scripts/create_module.py quality_analytics --name "품질 분석" --category feature
    python scripts/create_module.py quality_pharma --name "품질관리 (제약)" --category industry
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


def to_pascal_case(snake_str: str) -> str:
    """snake_case를 PascalCase로 변환"""
    components = snake_str.split('_')
    return ''.join(x.title() for x in components)


def validate_module_code(code: str) -> bool:
    """모듈 코드 유효성 검증"""
    pattern = r'^[a-z][a-z0-9_]*$'
    return bool(re.match(pattern, code))


def create_manifest(
    module_code: str,
    name: str,
    description: str,
    category: str,
    icon: str,
    requires_subscription: Optional[str],
    display_order: int,
    admin_only: bool,
) -> dict:
    """manifest.json 생성"""
    pascal_name = to_pascal_case(module_code)

    manifest = {
        "$schema": "../module-schema.json",
        "module_code": module_code,
        "version": "1.0.0",
        "name": name,
        "description": description,
        "category": category,
        "icon": icon,
        "default_enabled": False,
        "requires_subscription": requires_subscription,
        "depends_on": [],
        "display_order": display_order,
        "backend": {
            "router_path": f"modules.{module_code}.backend.router",
            "api_prefix": f"/api/v1/{module_code.replace('_', '-')}",
            "tags": [module_code.replace('_', '-')]
        },
        "frontend": {
            "page_component": f"{pascal_name}Page",
            "admin_only": admin_only
        },
        "author": "TriFlow AI Team",
        "license": "proprietary"
    }

    return manifest


def create_backend_files(module_dir: Path, module_code: str, name: str):
    """백엔드 파일 생성"""
    backend_dir = module_dir / "backend"
    backend_dir.mkdir(parents=True, exist_ok=True)

    # __init__.py
    (backend_dir / "__init__.py").write_text(
        f'"""\n{name} Module Backend\n"""\n',
        encoding="utf-8"
    )

    # router.py
    router_content = f'''"""
{name} Module - API Router
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.core import User

router = APIRouter()


@router.get("/")
async def get_{module_code}_info(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    {name} 모듈 정보 조회
    """
    return {{
        "module": "{module_code}",
        "name": "{name}",
        "status": "active",
        "tenant_id": str(current_user.tenant_id)
    }}


@router.get("/config")
async def get_{module_code}_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    {name} 모듈 설정 조회
    """
    # TODO: 모듈별 설정 구현
    return {{
        "module": "{module_code}",
        "config": {{}}
    }}
'''

    (backend_dir / "router.py").write_text(router_content, encoding="utf-8")

    # service.py
    service_content = f'''"""
{name} Module - Business Logic Service
"""
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session


class {to_pascal_case(module_code)}Service:
    """
    {name} 서비스

    이 클래스에 모듈의 비즈니스 로직을 구현하세요.
    """

    def __init__(self, db: Session):
        self.db = db

    async def process(self, tenant_id: UUID, data: dict) -> dict:
        """
        데이터 처리

        Args:
            tenant_id: 테넌트 ID
            data: 입력 데이터

        Returns:
            처리 결과
        """
        # TODO: 비즈니스 로직 구현
        return {{
            "status": "processed",
            "data": data
        }}
'''

    (backend_dir / "service.py").write_text(service_content, encoding="utf-8")


def create_frontend_files(module_dir: Path, module_code: str, name: str, icon: str):
    """프론트엔드 파일 생성"""
    frontend_dir = module_dir / "frontend"
    frontend_dir.mkdir(parents=True, exist_ok=True)
    components_dir = frontend_dir / "components"
    components_dir.mkdir(exist_ok=True)

    pascal_name = to_pascal_case(module_code)

    # Main Page Component
    page_content = f'''/**
 * {name} Page
 *
 * 모듈 메인 페이지 컴포넌트
 */
import React from 'react';
import {{ {icon} }} from 'lucide-react';

interface {pascal_name}PageProps {{
  // 필요한 props 정의
}}

export default function {pascal_name}Page(_props: {pascal_name}PageProps) {{
  return (
    <div className="p-6 space-y-6">
      {{/* Header */}}
      <div className="flex items-center gap-3">
        <{icon} className="w-8 h-8 text-blue-600" />
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{name}</h1>
          <p className="text-gray-500">모듈 설명을 여기에 입력하세요</p>
        </div>
      </div>

      {{/* Content */}}
      <div className="bg-white rounded-lg shadow p-6">
        <p className="text-gray-600">
          {name} 모듈의 콘텐츠를 여기에 구현하세요.
        </p>
      </div>
    </div>
  );
}}
'''

    (frontend_dir / f"{pascal_name}Page.tsx").write_text(page_content, encoding="utf-8")

    # Example Component
    example_component = f'''/**
 * {name} - Example Component
 */
import React from 'react';

interface {pascal_name}CardProps {{
  title: string;
  value: string | number;
}}

export function {pascal_name}Card({{ title, value }}: {pascal_name}CardProps) {{
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="text-sm font-medium text-gray-500">{{title}}</h3>
      <p className="text-2xl font-bold text-gray-900">{{value}}</p>
    </div>
  );
}}
'''

    (components_dir / f"{pascal_name}Card.tsx").write_text(example_component, encoding="utf-8")


def create_module(
    module_code: str,
    name: str,
    description: str = "",
    category: str = "feature",
    icon: str = "Box",
    requires_subscription: Optional[str] = None,
    display_order: int = 100,
    admin_only: bool = False,
):
    """모듈 스캐폴딩 생성"""
    # 프로젝트 루트 찾기
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    modules_dir = project_root / "modules"
    module_dir = modules_dir / module_code

    # 유효성 검증
    if not validate_module_code(module_code):
        print(f"Error: Invalid module code '{module_code}'")
        print("Module code must start with lowercase letter and contain only lowercase letters, numbers, and underscores")
        sys.exit(1)

    if module_dir.exists():
        print(f"Error: Module '{module_code}' already exists at {module_dir}")
        sys.exit(1)

    # 디렉토리 생성
    module_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nCreating module: {module_code}")
    print(f"Location: {module_dir}")
    print("-" * 50)

    # manifest.json 생성
    manifest = create_manifest(
        module_code=module_code,
        name=name,
        description=description or f"{name} 모듈",
        category=category,
        icon=icon,
        requires_subscription=requires_subscription,
        display_order=display_order,
        admin_only=admin_only,
    )

    manifest_path = module_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    print(f"  [OK] manifest.json")

    # Backend 파일 생성
    create_backend_files(module_dir, module_code, name)
    print(f"  [OK] backend/router.py")
    print(f"  [OK] backend/service.py")

    # Frontend 파일 생성
    create_frontend_files(module_dir, module_code, name, icon)
    pascal_name = to_pascal_case(module_code)
    print(f"  [OK] frontend/{pascal_name}Page.tsx")
    print(f"  [OK] frontend/components/{pascal_name}Card.tsx")

    print("-" * 50)
    print(f"\nModule '{module_code}' created successfully!")
    print("\nNext steps:")
    print("  1. Edit manifest.json to customize module settings")
    print("  2. Implement business logic in backend/service.py")
    print("  3. Build the UI in frontend/ components")
    print("  4. Run: python scripts/build_module_registry.py")
    print("  5. Restart the backend server")


def main():
    parser = argparse.ArgumentParser(
        description="Create a new TriFlow AI module",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/create_module.py quality_analytics --name "품질 분석"
  python scripts/create_module.py quality_pharma --name "품질관리 (제약)" --category industry
  python scripts/create_module.py reporting --name "리포팅" --icon BarChart --subscription standard
        """
    )

    parser.add_argument(
        "module_code",
        help="Module code (lowercase, underscores allowed, e.g., 'quality_analytics')"
    )
    parser.add_argument(
        "--name", "-n",
        required=True,
        help="Display name for the module (e.g., '품질 분석')"
    )
    parser.add_argument(
        "--description", "-d",
        default="",
        help="Module description"
    )
    parser.add_argument(
        "--category", "-c",
        choices=["core", "feature", "industry", "integration"],
        default="feature",
        help="Module category (default: feature)"
    )
    parser.add_argument(
        "--icon", "-i",
        default="Box",
        help="Lucide icon name (default: Box)"
    )
    parser.add_argument(
        "--subscription", "-s",
        choices=["free", "standard", "enterprise"],
        default=None,
        help="Minimum subscription plan required"
    )
    parser.add_argument(
        "--order", "-o",
        type=int,
        default=100,
        help="Display order in navigation (default: 100)"
    )
    parser.add_argument(
        "--admin-only",
        action="store_true",
        help="Only visible to admin users"
    )

    args = parser.parse_args()

    create_module(
        module_code=args.module_code,
        name=args.name,
        description=args.description,
        category=args.category,
        icon=args.icon,
        requires_subscription=args.subscription,
        display_order=args.order,
        admin_only=args.admin_only,
    )


if __name__ == "__main__":
    main()
