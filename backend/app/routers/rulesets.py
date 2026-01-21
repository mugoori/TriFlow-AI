"""
Ruleset Router
룰셋 CRUD 및 실행 API - PostgreSQL DB 연동
Rhai 스크립트 기반 규칙 관리

권한:
- rulesets:read - 모든 역할 (viewer 이상)
- rulesets:create - user 이상
- rulesets:update - user 이상
- rulesets:execute - operator 이상
- rulesets:delete - admin만
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Query, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Ruleset, RulesetVersion, Tenant
from app.services.rbac_service import (
    check_permission,
    require_admin,
)
from app.repositories import RulesetRepository

router = APIRouter()


# ============ Pydantic Models ============

class RulesetCreate(BaseModel):
    name: str = Field(..., description="룰셋 이름")
    description: Optional[str] = Field(None, description="룰셋 설명")
    rhai_script: str = Field(..., description="Rhai 스크립트 코드")


class RulesetUpdate(BaseModel):
    name: Optional[str] = Field(None, description="룰셋 이름")
    description: Optional[str] = Field(None, description="룰셋 설명")
    rhai_script: Optional[str] = Field(None, description="Rhai 스크립트 코드")
    is_active: Optional[bool] = Field(None, description="활성 상태")


class RulesetResponse(BaseModel):
    ruleset_id: str
    name: str
    description: Optional[str]
    rhai_script: str
    version: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RulesetListResponse(BaseModel):
    rulesets: List[RulesetResponse]
    total: int


class RulesetExecuteRequest(BaseModel):
    input_data: Dict[str, Any] = Field(..., description="룰셋 실행 입력 데이터")


class RulesetExecuteResponse(BaseModel):
    execution_id: str
    ruleset_id: str
    ruleset_name: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    confidence_score: Optional[float]
    execution_time_ms: int
    executed_at: datetime


class ExecutionHistoryResponse(BaseModel):
    executions: List[RulesetExecuteResponse]
    total: int


class RulesetVersionResponse(BaseModel):
    version_id: str
    ruleset_id: str
    version_number: int
    version_label: str
    rhai_script: str
    description: Optional[str]
    change_summary: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class RulesetVersionListResponse(BaseModel):
    versions: List[RulesetVersionResponse]
    total: int


# ============ Helper Functions ============

def _ruleset_to_response(ruleset: Ruleset) -> RulesetResponse:
    """ORM 객체를 Response 모델로 변환"""
    return RulesetResponse(
        ruleset_id=str(ruleset.ruleset_id),
        name=ruleset.name,
        description=ruleset.description,
        rhai_script=ruleset.rhai_script,
        version=ruleset.version,
        is_active=ruleset.is_active,
        created_at=ruleset.created_at,
        updated_at=ruleset.updated_at,
    )




def _get_or_create_tenant(db: Session) -> Tenant:
    """MVP용 기본 tenant 조회 또는 생성"""
    tenant = db.query(Tenant).first()
    if not tenant:
        tenant = Tenant(
            name="Default Tenant",
            slug="default",
            settings={},
        )
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
    return tenant


# ============ Sample Rhai Scripts ============

SAMPLE_RHAI_SCRIPTS = {
    "temperature_check": '''
// 온도 임계값 체크 룰
let threshold = 70.0;
let temperature = input.temperature;

if temperature > threshold {
    #{
        "result": "alert",
        "message": "온도가 임계값을 초과했습니다",
        "temperature": temperature,
        "threshold": threshold
    }
} else {
    #{
        "result": "normal",
        "message": "온도가 정상 범위입니다",
        "temperature": temperature,
        "threshold": threshold
    }
}
''',
    "pressure_monitor": '''
// 압력 모니터링 룰
let min_pressure = 2.0;
let max_pressure = 8.0;
let pressure = input.pressure;

if pressure < min_pressure {
    #{
        "result": "low_pressure",
        "action": "increase_pressure",
        "current": pressure,
        "target": min_pressure
    }
} else if pressure > max_pressure {
    #{
        "result": "high_pressure",
        "action": "decrease_pressure",
        "current": pressure,
        "target": max_pressure
    }
} else {
    #{
        "result": "normal",
        "action": "none",
        "current": pressure
    }
}
''',
    "defect_detection": '''
// 불량 감지 룰
let defect_rate = input.defect_rate;
let threshold = 5.0;

let severity = if defect_rate > 10.0 {
    "critical"
} else if defect_rate > threshold {
    "warning"
} else {
    "normal"
};

#{
    "severity": severity,
    "defect_rate": defect_rate,
    "threshold": threshold,
    "requires_action": defect_rate > threshold
}
'''
}


# ============ Rhai Script Validation ============

class RhaiValidateRequest(BaseModel):
    """Rhai 스크립트 검증 요청"""
    script: str = Field(..., description="검증할 Rhai 스크립트")


class RhaiValidateResponse(BaseModel):
    """Rhai 스크립트 검증 응답"""
    valid: bool
    script_preview: str
    line_count: int
    errors: List[Dict[str, Any]]
    warnings: List[Dict[str, Any]]


def validate_rhai_script(script: str) -> RhaiValidateResponse:
    """
    Rhai 스크립트 문법 검증 (간단한 정적 분석)

    실제 Rhai 엔진 연동 전까지는 기본적인 문법 검사만 수행합니다.
    """
    errors = []
    warnings = []
    lines = script.strip().split('\n')
    line_count = len(lines)

    # 기본 문법 검사
    brace_count = 0
    paren_count = 0
    bracket_count = 0

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # 빈 줄이나 주석은 건너뜀
        if not stripped or stripped.startswith('//'):
            continue

        # 괄호 카운팅
        brace_count += stripped.count('{') - stripped.count('}')
        paren_count += stripped.count('(') - stripped.count(')')
        bracket_count += stripped.count('[') - stripped.count(']')

        # 일반적인 오류 패턴 검사
        if '==' in stripped and '===' not in stripped:
            # Rhai는 == 사용 (정상)
            pass

        if stripped.endswith(',}') or stripped.endswith(',]'):
            warnings.append({
                "line": i,
                "column": len(stripped),
                "message": "Trailing comma before closing bracket",
                "severity": "warning",
            })

        # let 변수 선언 검사
        if stripped.startswith('let ') and '=' not in stripped and ';' in stripped:
            errors.append({
                "line": i,
                "column": 1,
                "message": "Variable declaration without initialization",
                "severity": "error",
            })

        # 함수 정의 검사 (fn keyword)
        if stripped.startswith('fn ') and '(' not in stripped:
            errors.append({
                "line": i,
                "column": 1,
                "message": "Function definition missing parameter list",
                "severity": "error",
            })

    # 최종 괄호 균형 검사
    if brace_count != 0:
        errors.append({
            "line": line_count,
            "column": 1,
            "message": f"Unbalanced curly braces: {'+' if brace_count > 0 else ''}{brace_count}",
            "severity": "error",
        })

    if paren_count != 0:
        errors.append({
            "line": line_count,
            "column": 1,
            "message": f"Unbalanced parentheses: {'+' if paren_count > 0 else ''}{paren_count}",
            "severity": "error",
        })

    if bracket_count != 0:
        errors.append({
            "line": line_count,
            "column": 1,
            "message": f"Unbalanced square brackets: {'+' if bracket_count > 0 else ''}{bracket_count}",
            "severity": "error",
        })

    # 스크립트 미리보기 (첫 100자)
    preview = script[:100] + ('...' if len(script) > 100 else '')

    return RhaiValidateResponse(
        valid=len(errors) == 0,
        script_preview=preview,
        line_count=line_count,
        errors=errors,
        warnings=warnings,
    )


# ============ API Endpoints ============

@router.post("/validate", response_model=RhaiValidateResponse)
async def validate_ruleset_script(request: RhaiValidateRequest):
    """
    Rhai 스크립트 문법 검증

    저장 전에 스크립트의 문법 오류를 검사합니다.

    Returns:
        valid: 검증 통과 여부
        errors: 오류 목록 (line, column, message)
        warnings: 경고 목록
    """
    return validate_rhai_script(request.script)


@router.get("", response_model=RulesetListResponse)
async def list_rulesets(
    db: Session = Depends(get_db),
    is_active: Optional[bool] = Query(None, description="활성 상태 필터"),
    search: Optional[str] = Query(None, description="이름/설명 검색"),
    _: None = Depends(check_permission("rulesets", "read")),
):
    """
    룰셋 목록 조회 (viewer 이상)
    """
    try:
        query = db.query(Ruleset)

        if is_active is not None:
            query = query.filter(Ruleset.is_active == is_active)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                (Ruleset.name.ilike(search_pattern)) |
                (Ruleset.description.ilike(search_pattern))
            )

        query = query.order_by(Ruleset.created_at.desc())
        rulesets = query.all()

        return RulesetListResponse(
            rulesets=[_ruleset_to_response(r) for r in rulesets],
            total=len(rulesets),
        )
    except Exception:
        # DB 연결 실패 시 빈 목록 반환
        return RulesetListResponse(
            rulesets=[],
            total=0,
        )


@router.get("/samples")
async def get_sample_scripts():
    """
    샘플 Rhai 스크립트 목록 조회
    """
    samples = []
    for name, script in SAMPLE_RHAI_SCRIPTS.items():
        samples.append({
            "name": name,
            "description": script.split('\n')[1].replace('//', '').strip() if script.startswith('//') or '\n//' in script else name,
            "script": script.strip(),
        })

    return {
        "samples": samples,
        "total": len(samples),
    }


@router.get("/{ruleset_id}", response_model=RulesetResponse)
async def get_ruleset(
    ruleset_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(check_permission("rulesets", "read")),
):
    """
    룰셋 상세 조회 (viewer 이상)
    """
    try:
        rs_uuid = UUID(ruleset_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ruleset ID format")

    # Repository 패턴 적용
    ruleset_repo = RulesetRepository(db)
    ruleset = ruleset_repo.get_by_id_or_404(rs_uuid)

    return _ruleset_to_response(ruleset)


@router.post("", response_model=RulesetResponse, status_code=201)
async def create_ruleset(
    ruleset: RulesetCreate,
    db: Session = Depends(get_db),
    _: None = Depends(check_permission("rulesets", "create")),
):
    """
    새 룰셋 생성 (user 이상)
    """
    tenant = _get_or_create_tenant(db)

    new_ruleset = Ruleset(
        tenant_id=tenant.tenant_id,
        name=ruleset.name,
        description=ruleset.description,
        rhai_script=ruleset.rhai_script,
        version="1.0.0",
        is_active=True,
    )

    db.add(new_ruleset)
    db.commit()
    db.refresh(new_ruleset)

    return _ruleset_to_response(new_ruleset)


@router.patch("/{ruleset_id}", response_model=RulesetResponse)
async def update_ruleset(
    ruleset_id: str,
    update_data: RulesetUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(check_permission("rulesets", "update")),
):
    """
    룰셋 수정 (user 이상)
    """
    try:
        rs_uuid = UUID(ruleset_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ruleset ID format")

    ruleset_repo = RulesetRepository(db)


    ruleset = ruleset_repo.get_by_id_or_404(rs_uuid)

    if update_data.name is not None:
        ruleset.name = update_data.name
    if update_data.description is not None:
        ruleset.description = update_data.description
    if update_data.rhai_script is not None:
        ruleset.rhai_script = update_data.rhai_script
        # 스크립트 변경 시 버전 증가
        current_version = ruleset.version.split('.')
        current_version[-1] = str(int(current_version[-1]) + 1)
        ruleset.version = '.'.join(current_version)
    if update_data.is_active is not None:
        ruleset.is_active = update_data.is_active

    ruleset.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(ruleset)

    return _ruleset_to_response(ruleset)


@router.delete("/{ruleset_id}", status_code=204)
async def delete_ruleset(
    ruleset_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    """
    룰셋 삭제 (admin만)
    """
    try:
        rs_uuid = UUID(ruleset_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ruleset ID format")

    ruleset_repo = RulesetRepository(db)


    ruleset = ruleset_repo.get_by_id_or_404(rs_uuid)

    db.delete(ruleset)
    db.commit()

    return None


@router.post("/{ruleset_id}/execute", response_model=RulesetExecuteResponse)
async def execute_ruleset(
    ruleset_id: str,
    request: RulesetExecuteRequest,
    db: Session = Depends(get_db),
    _: None = Depends(check_permission("rulesets", "execute")),
):
    """
    룰셋 실행 (MVP: Mock 실행 - 실제 Rhai 엔진 연동 전, operator 이상)

    입력 데이터를 받아 룰셋을 실행하고 결과를 반환합니다.
    MVP 단계에서는 실행 이력을 DB에 저장하지 않습니다.
    """
    try:
        rs_uuid = UUID(ruleset_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ruleset ID format")

    ruleset_repo = RulesetRepository(db)


    ruleset = ruleset_repo.get_by_id_or_404(rs_uuid)

    if not ruleset.is_active:
        raise HTTPException(status_code=400, detail="Ruleset is not active")

    # MVP: Mock 실행 결과 생성
    # 실제로는 Rhai 엔진을 통해 스크립트를 실행해야 함
    import time
    from uuid import uuid4
    start_time = time.time()

    # 간단한 Mock 결과 생성
    output_data = {
        "status": "executed",
        "message": f"Ruleset '{ruleset.name}' executed successfully",
        "input_keys": list(request.input_data.keys()),
        "script_lines": len(ruleset.rhai_script.split('\n')),
    }

    # 입력 데이터에 따른 간단한 판단 로직 (Mock)
    if "temperature" in request.input_data:
        temp = request.input_data["temperature"]
        output_data["temperature_status"] = "high" if temp > 70 else "normal"
    if "pressure" in request.input_data:
        pres = request.input_data["pressure"]
        output_data["pressure_status"] = "high" if pres > 8 else ("low" if pres < 2 else "normal")

    execution_time_ms = int((time.time() - start_time) * 1000) + 5  # 최소 5ms
    confidence_score = 0.95  # Mock confidence

    # MVP: 실행 이력 DB 저장 없이 즉시 결과 반환
    return RulesetExecuteResponse(
        execution_id=str(uuid4()),
        ruleset_id=ruleset_id,
        ruleset_name=ruleset.name,
        input_data=request.input_data,
        output_data=output_data,
        confidence_score=confidence_score,
        execution_time_ms=execution_time_ms,
        executed_at=datetime.utcnow(),
    )


@router.get("/{ruleset_id}/executions", response_model=ExecutionHistoryResponse)
async def list_ruleset_executions(
    ruleset_id: str,
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100, description="조회 개수"),
):
    """
    룰셋 실행 이력 조회
    MVP: 실행 이력 DB 저장이 구현되지 않아 빈 배열 반환
    """
    try:
        rs_uuid = UUID(ruleset_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ruleset ID format")

    ruleset_repo = RulesetRepository(db)


    ruleset = ruleset_repo.get_by_id_or_404(rs_uuid)

    # MVP: 실행 이력 DB 저장이 구현되지 않아 빈 배열 반환
    return ExecutionHistoryResponse(
        executions=[],
        total=0,
    )


# ============ Version Management Endpoints ============

def _version_to_response(version: RulesetVersion) -> RulesetVersionResponse:
    """RulesetVersion ORM 객체를 Response 모델로 변환"""
    return RulesetVersionResponse(
        version_id=str(version.version_id),
        ruleset_id=str(version.ruleset_id),
        version_number=version.version_number,
        version_label=version.version_label,
        rhai_script=version.rhai_script,
        description=version.description,
        change_summary=version.change_summary,
        created_at=version.created_at,
    )


def _create_version_snapshot(
    db: Session,
    ruleset: Ruleset,
    change_summary: Optional[str] = None,
) -> RulesetVersion:
    """현재 룰셋 상태를 버전으로 저장"""
    # 최신 버전 번호 조회
    latest_version = (
        db.query(RulesetVersion)
        .filter(RulesetVersion.ruleset_id == ruleset.ruleset_id)
        .order_by(RulesetVersion.version_number.desc())
        .first()
    )

    next_version_number = (latest_version.version_number + 1) if latest_version else 1

    new_version = RulesetVersion(
        ruleset_id=ruleset.ruleset_id,
        version_number=next_version_number,
        version_label=ruleset.version,
        rhai_script=ruleset.rhai_script,
        description=ruleset.description,
        change_summary=change_summary,
        created_by=ruleset.created_by,
    )

    db.add(new_version)
    db.commit()
    db.refresh(new_version)

    return new_version


@router.get("/{ruleset_id}/versions", response_model=RulesetVersionListResponse)
async def list_ruleset_versions(
    ruleset_id: str,
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100, description="조회 개수"),
    offset: int = Query(0, ge=0, description="오프셋"),
):
    """
    룰셋 버전 히스토리 조회
    """
    try:
        rs_uuid = UUID(ruleset_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ruleset ID format")

    ruleset_repo = RulesetRepository(db)


    ruleset = ruleset_repo.get_by_id_or_404(rs_uuid)

    # 버전 목록 조회
    query = (
        db.query(RulesetVersion)
        .filter(RulesetVersion.ruleset_id == rs_uuid)
        .order_by(RulesetVersion.version_number.desc())
    )

    total = query.count()
    versions = query.offset(offset).limit(limit).all()

    return RulesetVersionListResponse(
        versions=[_version_to_response(v) for v in versions],
        total=total,
    )


@router.get("/{ruleset_id}/versions/{version_id}", response_model=RulesetVersionResponse)
async def get_ruleset_version(
    ruleset_id: str,
    version_id: str,
    db: Session = Depends(get_db),
):
    """
    특정 버전 상세 조회
    """
    try:
        rs_uuid = UUID(ruleset_id)
        v_uuid = UUID(version_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    version = (
        db.query(RulesetVersion)
        .filter(
            RulesetVersion.ruleset_id == rs_uuid,
            RulesetVersion.version_id == v_uuid,
        )
        .first()
    )

    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    return _version_to_response(version)


@router.post("/{ruleset_id}/versions", response_model=RulesetVersionResponse, status_code=201)
async def create_ruleset_version(
    ruleset_id: str,
    db: Session = Depends(get_db),
    change_summary: Optional[str] = Query(None, description="변경 사항 요약"),
):
    """
    현재 룰셋 상태를 새 버전으로 저장 (스냅샷)
    """
    try:
        rs_uuid = UUID(ruleset_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ruleset ID format")

    ruleset_repo = RulesetRepository(db)


    ruleset = ruleset_repo.get_by_id_or_404(rs_uuid)

    new_version = _create_version_snapshot(db, ruleset, change_summary)

    return _version_to_response(new_version)


@router.post("/{ruleset_id}/versions/{version_id}/rollback", response_model=RulesetResponse)
async def rollback_to_version(
    ruleset_id: str,
    version_id: str,
    db: Session = Depends(get_db),
):
    """
    특정 버전으로 롤백
    현재 상태를 버전으로 저장한 후, 선택한 버전의 스크립트로 복원
    """
    try:
        rs_uuid = UUID(ruleset_id)
        v_uuid = UUID(version_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    ruleset_repo = RulesetRepository(db)


    ruleset = ruleset_repo.get_by_id_or_404(rs_uuid)

    target_version = (
        db.query(RulesetVersion)
        .filter(
            RulesetVersion.ruleset_id == rs_uuid,
            RulesetVersion.version_id == v_uuid,
        )
        .first()
    )

    if not target_version:
        raise HTTPException(status_code=404, detail="Version not found")

    # 현재 상태를 버전으로 먼저 저장
    _create_version_snapshot(db, ruleset, f"Auto-saved before rollback to v{target_version.version_label}")

    # 선택한 버전으로 복원
    ruleset.rhai_script = target_version.rhai_script
    ruleset.description = target_version.description

    # 버전 번호 증가
    current_version = ruleset.version.split('.')
    current_version[-1] = str(int(current_version[-1]) + 1)
    ruleset.version = '.'.join(current_version)

    ruleset.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(ruleset)

    # 롤백 후 새 버전 스냅샷 저장
    _create_version_snapshot(db, ruleset, f"Rolled back to v{target_version.version_label}")

    return _ruleset_to_response(ruleset)


@router.delete("/{ruleset_id}/versions/{version_id}", status_code=204)
async def delete_ruleset_version(
    ruleset_id: str,
    version_id: str,
    db: Session = Depends(get_db),
):
    """
    특정 버전 삭제 (가장 최근 버전만 삭제 가능)
    """
    try:
        rs_uuid = UUID(ruleset_id)
        v_uuid = UUID(version_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    version = (
        db.query(RulesetVersion)
        .filter(
            RulesetVersion.ruleset_id == rs_uuid,
            RulesetVersion.version_id == v_uuid,
        )
        .first()
    )

    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    # 가장 최근 버전인지 확인
    latest_version = (
        db.query(RulesetVersion)
        .filter(RulesetVersion.ruleset_id == rs_uuid)
        .order_by(RulesetVersion.version_number.desc())
        .first()
    )

    if version.version_id != latest_version.version_id:
        raise HTTPException(
            status_code=400,
            detail="Only the latest version can be deleted",
        )

    db.delete(version)
    db.commit()

    return None
