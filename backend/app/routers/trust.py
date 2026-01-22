# -*- coding: utf-8 -*-
"""
Trust Router - V2.0 Progressive Trust Model API

B-4 스펙 섹션 12: Trust API 엔드포인트
- GET  /api/v2/trust/rules/{rule_id}          - Trust 정보 조회
- POST /api/v2/trust/rules/{rule_id}/calculate - Trust Score 재계산
- PATCH /api/v2/trust/rules/{rule_id}/level    - Trust Level 수동 변경
- GET  /api/v2/trust/rules/{rule_id}/history   - 변경 이력 조회
- POST /api/v2/trust/evaluate/batch            - 일괄 평가
"""
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.trust_service import TrustService, TrustLevel
from app.auth.dependencies import require_admin
from app.services.audit_service import create_audit_log
from app.models import User

logger = logging.getLogger(__name__)

router = APIRouter()


# ============ Pydantic Models ============

class TrustLevelUpdate(BaseModel):
    """Trust Level 수동 변경 요청"""
    new_level: int = Field(..., ge=0, le=3, description="새 Trust Level (0-3)")
    reason: str = Field(..., min_length=5, max_length=500, description="변경 사유")


class TrustScoreComponents(BaseModel):
    """Trust Score 컴포넌트"""
    accuracy: float = Field(..., ge=0, le=1, description="정확도 컴포넌트")
    consistency: float = Field(..., ge=0, le=1, description="일관성 컴포넌트")
    frequency: float = Field(..., ge=0, le=1, description="빈도 컴포넌트")
    feedback: float = Field(..., ge=0, le=1, description="피드백 컴포넌트")
    age: float = Field(..., ge=0, le=1, description="운영 기간 컴포넌트")


class TrustInfoResponse(BaseModel):
    """Trust 정보 응답"""
    ruleset_id: str
    name: str
    trust_level: int
    trust_level_name: str
    trust_score: float
    trust_score_components: Optional[Dict[str, float]] = None
    execution_count: int
    positive_feedback_count: int
    negative_feedback_count: int
    accuracy_rate: Optional[float] = None
    last_execution_at: Optional[str] = None
    last_promoted_at: Optional[str] = None
    last_demoted_at: Optional[str] = None
    created_at: str


class TrustHistoryItem(BaseModel):
    """Trust Level 변경 이력 항목"""
    id: str
    previous_level: int
    previous_level_name: str
    new_level: int
    new_level_name: str
    reason: Optional[str]
    triggered_by: Optional[str]
    metrics_snapshot: Optional[Dict[str, Any]]
    created_at: str
    created_by: Optional[str]


class TrustHistoryResponse(BaseModel):
    """Trust Level 변경 이력 응답"""
    ruleset_id: str
    history: List[TrustHistoryItem]


class TrustCalculateResponse(BaseModel):
    """Trust Score 계산 응답"""
    ruleset_id: str
    trust_score: float
    components: TrustScoreComponents


class TrustLevelChangeResponse(BaseModel):
    """Trust Level 변경 응답"""
    ruleset_id: str
    previous_level: int
    previous_level_name: str
    new_level: int
    new_level_name: str
    reason: str


class BatchEvaluateRequest(BaseModel):
    """일괄 평가 요청"""
    ruleset_ids: List[str] = Field(..., min_length=1, max_length=100, description="평가할 룰셋 ID 목록")


class BatchEvaluateResult(BaseModel):
    """일괄 평가 결과 항목"""
    ruleset_id: str
    action: Optional[str] = None  # promoted, demoted, or None
    previous_level: Optional[int] = None
    new_level: Optional[int] = None
    reason: Optional[str] = None
    error: Optional[str] = None


class BatchEvaluateResponse(BaseModel):
    """일괄 평가 응답"""
    results: List[BatchEvaluateResult]
    total: int
    changed: int


# ============ API Endpoints ============

@router.get(
    "/rules/{rule_id}",
    response_model=TrustInfoResponse,
    summary="Trust 정보 조회",
    description="룰셋의 Trust Level, Score, 메트릭 정보를 조회합니다.",
)
async def get_trust_info(
    rule_id: UUID,
    db: Session = Depends(get_db),
):
    """Trust 정보 조회

    Args:
        rule_id: 룰셋 ID

    Returns:
        TrustInfoResponse: Trust 정보
    """
    trust_service = TrustService(db)
    info = trust_service.get_trust_info(rule_id)

    if not info:
        raise HTTPException(status_code=404, detail=f"Ruleset {rule_id} not found")

    return TrustInfoResponse(**info)


@router.post(
    "/rules/{rule_id}/calculate",
    response_model=TrustCalculateResponse,
    summary="Trust Score 재계산",
    description="룰셋의 Trust Score를 재계산하고 저장합니다.",
)
async def calculate_trust_score(
    rule_id: UUID,
    db: Session = Depends(get_db),
):
    """Trust Score 재계산

    Args:
        rule_id: 룰셋 ID

    Returns:
        TrustCalculateResponse: 계산된 Trust Score와 컴포넌트
    """
    trust_service = TrustService(db)

    try:
        score, components = trust_service.calculate_trust_score(rule_id)

        # 저장
        trust_service.update_trust_score(rule_id)

        return TrustCalculateResponse(
            ruleset_id=str(rule_id),
            trust_score=float(score),
            components=TrustScoreComponents(
                accuracy=float(components["accuracy"]),
                consistency=float(components["consistency"]),
                frequency=float(components["frequency"]),
                feedback=float(components["feedback"]),
                age=float(components["age"]),
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch(
    "/rules/{rule_id}/level",
    response_model=TrustLevelChangeResponse,
    summary="Trust Level 수동 변경",
    description="룰셋의 Trust Level을 수동으로 변경합니다. 관리자 권한 필요.",
)
async def update_trust_level(
    rule_id: UUID,
    request: TrustLevelUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Trust Level 수동 변경

    Args:
        rule_id: 룰셋 ID
        request: 변경 요청 (새 레벨, 사유)
        current_user: 현재 관리자 사용자 (인증 필수)

    Returns:
        TrustLevelChangeResponse: 변경 결과

    Raises:
        HTTPException 403: 관리자 권한 없음
        HTTPException 404: 룰셋 없음
        HTTPException 400: 이미 해당 레벨
    """
    trust_service = TrustService(db)

    try:
        history = trust_service.update_trust_level(
            ruleset_id=rule_id,
            new_level=request.new_level,
            reason=request.reason,
            triggered_by="manual",
            user_id=current_user.user_id,
        )

        if history is None:
            raise HTTPException(
                status_code=400,
                detail=f"Trust level is already {request.new_level}"
            )

        # Audit Log 기록
        await create_audit_log(
            db=db,
            user_id=current_user.user_id,
            tenant_id=current_user.tenant_id,
            action="update_trust_level",
            resource="trust_ruleset",
            resource_id=str(rule_id),
            method="PATCH",
            path=f"/api/v2/trust/rules/{rule_id}/level",
            status_code=200,
            request_body={
                "new_level": request.new_level,
                "reason": request.reason,
            },
            response_summary=f"Trust level changed: {history.previous_level} -> {history.new_level}",
        )
        db.commit()

        return TrustLevelChangeResponse(
            ruleset_id=str(rule_id),
            previous_level=history.previous_level,
            previous_level_name=TrustService._level_to_name(history.previous_level),
            new_level=history.new_level,
            new_level_name=TrustService._level_to_name(history.new_level),
            reason=history.reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/rules/{rule_id}/history",
    response_model=TrustHistoryResponse,
    summary="Trust Level 변경 이력 조회",
    description="룰셋의 Trust Level 변경 이력을 조회합니다.",
)
async def get_trust_history(
    rule_id: UUID,
    limit: int = Query(20, ge=1, le=100, description="조회 개수"),
    db: Session = Depends(get_db),
):
    """Trust Level 변경 이력 조회

    Args:
        rule_id: 룰셋 ID
        limit: 조회 개수 (기본 20, 최대 100)

    Returns:
        TrustHistoryResponse: 변경 이력
    """
    trust_service = TrustService(db)
    history = trust_service.get_trust_history(rule_id, limit=limit)

    return TrustHistoryResponse(
        ruleset_id=str(rule_id),
        history=[TrustHistoryItem(**h) for h in history],
    )


@router.post(
    "/evaluate/batch",
    response_model=BatchEvaluateResponse,
    summary="일괄 Trust 평가",
    description="여러 룰셋의 Trust Score를 재계산하고 승격/강등 조건을 평가합니다.",
)
async def batch_evaluate(
    request: BatchEvaluateRequest,
    db: Session = Depends(get_db),
):
    """일괄 Trust 평가

    Args:
        request: 평가할 룰셋 ID 목록

    Returns:
        BatchEvaluateResponse: 평가 결과
    """
    trust_service = TrustService(db)
    results = []
    changed = 0

    for ruleset_id_str in request.ruleset_ids:
        try:
            ruleset_id = UUID(ruleset_id_str)
            result = trust_service.evaluate_and_update(ruleset_id)

            if result:
                results.append(BatchEvaluateResult(
                    ruleset_id=ruleset_id_str,
                    action=result["action"],
                    previous_level=result["previous_level"],
                    new_level=result["new_level"],
                    reason=result["reason"],
                ))
                changed += 1
            else:
                results.append(BatchEvaluateResult(
                    ruleset_id=ruleset_id_str,
                    action=None,
                ))
        except ValueError as e:
            results.append(BatchEvaluateResult(
                ruleset_id=ruleset_id_str,
                error=str(e),
            ))
        except Exception as e:
            logger.error(f"Error evaluating ruleset {ruleset_id_str}: {e}")
            results.append(BatchEvaluateResult(
                ruleset_id=ruleset_id_str,
                error=f"Evaluation failed: {str(e)}",
            ))

    return BatchEvaluateResponse(
        results=results,
        total=len(results),
        changed=changed,
    )


# ============ Additional Utility Endpoints ============

@router.get(
    "/levels",
    summary="Trust Level 목록 조회",
    description="사용 가능한 Trust Level 목록과 설명을 조회합니다.",
)
async def get_trust_levels():
    """Trust Level 목록 조회"""
    return {
        "levels": [
            {
                "level": TrustLevel.PROPOSED,
                "name": "Proposed",
                "description": "새로운 룰, 검증 필요. 자동 실행 없음.",
            },
            {
                "level": TrustLevel.ALERT_ONLY,
                "name": "Alert Only",
                "description": "알림만 발생, 자동 실행 없음.",
            },
            {
                "level": TrustLevel.LOW_RISK_AUTO,
                "name": "Low Risk Auto",
                "description": "저위험 작업만 자동 실행.",
            },
            {
                "level": TrustLevel.FULL_AUTO,
                "name": "Full Auto",
                "description": "모든 작업 자동 실행 가능.",
            },
        ],
        "promotion_conditions": TrustService.PROMOTION_CONDITIONS,
        "demotion_conditions": TrustService.DEMOTION_CONDITIONS,
    }


@router.get(
    "/stats",
    summary="Trust 통계 조회",
    description="전체 룰셋의 Trust Level 분포 통계를 조회합니다.",
)
async def get_trust_stats(
    tenant_id: Optional[UUID] = Query(None, description="테넌트 ID (선택)"),
    db: Session = Depends(get_db),
):
    """Trust 통계 조회"""
    from sqlalchemy import func
    from app.models.core import Ruleset

    query = db.query(
        Ruleset.trust_level,
        func.count(Ruleset.ruleset_id).label("count"),
        func.avg(Ruleset.trust_score).label("avg_score"),
    )

    if tenant_id:
        query = query.filter(Ruleset.tenant_id == tenant_id)

    stats = query.group_by(Ruleset.trust_level).all()

    return {
        "stats": [
            {
                "trust_level": s.trust_level,
                "trust_level_name": TrustService._level_to_name(s.trust_level),
                "count": s.count,
                "avg_score": float(s.avg_score) if s.avg_score else 0.0,
            }
            for s in stats
        ],
        "total_rulesets": sum(s.count for s in stats),
    }
