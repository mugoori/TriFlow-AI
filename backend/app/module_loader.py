"""
Module Loader
플러그인 모듈의 라우터를 동적으로 로드합니다.

사용법:
    from app.module_loader import load_module_routers
    load_module_routers(app)
"""
import importlib
import json
import logging
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI

logger = logging.getLogger(__name__)


def _ensure_modules_in_path():
    """modules 디렉토리를 Python path에 추가"""
    # backend/app/module_loader.py -> project_root
    current_file = Path(__file__)
    project_root = current_file.parent.parent.parent

    # project_root를 path에 추가 (modules 패키지 임포트 가능)
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)
        logger.debug(f"Added to Python path: {project_root_str}")


class ModuleLoadError(Exception):
    """모듈 로딩 실패 예외"""
    pass


def get_modules_directory() -> Path:
    """모듈 디렉토리 경로 반환"""
    # backend/app/module_loader.py -> project_root/modules
    current_file = Path(__file__)
    project_root = current_file.parent.parent.parent
    return project_root / "modules"


def load_manifest(module_dir: Path) -> Optional[dict]:
    """모듈 매니페스트 로드"""
    manifest_path = module_dir / "manifest.json"

    if not manifest_path.exists():
        return None

    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        logger.error(f"Invalid manifest JSON in {module_dir.name}: {e}")
        return None


def validate_manifest(manifest: dict) -> bool:
    """매니페스트 유효성 검증"""
    required_fields = ["module_code", "name", "category", "version"]

    for field in required_fields:
        if field not in manifest:
            logger.error(f"Missing required field '{field}' in manifest")
            return False

    return True


def load_module_router(app: FastAPI, manifest: dict, module_dir: Path) -> bool:
    """개별 모듈 라우터 로드"""
    module_code = manifest["module_code"]
    backend_config = manifest.get("backend", {})

    router_path = backend_config.get("router_path")
    if not router_path:
        logger.debug(f"Module '{module_code}' has no backend router")
        return True  # 프론트엔드 전용 모듈일 수 있음

    try:
        # 동적 임포트
        router_module = importlib.import_module(router_path)

        if not hasattr(router_module, "router"):
            logger.error(f"Module '{module_code}' router has no 'router' attribute")
            return False

        # 라우터 등록
        api_prefix = backend_config.get("api_prefix", f"/api/v1/{module_code}")
        tags = backend_config.get("tags", [module_code])

        app.include_router(
            router_module.router,
            prefix=api_prefix,
            tags=tags
        )

        logger.info(f"Module '{module_code}' router registered at {api_prefix}")
        return True

    except ImportError as e:
        logger.error(f"Failed to import module '{module_code}': {e}")
        return False
    except Exception as e:
        logger.error(f"Error loading module '{module_code}': {e}")
        return False


def load_module_routers(app: FastAPI) -> dict:
    """
    모듈 매니페스트 기반 라우터 자동 등록

    Returns:
        dict: 로딩 결과 요약 {"loaded": [...], "failed": [...], "skipped": [...]}
    """
    # modules 디렉토리를 Python path에 추가
    _ensure_modules_in_path()

    modules_dir = get_modules_directory()

    result = {
        "loaded": [],
        "failed": [],
        "skipped": []
    }

    if not modules_dir.exists():
        logger.warning(f"Modules directory not found: {modules_dir}")
        return result

    logger.info(f"Loading modules from: {modules_dir}")

    for module_dir in sorted(modules_dir.iterdir()):
        # 디렉토리가 아니거나 _로 시작하면 스킵
        if not module_dir.is_dir() or module_dir.name.startswith("_"):
            continue

        manifest = load_manifest(module_dir)

        if manifest is None:
            result["skipped"].append(module_dir.name)
            continue

        if not validate_manifest(manifest):
            result["failed"].append(module_dir.name)
            continue

        module_code = manifest["module_code"]

        if load_module_router(app, manifest, module_dir):
            result["loaded"].append(module_code)
        else:
            result["failed"].append(module_code)

    # 요약 로그
    logger.info(
        f"Module loading complete: "
        f"{len(result['loaded'])} loaded, "
        f"{len(result['failed'])} failed, "
        f"{len(result['skipped'])} skipped"
    )

    return result


def get_loaded_modules() -> list[dict]:
    """로드된 모듈 목록 반환 (레지스트리에서 읽음)"""
    modules_dir = get_modules_directory()
    registry_path = modules_dir / "_registry.json"

    if not registry_path.exists():
        return []

    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        return registry.get("modules", [])
    except Exception as e:
        logger.error(f"Failed to read module registry: {e}")
        return []


def sync_modules_to_db():
    """
    모듈 매니페스트를 DB의 module_definitions 테이블과 동기화

    주의: 이 함수는 앱 시작 시 호출되어야 합니다.
    """
    from app.database import get_db_context
    from sqlalchemy import text

    modules = get_loaded_modules()

    if not modules:
        logger.info("No modules to sync to database")
        return

    with get_db_context() as db:
        for manifest in modules:
            try:
                db.execute(
                    text("""
                        INSERT INTO core.module_definitions
                        (module_code, name, description, category, icon,
                         default_enabled, requires_subscription, depends_on, display_order, created_at)
                        VALUES
                        (:module_code, :name, :description, :category, :icon,
                         :default_enabled, :requires_subscription, :depends_on, :display_order, NOW())
                        ON CONFLICT (module_code) DO UPDATE SET
                            name = EXCLUDED.name,
                            description = EXCLUDED.description,
                            category = EXCLUDED.category,
                            icon = EXCLUDED.icon,
                            default_enabled = EXCLUDED.default_enabled,
                            requires_subscription = EXCLUDED.requires_subscription,
                            depends_on = EXCLUDED.depends_on,
                            display_order = EXCLUDED.display_order
                    """),
                    {
                        "module_code": manifest["module_code"],
                        "name": manifest["name"],
                        "description": manifest.get("description"),
                        "category": manifest["category"],
                        "icon": manifest.get("icon"),
                        "default_enabled": manifest.get("default_enabled", False),
                        "requires_subscription": manifest.get("requires_subscription"),
                        "depends_on": manifest.get("depends_on", []),
                        "display_order": manifest.get("display_order", 100),
                    }
                )
            except Exception as e:
                logger.error(f"Failed to sync module '{manifest['module_code']}': {e}")

        db.commit()
        logger.info(f"Synced {len(modules)} modules to database")
