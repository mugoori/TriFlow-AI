"""
Ruleset Router
룰셋 CRUD 및 실행 API - PostgreSQL DB 연동
Rhai 스크립트 기반 규칙 관리
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Query, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Ruleset, Tenant

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


# ============ API Endpoints ============

@router.get("", response_model=RulesetListResponse)
async def list_rulesets(
    db: Session = Depends(get_db),
    is_active: Optional[bool] = Query(None, description="활성 상태 필터"),
    search: Optional[str] = Query(None, description="이름/설명 검색"),
):
    """
    룰셋 목록 조회
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
):
    """
    룰셋 상세 조회
    """
    try:
        rs_uuid = UUID(ruleset_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ruleset ID format")

    ruleset = db.query(Ruleset).filter(Ruleset.ruleset_id == rs_uuid).first()

    if not ruleset:
        raise HTTPException(status_code=404, detail="Ruleset not found")

    return _ruleset_to_response(ruleset)


@router.post("", response_model=RulesetResponse, status_code=201)
async def create_ruleset(
    ruleset: RulesetCreate,
    db: Session = Depends(get_db),
):
    """
    새 룰셋 생성
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
):
    """
    룰셋 수정
    """
    try:
        rs_uuid = UUID(ruleset_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ruleset ID format")

    ruleset = db.query(Ruleset).filter(Ruleset.ruleset_id == rs_uuid).first()

    if not ruleset:
        raise HTTPException(status_code=404, detail="Ruleset not found")

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
):
    """
    룰셋 삭제
    """
    try:
        rs_uuid = UUID(ruleset_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ruleset ID format")

    ruleset = db.query(Ruleset).filter(Ruleset.ruleset_id == rs_uuid).first()

    if not ruleset:
        raise HTTPException(status_code=404, detail="Ruleset not found")

    db.delete(ruleset)
    db.commit()

    return None


@router.post("/{ruleset_id}/execute", response_model=RulesetExecuteResponse)
async def execute_ruleset(
    ruleset_id: str,
    request: RulesetExecuteRequest,
    db: Session = Depends(get_db),
):
    """
    룰셋 실행 (MVP: Mock 실행 - 실제 Rhai 엔진 연동 전)

    입력 데이터를 받아 룰셋을 실행하고 결과를 반환합니다.
    MVP 단계에서는 실행 이력을 DB에 저장하지 않습니다.
    """
    try:
        rs_uuid = UUID(ruleset_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ruleset ID format")

    ruleset = db.query(Ruleset).filter(Ruleset.ruleset_id == rs_uuid).first()

    if not ruleset:
        raise HTTPException(status_code=404, detail="Ruleset not found")

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

    ruleset = db.query(Ruleset).filter(Ruleset.ruleset_id == rs_uuid).first()

    if not ruleset:
        raise HTTPException(status_code=404, detail="Ruleset not found")

    # MVP: 실행 이력 DB 저장이 구현되지 않아 빈 배열 반환
    return ExecutionHistoryResponse(
        executions=[],
        total=0,
    )
