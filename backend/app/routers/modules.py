"""
Module Management API
Upload, install, and manage TriFlow modules
"""
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_admin
from app.database import get_db
from app.models.core import User
from pydantic import BaseModel

logger = logging.getLogger(__name__)


router = APIRouter()


@router.get("/test")
async def test_endpoint():
    """Simple test endpoint without dependencies"""
    logger.info("[MODULE TEST] Test endpoint called")
    return {"status": "ok", "message": "Module router is working"}


# Schemas
class ModuleInfo(BaseModel):
    """Module information"""
    module_code: str
    name: str
    version: str
    category: str
    description: str
    author: Optional[str] = None
    icon: Optional[str] = None
    is_enabled: bool = False
    is_system: bool = False  # Core modules cannot be uninstalled
    can_uninstall: bool = True
    installed_at: Optional[datetime] = None


class InstallationProgress(BaseModel):
    """Installation progress"""
    installation_id: str
    module_code: str
    version: str
    status: str  # pending, installing, success, failed
    progress: int  # 0-100
    current_step: str
    current_step_index: int
    logs: List[dict]
    error: Optional[str] = None


class InstallResponse(BaseModel):
    """Installation response"""
    success: bool
    module_code: str
    version: str
    installation_id: str
    message: str


# API Endpoints
@router.get("/", response_model=List[ModuleInfo])
async def list_modules(
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List installed modules

    Returns all installed modules with their metadata.
    Admin users see all modules, regular users see only enabled ones.
    """
    project_root = Path(__file__).parent.parent.parent.parent
    registry_path = project_root / 'modules' / '_registry.json'

    if not registry_path.exists():
        return []

    # Load registry
    with open(registry_path, 'r', encoding='utf-8') as f:
        registry = json.load(f)

    modules = registry.get('modules', [])

    # Filter by category
    if category:
        modules = [m for m in modules if m.get('category') == category]

    # Convert to response format
    result = []
    for module in modules:
        module_code = module.get('module_code', '')
        is_core = module.get('category') == 'core'

        module_info = ModuleInfo(
            module_code=module_code,
            name=module.get('name', ''),
            version=module.get('version', '1.0.0'),
            category=module.get('category', 'feature'),
            description=module.get('description', ''),
            author=module.get('author'),
            icon=module.get('icon'),
            is_enabled=True,  # TODO: Check from DB
            is_system=is_core,
            can_uninstall=not is_core
        )
        result.append(module_info)

    return result


@router.post("/upload", response_model=InstallResponse)
async def upload_module(
    file: UploadFile = File(...),
    force: bool = False,
    current_user: User = Depends(get_current_user)  # 임시로 require_admin 대신 get_current_user 사용
):
    """
    Upload and install module from ZIP file

    Admin only. Validates, extracts, and installs the module.
    """
    logger.info(f"[MODULE UPLOAD] Started by user {current_user.email}")
    logger.info(f"[MODULE UPLOAD] File: {file.filename}, Force: {force}")

    # Check admin permission
    if current_user.role != "admin":
        logger.error(f"[MODULE UPLOAD] Permission denied for user role: {current_user.role}")
        raise HTTPException(status_code=403, detail="Admin privileges required")

    # Validate file type
    if not file.filename or not file.filename.endswith('.zip'):
        logger.error("[MODULE UPLOAD] Invalid file type")
        raise HTTPException(status_code=400, detail="Only ZIP files are allowed")

    installation_id = str(uuid4())
    temp_dir = None
    temp_zip_path = None

    try:
        logger.info("[MODULE UPLOAD] [1/6] Saving uploaded file...")
        # Save uploaded file to temp
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_zip_path = temp_file.name
        logger.info(f"[MODULE UPLOAD] [1/6] OK - Saved to: {temp_zip_path}")

        logger.info("[MODULE UPLOAD] [2/6] Validating ZIP...")
        # Validate ZIP
        if not zipfile.is_zipfile(temp_zip_path):
            logger.error("[MODULE UPLOAD] Invalid ZIP file")
            raise HTTPException(status_code=400, detail="Invalid ZIP file")
        logger.info("[MODULE UPLOAD] [2/6] OK - Valid ZIP file")

        logger.info("[MODULE UPLOAD] [3/6] Extracting manifest.json...")
        # Extract manifest
        with zipfile.ZipFile(temp_zip_path, 'r') as zf:
            if 'manifest.json' not in zf.namelist():
                logger.error("[MODULE UPLOAD] manifest.json not found")
                raise HTTPException(status_code=400, detail="manifest.json not found")

            manifest_data = zf.read('manifest.json')
            manifest = json.loads(manifest_data)
        logger.info("[MODULE UPLOAD] [3/6] OK - Manifest loaded")

        logger.info("[MODULE UPLOAD] [4/6] Validating manifest...")
        module_code = manifest.get('module_code')
        version = manifest.get('version')

        if not module_code or not version:
            logger.error(f"[MODULE UPLOAD] Missing fields in manifest: module_code={module_code}, version={version}")
            raise HTTPException(
                status_code=400,
                detail="manifest.json missing module_code or version"
            )
        logger.info(f"[MODULE UPLOAD] [4/6] OK - Module: {module_code} v{version}")

        logger.info("[MODULE UPLOAD] [5/6] Checking conflicts...")
        # Check version conflict
        project_root = Path(__file__).parent.parent.parent.parent
        modules_dir = project_root / 'modules'
        module_dir = modules_dir / module_code

        if module_dir.exists() and not force:
            logger.warning(f"[MODULE UPLOAD] Module '{module_code}' already exists")
            raise HTTPException(
                status_code=409,
                detail=f"Module '{module_code}' already exists. Use force=true to override"
            )
        logger.info("[MODULE UPLOAD] [5/6] OK - No conflicts")

        logger.info("[MODULE UPLOAD] [6/6] Installing module...")

        # Extract ZIP to modules directory
        if module_dir.exists():
            logger.info(f"[MODULE UPLOAD] Removing existing module at {module_dir}")
            shutil.rmtree(module_dir)

        logger.info(f"[MODULE UPLOAD] Extracting to {module_dir}")
        with zipfile.ZipFile(temp_zip_path, 'r') as zf:
            zf.extractall(module_dir)

        # Rebuild registry
        logger.info("[MODULE UPLOAD] Rebuilding registry...")
        try:
            subprocess.run(
                [sys.executable, str(project_root / 'scripts' / 'build_module_registry.py')],
                cwd=str(project_root),
                check=True,
                capture_output=True
            )
            logger.info("[MODULE UPLOAD] Registry rebuilt")
        except subprocess.CalledProcessError as e:
            logger.warning(f"[MODULE UPLOAD] Registry build warning: {e}")

        # Rebuild frontend imports
        logger.info("[MODULE UPLOAD] Rebuilding frontend imports...")
        try:
            subprocess.run(
                [sys.executable, str(project_root / 'scripts' / 'build_frontend_imports.py')],
                cwd=str(project_root),
                check=True,
                capture_output=True
            )
            logger.info("[MODULE UPLOAD] Frontend imports rebuilt")
        except subprocess.CalledProcessError as e:
            logger.warning(f"[MODULE UPLOAD] Frontend build warning: {e}")

        logger.info(f"[MODULE UPLOAD] SUCCESS - Module '{module_code}' installed at {module_dir}")

        return InstallResponse(
            success=True,
            module_code=module_code,
            version=version,
            installation_id=installation_id,
            message=f"Module '{module_code}' installed successfully! Please restart backend and frontend."
        )

    except HTTPException as e:
        logger.error(f"[MODULE UPLOAD] HTTPException: status={e.status_code}, detail={e.detail}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"[MODULE UPLOAD] Invalid manifest.json: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid manifest.json format: {str(e)}")
    except Exception as e:
        logger.exception(f"[MODULE UPLOAD] Unexpected error: {e}")
        import traceback
        error_detail = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_detail)
    finally:
        # Cleanup temp file
        if temp_zip_path and os.path.exists(temp_zip_path):
            try:
                os.unlink(temp_zip_path)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp file: {e}")


@router.delete("/{module_code}")
async def uninstall_module(
    module_code: str,
    keep_data: bool = False,
    current_user: User = Depends(require_admin)
):
    """
    Uninstall a module

    Admin only. Removes module files and optionally keeps data.
    """
    project_root = Path(__file__).parent.parent.parent.parent
    modules_dir = project_root / 'modules'
    module_dir = modules_dir / module_code

    # Check if exists
    if not module_dir.exists():
        raise HTTPException(status_code=404, detail=f"Module '{module_code}' not found")

    # Check if it's a core module
    manifest_path = module_dir / 'manifest.json'
    if manifest_path.exists():
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        if manifest.get('category') == 'core':
            raise HTTPException(status_code=403, detail="Cannot uninstall core modules")

    try:
        # Remove module directory
        shutil.rmtree(module_dir)

        # Rebuild registry
        subprocess.run(
            [sys.executable, 'scripts/build_module_registry.py'],
            cwd=str(project_root),
            check=True,
            capture_output=True
        )

        subprocess.run(
            [sys.executable, 'scripts/build_frontend_imports.py'],
            cwd=str(project_root),
            check=True,
            capture_output=True
        )

        return {
            "success": True,
            "message": f"Module '{module_code}' uninstalled successfully"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Uninstallation failed: {str(e)}"
        )


@router.get("/install/{installation_id}", response_model=InstallationProgress)
async def get_installation_progress(
    installation_id: str,
    current_user: User = Depends(require_admin)
):
    """
    Get installation progress

    Returns the current status of an ongoing installation.
    """
    # TODO: Implement progress tracking
    # For now, return mock data
    return InstallationProgress(
        installation_id=installation_id,
        module_code="unknown",
        version="1.0.0",
        status="pending",
        progress=0,
        current_step="Initializing",
        current_step_index=0,
        logs=[]
    )
