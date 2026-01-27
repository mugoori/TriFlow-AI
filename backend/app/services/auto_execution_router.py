# -*- coding: utf-8 -*-
"""
Auto Execution Router

Trust Level × Risk Level → Execution Decision 라우팅 서비스.

Auto Execution 흐름:
1. Ruleset의 Trust Level/Score 조회 (TrustService)
2. Action의 Risk Level 평가 (ActionRiskEvaluator)
3. Decision Matrix에서 결정 조회 (DecisionMatrixService)
4. 결정에 따라 라우팅:
   - auto_execute: 자동 실행
   - require_approval: 승인 워크플로우 호출
   - reject: 실행 거부
5. 실행 로그 기록 (AutoExecutionLog)
"""
import logging
import time
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.models.auto_execution import (
    AutoExecutionLog,
    ExecutionDecision,
    ExecutionStatus,
    RiskLevel,
)
from app.models.core import Ruleset
from app.services.decision_matrix_service import DecisionMatrixService
from app.services.action_risk_evaluator import ActionRiskEvaluator
from app.services.trust_service import TrustLevel, TrustService

logger = logging.getLogger(__name__)


class ExecutionResult:
    """실행 결과 DTO"""

    def __init__(
        self,
        decision: str,
        executed: bool,
        *,
        result: Optional[dict] = None,
        approval_id: Optional[str] = None,
        error: Optional[str] = None,
        log_id: Optional[str] = None,
    ):
        self.decision = decision
        self.executed = executed
        self.result = result
        self.approval_id = approval_id
        self.error = error
        self.log_id = log_id

    def to_dict(self) -> dict:
        return {
            "decision": self.decision,
            "executed": self.executed,
            "result": self.result,
            "approval_id": self.approval_id,
            "error": self.error,
            "log_id": self.log_id,
        }

    @property
    def needs_approval(self) -> bool:
        return self.decision == ExecutionDecision.REQUIRE_APPROVAL

    @property
    def was_rejected(self) -> bool:
        return self.decision == ExecutionDecision.REJECT

    @property
    def was_auto_executed(self) -> bool:
        return self.decision == ExecutionDecision.AUTO_EXECUTE and self.executed


class AutoExecutionRouter:
    """Auto Execution Router

    Trust-based 자동 실행 라우팅.
    TrustService, ActionRiskEvaluator, DecisionMatrixService 통합.
    """

    def __init__(self, db: Session):
        self.db = db
        self.trust_service = TrustService(db)
        self.risk_evaluator = ActionRiskEvaluator(db)
        self.decision_matrix = DecisionMatrixService(db)

    # ============================================
    # 라우팅 결정
    # ============================================

    def evaluate(
        self,
        tenant_id: UUID,
        action_type: str,
        *,
        ruleset_id: Optional[UUID] = None,
        trust_level_override: Optional[int] = None,
        trust_score_override: Optional[Decimal] = None,
    ) -> tuple[str, str, dict]:
        """실행 결정 평가 (실행 없이 결정만 반환)

        Args:
            tenant_id: 테넌트 ID
            action_type: 작업 유형
            ruleset_id: 룰셋 ID (Trust Level 조회용)
            trust_level_override: Trust Level 오버라이드
            trust_score_override: Trust Score 오버라이드

        Returns:
            (decision, reason, context) 튜플
            - decision: auto_execute, require_approval, reject
            - reason: 결정 사유
            - context: 평가 컨텍스트 (trust_level, risk_level 등)
        """
        # 1. Trust Level/Score 조회
        trust_level = trust_level_override if trust_level_override is not None else TrustLevel.PROPOSED
        trust_score = trust_score_override

        if ruleset_id and trust_level_override is None:
            ruleset = self.db.query(Ruleset).filter(
                Ruleset.ruleset_id == ruleset_id
            ).first()
            if ruleset:
                trust_level = ruleset.trust_level
                trust_score = ruleset.trust_score

        # 2. Risk Level 평가
        risk_level, risk_score, risk_info = self.risk_evaluator.evaluate_risk(
            tenant_id=tenant_id,
            action_type=action_type,
        )

        # 3. Decision Matrix에서 결정 조회
        decision, decision_reason = self.decision_matrix.evaluate_decision(
            tenant_id=tenant_id,
            trust_level=trust_level,
            risk_level=risk_level,
            trust_score=trust_score,
        )

        # 4. 컨텍스트 구성
        context = {
            "trust_level": trust_level,
            "trust_level_name": self._level_to_name(trust_level),
            "trust_score": float(trust_score) if trust_score else None,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "risk_info": risk_info,
            "action_type": action_type,
            "ruleset_id": str(ruleset_id) if ruleset_id else None,
        }

        logger.info(
            f"Execution decision: action={action_type}, "
            f"trust={trust_level}, risk={risk_level} -> {decision}"
        )

        return decision, decision_reason, context

    def can_auto_execute(
        self,
        tenant_id: UUID,
        action_type: str,
        *,
        ruleset_id: Optional[UUID] = None,
    ) -> bool:
        """자동 실행 가능 여부만 확인"""
        decision, _, _ = self.evaluate(
            tenant_id=tenant_id,
            action_type=action_type,
            ruleset_id=ruleset_id,
        )
        return decision == ExecutionDecision.AUTO_EXECUTE

    # ============================================
    # 라우팅 실행
    # ============================================

    def route(
        self,
        tenant_id: UUID,
        action_type: str,
        action_params: dict,
        *,
        ruleset_id: Optional[UUID] = None,
        workflow_id: Optional[UUID] = None,
        instance_id: Optional[UUID] = None,
        node_id: Optional[str] = None,
        executor: Optional[Callable[[dict], dict]] = None,
        approval_handler: Optional[Callable[[dict], str]] = None,
    ) -> ExecutionResult:
        """실행 라우팅

        Args:
            tenant_id: 테넌트 ID
            action_type: 작업 유형
            action_params: 작업 파라미터
            ruleset_id: 룰셋 ID
            workflow_id: 워크플로우 ID
            instance_id: 인스턴스 ID
            node_id: 노드 ID
            executor: 자동 실행 시 호출할 함수 (params -> result)
            approval_handler: 승인 요청 시 호출할 함수 (context -> approval_id)

        Returns:
            ExecutionResult
        """
        start_time = time.time()

        # 1. 결정 평가
        decision, reason, context = self.evaluate(
            tenant_id=tenant_id,
            action_type=action_type,
            ruleset_id=ruleset_id,
        )

        # 2. 로그 생성
        log = self._create_log(
            tenant_id=tenant_id,
            action_type=action_type,
            action_params=action_params,
            ruleset_id=ruleset_id,
            workflow_id=workflow_id,
            instance_id=instance_id,
            node_id=node_id,
            decision=decision,
            reason=reason,
            context=context,
        )

        # 3. 결정에 따라 라우팅
        result = None
        error = None
        approval_id = None
        executed = False

        try:
            if decision == ExecutionDecision.AUTO_EXECUTE:
                # 자동 실행
                if executor:
                    result = executor(action_params)
                    executed = True
                    log.mark_executed(
                        result=result,
                        latency_ms=int((time.time() - start_time) * 1000),
                    )
                else:
                    # executor 없으면 실행 가능 상태만 표시
                    log.execution_status = ExecutionStatus.PENDING
                    executed = False

            elif decision == ExecutionDecision.REQUIRE_APPROVAL:
                # 승인 요청
                if approval_handler:
                    approval_id = approval_handler({
                        "action_type": action_type,
                        "action_params": action_params,
                        "context": context,
                        "log_id": str(log.log_id),
                    })
                    log.approval_id = UUID(approval_id) if approval_id else None
                    log.execution_status = ExecutionStatus.PENDING

            else:  # REJECT
                log.execution_status = ExecutionStatus.REJECTED
                log.decision_reason = f"Rejected: {reason}"

        except Exception as e:
            error = str(e)
            log.mark_failed(error_message=error)
            logger.error(f"Execution failed: {action_type} - {e}")

        # 4. 로그 저장
        self.db.commit()

        return ExecutionResult(
            decision=decision,
            executed=executed,
            result=result,
            approval_id=approval_id,
            error=error,
            log_id=str(log.log_id),
        )

    def _create_log(
        self,
        tenant_id: UUID,
        action_type: str,
        action_params: dict,
        ruleset_id: Optional[UUID],
        workflow_id: Optional[UUID],
        instance_id: Optional[UUID],
        node_id: Optional[str],
        decision: str,
        reason: str,
        context: dict,
    ) -> AutoExecutionLog:
        """실행 로그 생성"""
        log = AutoExecutionLog(
            log_id=uuid4(),
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            instance_id=instance_id,
            node_id=node_id,
            ruleset_id=ruleset_id,
            action_type=action_type,
            action_params=action_params,
            trust_level=context.get("trust_level", 0),
            trust_score=context.get("trust_score"),
            risk_level=context.get("risk_level", RiskLevel.MEDIUM),
            risk_score=context.get("risk_score"),
            decision=decision,
            decision_reason=reason,
            execution_status=ExecutionStatus.PENDING,
            execution_metadata={
                "risk_info": context.get("risk_info"),
                "trust_level_name": context.get("trust_level_name"),
            },
        )
        self.db.add(log)
        return log

    # ============================================
    # 승인 후 실행
    # ============================================

    def execute_after_approval(
        self,
        log_id: UUID,
        approved_by: UUID,
        executor: Callable[[dict], dict],
    ) -> ExecutionResult:
        """승인 후 실행

        Args:
            log_id: 실행 로그 ID
            approved_by: 승인자 ID
            executor: 실행 함수

        Returns:
            ExecutionResult
        """
        log = self.db.query(AutoExecutionLog).filter(
            AutoExecutionLog.log_id == log_id
        ).first()

        if not log:
            return ExecutionResult(
                decision=ExecutionDecision.REJECT,
                executed=False,
                error="Log not found",
            )

        if log.decision != ExecutionDecision.REQUIRE_APPROVAL:
            return ExecutionResult(
                decision=log.decision,
                executed=False,
                error="This action does not require approval",
            )

        if log.execution_status != ExecutionStatus.PENDING:
            return ExecutionResult(
                decision=log.decision,
                executed=False,
                error=f"Invalid status: {log.execution_status}",
            )

        start_time = time.time()

        try:
            result = executor(log.action_params or {})

            log.mark_approved(str(approved_by))
            log.mark_executed(
                result=result,
                latency_ms=int((time.time() - start_time) * 1000),
            )

            self.db.commit()

            return ExecutionResult(
                decision=log.decision,
                executed=True,
                result=result,
                log_id=str(log.log_id),
            )

        except Exception as e:
            log.mark_approved(str(approved_by))
            log.mark_failed(error_message=str(e))
            self.db.commit()

            return ExecutionResult(
                decision=log.decision,
                executed=False,
                error=str(e),
                log_id=str(log.log_id),
            )

    def reject_after_approval(
        self,
        log_id: UUID,
        rejected_by: UUID,
        reason: Optional[str] = None,
    ) -> bool:
        """승인 거부 처리"""
        log = self.db.query(AutoExecutionLog).filter(
            AutoExecutionLog.log_id == log_id
        ).first()

        if not log or log.execution_status != ExecutionStatus.PENDING:
            return False

        log.execution_status = ExecutionStatus.REJECTED
        log.approved_by = rejected_by
        log.approved_at = datetime.utcnow()
        log.decision_reason = reason or "Rejected by user"

        self.db.commit()
        return True

    # ============================================
    # 로그 조회
    # ============================================

    def get_log(self, log_id: UUID) -> Optional[AutoExecutionLog]:
        """실행 로그 조회"""
        return self.db.query(AutoExecutionLog).filter(
            AutoExecutionLog.log_id == log_id
        ).first()

    def get_logs(
        self,
        tenant_id: UUID,
        *,
        ruleset_id: Optional[UUID] = None,
        workflow_id: Optional[UUID] = None,
        decision: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AutoExecutionLog]:
        """실행 로그 목록 조회"""
        query = self.db.query(AutoExecutionLog).filter(
            AutoExecutionLog.tenant_id == tenant_id
        )

        if ruleset_id:
            query = query.filter(AutoExecutionLog.ruleset_id == ruleset_id)
        if workflow_id:
            query = query.filter(AutoExecutionLog.workflow_id == workflow_id)
        if decision:
            query = query.filter(AutoExecutionLog.decision == decision)
        if status:
            query = query.filter(AutoExecutionLog.execution_status == status)

        return query.order_by(
            AutoExecutionLog.created_at.desc()
        ).offset(offset).limit(limit).all()

    def get_pending_approvals(
        self,
        tenant_id: UUID,
        *,
        limit: int = 100,
    ) -> list[AutoExecutionLog]:
        """승인 대기 중인 실행 목록 조회"""
        return self.db.query(AutoExecutionLog).filter(
            AutoExecutionLog.tenant_id == tenant_id,
            AutoExecutionLog.decision == ExecutionDecision.REQUIRE_APPROVAL,
            AutoExecutionLog.execution_status == ExecutionStatus.PENDING,
        ).order_by(
            AutoExecutionLog.created_at.asc()
        ).limit(limit).all()

    def get_execution_stats(
        self,
        tenant_id: UUID,
        *,
        ruleset_id: Optional[UUID] = None,
        days: int = 7,
    ) -> dict:
        """실행 통계 조회"""
        from datetime import timedelta
        from sqlalchemy import func

        since = datetime.utcnow() - timedelta(days=days)

        query = self.db.query(AutoExecutionLog).filter(
            AutoExecutionLog.tenant_id == tenant_id,
            AutoExecutionLog.created_at >= since,
        )

        if ruleset_id:
            query = query.filter(AutoExecutionLog.ruleset_id == ruleset_id)

        logs = query.all()

        stats = {
            "total": len(logs),
            "by_decision": {
                ExecutionDecision.AUTO_EXECUTE: 0,
                ExecutionDecision.REQUIRE_APPROVAL: 0,
                ExecutionDecision.REJECT: 0,
            },
            "by_status": {
                ExecutionStatus.PENDING: 0,
                ExecutionStatus.EXECUTED: 0,
                ExecutionStatus.APPROVED: 0,
                ExecutionStatus.REJECTED: 0,
                ExecutionStatus.FAILED: 0,
            },
            "auto_execution_rate": 0.0,
            "avg_latency_ms": 0,
        }

        latencies = []
        for log in logs:
            stats["by_decision"][log.decision] = \
                stats["by_decision"].get(log.decision, 0) + 1
            stats["by_status"][log.execution_status] = \
                stats["by_status"].get(log.execution_status, 0) + 1
            if log.latency_ms:
                latencies.append(log.latency_ms)

        if stats["total"] > 0:
            stats["auto_execution_rate"] = \
                stats["by_decision"][ExecutionDecision.AUTO_EXECUTE] / stats["total"]

        if latencies:
            stats["avg_latency_ms"] = sum(latencies) // len(latencies)

        return stats

    # ============================================
    # 유틸리티
    # ============================================

    @staticmethod
    def _level_to_name(level: int) -> str:
        """Trust Level 이름 변환"""
        names = {0: "Proposed", 1: "Alert Only", 2: "Low Risk Auto", 3: "Full Auto"}
        return names.get(level, "Unknown")
