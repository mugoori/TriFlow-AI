"""
Judgment API Router
판단 실행 및 Replay API
"""
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.auth.dependencies import get_current_user
from app.services.judgment_replay_service import get_judgment_replay_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ========== Request/Response Schemas ==========


class JudgmentExecuteRequest(BaseModel):
    """Judgment 실행 요청"""
    ruleset_id: str = Field(..., description="Ruleset ID (UUID)")
    input_data: dict = Field(..., description="입력 데이터 (센서 값 등)")
    policy: str = Field("hybrid_weighted", description="판단 정책 (rule_only, llm_only, hybrid_weighted, hybrid_gate 등)")
    need_explanation: bool = Field(True, description="설명 생성 여부")
    context: Optional[dict] = Field(None, description="추가 컨텍스트")


class JudgmentExecuteResponse(BaseModel):
    """Judgment 실행 응답"""
    execution_id: str
    decision: str
    confidence: float
    source: str
    policy_used: str
    execution_time_ms: int
    cached: bool
    explanation: Optional[dict] = None
    evidence: Optional[List[str]] = None
    recommended_actions: Optional[List[dict]] = None
    rule_result: Optional[dict] = None
    llm_result: Optional[dict] = None
    details: dict = {}
    timestamp: str


class ReplayRequest(BaseModel):
    """Replay 요청"""
    use_current_ruleset: bool = Field(True, description="현재 활성 Ruleset 사용 여부")
    ruleset_version: Optional[int] = Field(None, description="특정 룰셋 버전 지정")


class BatchReplayRequest(BaseModel):
    """일괄 Replay 요청"""
    execution_ids: List[str] = Field(..., min_length=1, max_length=100, description="Execution ID 목록")
    use_current_ruleset: bool = Field(True, description="현재 활성 Ruleset 사용 여부")


class WhatIfRequest(BaseModel):
    """What-If 분석 요청"""
    input_modifications: dict = Field(..., description="변경할 입력 값")


# ========== API Endpoints ==========


@router.post("/execute", response_model=JudgmentExecuteResponse)
async def execute_judgment(
    request: JudgmentExecuteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Judgment 실행 (독립 API)

    스펙 참조: A-2 JUD-FR-010~050

    Rule + LLM 하이브리드 판단을 수행하여 결과를 반환합니다.

    Args:
        ruleset_id: 실행할 Ruleset ID
        input_data: 입력 데이터 (센서 값, 생산 데이터 등)
        policy: 판단 정책 (rule_only, llm_only, hybrid_weighted, hybrid_gate 등)
        need_explanation: True면 설명/증거/추천조치 생성
        context: 추가 컨텍스트 (라인 코드, 날짜 등)

    Returns:
        {
            "execution_id": "...",
            "decision": "OK|WARNING|CRITICAL",
            "confidence": 0.92,
            "source": "rule|llm|hybrid",
            "policy_used": "hybrid_weighted",
            "execution_time_ms": 1250,
            "cached": false,
            "explanation": {...},
            "evidence": [...],
            "recommended_actions": [...]
        }
    """
    from app.services.judgment_policy import get_hybrid_judgment_service, JudgmentPolicy
    from app.models.core import JudgmentExecution, Ruleset
    from uuid import UUID as PythonUUID

    # UUID 변환
    try:
        ruleset_uuid = PythonUUID(request.ruleset_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ruleset_id format")

    # Ruleset 존재 여부 확인
    ruleset = db.query(Ruleset).filter(
        Ruleset.ruleset_id == ruleset_uuid,
        Ruleset.tenant_id == current_user.tenant_id
    ).first()

    if not ruleset:
        raise HTTPException(status_code=404, detail="Ruleset not found")

    if not ruleset.is_active:
        raise HTTPException(status_code=400, detail="Ruleset is not active")

    # 정책 변환
    try:
        policy_enum = JudgmentPolicy(request.policy)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid policy. Allowed: {', '.join([p.value for p in JudgmentPolicy])}"
        )

    # Judgment 실행
    try:
        hybrid_service = get_hybrid_judgment_service()
        result = await hybrid_service.execute(
            tenant_id=current_user.tenant_id,
            ruleset_id=ruleset_uuid,
            input_data=request.input_data,
            policy=policy_enum,
            context=request.context or {},
        )

        # DB에 실행 기록 저장
        execution = JudgmentExecution(
            tenant_id=current_user.tenant_id,
            ruleset_id=ruleset_uuid,
            source="api",
            input_data=request.input_data,
            result=result.decision,
            confidence=result.confidence,
            method_used=result.source,
            explanation=result.explanation,
            evidence=result.evidence,
            cache_hit=result.cached,
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)

        logger.info(
            f"Judgment executed: execution_id={execution.execution_id}, "
            f"decision={result.decision}, confidence={result.confidence:.3f}, "
            f"policy={policy_enum.value}, cached={result.cached}"
        )

        # 응답 구성
        return JudgmentExecuteResponse(
            execution_id=str(execution.execution_id),
            decision=result.decision,
            confidence=result.confidence,
            source=result.source,
            policy_used=policy_enum.value,
            execution_time_ms=result.execution_time_ms,
            cached=result.cached,
            explanation=result.explanation if request.need_explanation else None,
            evidence=result.evidence if request.need_explanation else None,
            recommended_actions=result.details.get("recommended_actions") if request.need_explanation else None,
            rule_result=result.rule_result if request.need_explanation else None,
            llm_result=result.llm_result if request.need_explanation else None,
            details=result.details,
            timestamp=result.timestamp,
        )

    except Exception as e:
        logger.error(f"Judgment execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Judgment execution failed: {str(e)}")


@router.post("/replay/{execution_id}")
async def replay_judgment_execution(
    execution_id: UUID,
    request: ReplayRequest = ReplayRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Judgment Execution 재실행

    과거 execution_id의 입력 데이터로 현재 Ruleset을 재실행하여
    결과를 비교합니다.

    사용 사례:
    - Rule 버전 업그레이드 후 영향 분석
    - Rule 변경 사항 검증
    - A/B 테스트

    Args:
        execution_id: 재실행할 Execution ID
        use_current_ruleset: True면 현재 활성 Ruleset 사용
        ruleset_version: 특정 버전 지정 (선택)

    Returns:
        {
            "original": {...},  # 원본 실행 결과
            "replay": {...},    # 재실행 결과
            "comparison": {...} # 비교 결과
        }
    """
    replay_service = get_judgment_replay_service(db)

    try:
        result = await replay_service.replay_execution(
            execution_id=execution_id,
            use_current_ruleset=request.use_current_ruleset,
            ruleset_version=request.ruleset_version,
        )

        logger.info(
            f"Replayed execution {execution_id}: "
            f"result_changed={result['comparison']['result_changed']}"
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to replay execution: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Replay failed")


@router.post("/replay/batch")
async def replay_judgment_batch(
    request: BatchReplayRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    여러 Judgment Execution 일괄 재실행

    Rule 변경 후 영향 받는 execution들을 일괄로 재실행하여
    변경률을 분석합니다.

    사용 사례:
    - Rule v1 → v2 업그레이드 영향 분석
    - 최근 100개 execution 재실행
    - "몇 %가 결과가 바뀌었는지" 통계

    Args:
        execution_ids: Execution ID 목록 (최대 100개)
        use_current_ruleset: 현재 활성 Ruleset 사용 여부

    Returns:
        {
            "total": 100,
            "changed": 15,  # 15개 변경됨
            "change_rate": 15.0,  # 15% 변경
            "results": [...],
            "summary": {...}
        }
    """
    replay_service = get_judgment_replay_service(db)

    # UUID 변환
    execution_ids = [UUID(id_str) for id_str in request.execution_ids]

    try:
        result = await replay_service.replay_batch(
            execution_ids=execution_ids,
            use_current_ruleset=request.use_current_ruleset,
        )

        logger.info(
            f"Batch replay completed: {result['total']} executions, "
            f"{result['changed']} changed ({result['change_rate']}%)"
        )

        return result

    except Exception as e:
        logger.error(f"Failed to replay batch: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Batch replay failed")


@router.post("/what-if/{execution_id}")
async def what_if_judgment_analysis(
    execution_id: UUID,
    request: WhatIfRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    What-If 분석

    특정 execution의 입력 값을 변경하여 결과가 어떻게 바뀌는지 분석합니다.

    사용 사례:
    - "온도가 85도였다면?"
    - "압력이 120이었다면?"
    - "불량률이 5%였다면?"

    Args:
        execution_id: 기준 Execution ID
        input_modifications: 변경할 입력 값

    Returns:
        원본 vs 변경 후 결과 비교

    Example:
        POST /api/v2/judgment/what-if/{execution_id}
        {
            "input_modifications": {
                "temperature": 85,
                "pressure": 120
            }
        }

        Response:
        {
            "original_result": "normal",
            "what_if_result": "warning",  # 변경됨!
            "impact": {
                "result_changed": true,
                "confidence_change": -0.15
            }
        }
    """
    replay_service = get_judgment_replay_service(db)

    try:
        result = await replay_service.what_if_analysis(
            execution_id=execution_id,
            input_modifications=request.input_modifications,
        )

        logger.info(
            f"What-if analysis for {execution_id}: "
            f"result_changed={result['impact']['result_changed']}"
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed what-if analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="What-if analysis failed")


@router.get("/executions/recent")
async def get_recent_executions(
    limit: int = Query(100, ge=1, le=500, description="조회 개수"),
    ruleset_id: Optional[UUID] = Query(None, description="룰셋 ID 필터"),
    result: Optional[str] = Query(None, description="결과 필터 (normal, warning, critical)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    최근 Judgment Execution 목록 조회 (Replay용)

    Replay할 execution을 선택하기 위한 최근 실행 이력 조회

    Args:
        limit: 조회 개수
        ruleset_id: 특정 Ruleset만 필터링
        result: 특정 결과만 필터링

    Returns:
        Execution 목록
    """
    from app.models import JudgmentExecution

    query = db.query(JudgmentExecution).filter(
        JudgmentExecution.tenant_id == current_user.tenant_id
    )

    if ruleset_id:
        query = query.filter(JudgmentExecution.ruleset_id == ruleset_id)

    if result:
        query = query.filter(JudgmentExecution.result == result)

    executions = query.order_by(
        JudgmentExecution.created_at.desc()
    ).limit(limit).all()

    return {
        "executions": [
            {
                "execution_id": str(e.execution_id),
                "ruleset_id": str(e.ruleset_id) if e.ruleset_id else None,
                "result": e.result,
                "confidence": e.confidence,
                "method_used": e.method_used,
                "executed_at": e.created_at.isoformat() if e.created_at else None,
                "input_summary": str(e.input_data)[:100] + "..." if e.input_data else None,
            }
            for e in executions
        ],
        "total": len(executions),
    }


logger.info("Judgment router initialized")
