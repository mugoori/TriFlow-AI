# -*- coding: utf-8 -*-
"""
Decision Matrix Service

Trust Level × Risk Level → Execution Decision 매핑 관리 서비스.

Default Decision Matrix (A-2-5 스펙 기반):
┌───────────────┬──────────────┬──────────────┬──────────────┬──────────────┐
│ Trust\Risk    │     LOW      │    MEDIUM    │     HIGH     │   CRITICAL   │
├───────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ Level 0       │  approval    │   approval   │   approval   │    reject    │
│ (Proposed)    │              │              │              │              │
├───────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ Level 1       │  approval    │   approval   │   approval   │    reject    │
│ (Alert Only)  │              │              │              │              │
├───────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ Level 2       │ auto_execute │   approval   │   approval   │    reject    │
│ (Low Risk)    │              │              │              │              │
├───────────────┼──────────────┼──────────────┼──────────────┼──────────────┤
│ Level 3       │ auto_execute │ auto_execute │   approval   │   approval   │
│ (Full Auto)   │              │              │              │              │
└───────────────┴──────────────┴──────────────┴──────────────┴──────────────┘
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.models.auto_execution import (
    DecisionMatrix,
    RiskLevel,
    ExecutionDecision,
)

logger = logging.getLogger(__name__)


# 기본 Decision Matrix 정의 (A-2-5 스펙)
DEFAULT_MATRIX = {
    # Level 0 (Proposed): 모든 작업에 승인 필요, Critical은 거부
    (0, RiskLevel.LOW): ExecutionDecision.REQUIRE_APPROVAL,
    (0, RiskLevel.MEDIUM): ExecutionDecision.REQUIRE_APPROVAL,
    (0, RiskLevel.HIGH): ExecutionDecision.REQUIRE_APPROVAL,
    (0, RiskLevel.CRITICAL): ExecutionDecision.REJECT,

    # Level 1 (Alert Only): 모든 작업에 승인 필요, Critical은 거부
    (1, RiskLevel.LOW): ExecutionDecision.REQUIRE_APPROVAL,
    (1, RiskLevel.MEDIUM): ExecutionDecision.REQUIRE_APPROVAL,
    (1, RiskLevel.HIGH): ExecutionDecision.REQUIRE_APPROVAL,
    (1, RiskLevel.CRITICAL): ExecutionDecision.REJECT,

    # Level 2 (Low Risk Auto): Low만 자동, 나머지는 승인, Critical은 거부
    (2, RiskLevel.LOW): ExecutionDecision.AUTO_EXECUTE,
    (2, RiskLevel.MEDIUM): ExecutionDecision.REQUIRE_APPROVAL,
    (2, RiskLevel.HIGH): ExecutionDecision.REQUIRE_APPROVAL,
    (2, RiskLevel.CRITICAL): ExecutionDecision.REJECT,

    # Level 3 (Full Auto): Low/Medium 자동, High/Critical은 승인
    (3, RiskLevel.LOW): ExecutionDecision.AUTO_EXECUTE,
    (3, RiskLevel.MEDIUM): ExecutionDecision.AUTO_EXECUTE,
    (3, RiskLevel.HIGH): ExecutionDecision.REQUIRE_APPROVAL,
    (3, RiskLevel.CRITICAL): ExecutionDecision.REQUIRE_APPROVAL,
}


class DecisionMatrixService:
    """Decision Matrix 관리 서비스

    Trust Level × Risk Level 조합에 따른 실행 결정 관리.
    테넌트별 커스터마이징 지원.
    """

    def __init__(self, db: Session):
        self.db = db

    # ============================================
    # Decision Matrix 초기화
    # ============================================

    def initialize_default_matrix(
        self,
        tenant_id: UUID,
        *,
        created_by: Optional[UUID] = None,
    ) -> list[DecisionMatrix]:
        """기본 Decision Matrix 초기화

        테넌트에 기본 Decision Matrix 레코드를 생성.
        이미 존재하면 건너뜀.

        Returns:
            생성된 DecisionMatrix 레코드 리스트
        """
        created = []

        for (trust_level, risk_level), decision in DEFAULT_MATRIX.items():
            # 이미 존재하는지 확인
            existing = self.db.query(DecisionMatrix).filter(
                DecisionMatrix.tenant_id == tenant_id,
                DecisionMatrix.trust_level == trust_level,
                DecisionMatrix.risk_level == risk_level,
            ).first()

            if existing:
                continue

            # 새 레코드 생성
            matrix = DecisionMatrix(
                matrix_id=uuid4(),
                tenant_id=tenant_id,
                trust_level=trust_level,
                risk_level=risk_level,
                decision=decision,
                description=self._get_default_description(trust_level, risk_level, decision),
                created_by=created_by,
            )
            self.db.add(matrix)
            created.append(matrix)

        if created:
            self.db.commit()
            logger.info(f"Initialized {len(created)} decision matrix entries for tenant {tenant_id}")

        return created

    def _get_default_description(
        self,
        trust_level: int,
        risk_level: str,
        decision: str,
    ) -> str:
        """기본 설명 생성"""
        trust_names = {0: "Proposed", 1: "Alert Only", 2: "Low Risk Auto", 3: "Full Auto"}
        return f"Trust Level {trust_level} ({trust_names.get(trust_level, 'Unknown')}) + {risk_level} Risk → {decision}"

    # ============================================
    # Decision 평가
    # ============================================

    def evaluate_decision(
        self,
        tenant_id: UUID,
        trust_level: int,
        risk_level: str,
        *,
        trust_score: Optional[Decimal] = None,
    ) -> tuple[str, Optional[str]]:
        """실행 결정 평가

        Args:
            tenant_id: 테넌트 ID
            trust_level: Trust Level (0-3)
            risk_level: Risk Level (LOW, MEDIUM, HIGH, CRITICAL)
            trust_score: 현재 Trust Score (추가 조건 확인용)

        Returns:
            (decision, reason) 튜플
            - decision: auto_execute, require_approval, reject
            - reason: 결정 사유
        """
        # DB에서 매트릭스 조회
        matrix = self.db.query(DecisionMatrix).filter(
            DecisionMatrix.tenant_id == tenant_id,
            DecisionMatrix.trust_level == trust_level,
            DecisionMatrix.risk_level == risk_level,
            DecisionMatrix.is_active == True,  # noqa: E712
        ).first()

        # DB에 없으면 기본값 사용
        if not matrix:
            decision = DEFAULT_MATRIX.get(
                (trust_level, risk_level),
                ExecutionDecision.REQUIRE_APPROVAL  # 기본값: 승인 필요
            )
            reason = f"Default matrix: Trust Level {trust_level} + {risk_level} Risk"
            logger.debug(f"Using default matrix: {reason} -> {decision}")
            return decision, reason

        decision = matrix.decision
        reason = matrix.description or f"Matrix rule: Trust Level {trust_level} + {risk_level} Risk"

        # 추가 조건 확인
        if matrix.min_trust_score and trust_score:
            if trust_score < matrix.min_trust_score:
                decision = ExecutionDecision.REQUIRE_APPROVAL
                reason = f"Trust score {trust_score} < minimum {matrix.min_trust_score}"
                logger.debug(f"Decision override due to trust score: {reason}")

        logger.debug(f"Decision evaluated: Trust {trust_level} + {risk_level} Risk -> {decision}")
        return decision, reason

    def can_auto_execute(
        self,
        tenant_id: UUID,
        trust_level: int,
        risk_level: str,
        *,
        trust_score: Optional[Decimal] = None,
    ) -> bool:
        """자동 실행 가능 여부 확인

        Returns:
            True if auto execution is allowed
        """
        decision, _ = self.evaluate_decision(
            tenant_id=tenant_id,
            trust_level=trust_level,
            risk_level=risk_level,
            trust_score=trust_score,
        )
        return decision == ExecutionDecision.AUTO_EXECUTE

    def should_reject(
        self,
        tenant_id: UUID,
        trust_level: int,
        risk_level: str,
    ) -> bool:
        """거부 여부 확인

        Returns:
            True if action should be rejected
        """
        decision, _ = self.evaluate_decision(
            tenant_id=tenant_id,
            trust_level=trust_level,
            risk_level=risk_level,
        )
        return decision == ExecutionDecision.REJECT

    # ============================================
    # CRUD Operations
    # ============================================

    def get_matrix(self, tenant_id: UUID) -> list[DecisionMatrix]:
        """테넌트의 전체 Decision Matrix 조회"""
        return self.db.query(DecisionMatrix).filter(
            DecisionMatrix.tenant_id == tenant_id,
            DecisionMatrix.is_active == True,  # noqa: E712
        ).order_by(
            DecisionMatrix.trust_level,
            DecisionMatrix.risk_level,
        ).all()

    def get_matrix_entry(
        self,
        tenant_id: UUID,
        trust_level: int,
        risk_level: str,
    ) -> Optional[DecisionMatrix]:
        """특정 매트릭스 엔트리 조회"""
        return self.db.query(DecisionMatrix).filter(
            DecisionMatrix.tenant_id == tenant_id,
            DecisionMatrix.trust_level == trust_level,
            DecisionMatrix.risk_level == risk_level,
        ).first()

    def update_matrix_entry(
        self,
        tenant_id: UUID,
        trust_level: int,
        risk_level: str,
        *,
        decision: Optional[str] = None,
        min_trust_score: Optional[Decimal] = None,
        max_consecutive_failures: Optional[int] = None,
        require_recent_success: Optional[bool] = None,
        cooldown_seconds: Optional[int] = None,
        description: Optional[str] = None,
    ) -> Optional[DecisionMatrix]:
        """매트릭스 엔트리 업데이트"""
        matrix = self.get_matrix_entry(tenant_id, trust_level, risk_level)

        if not matrix:
            # 새로 생성
            matrix = DecisionMatrix(
                matrix_id=uuid4(),
                tenant_id=tenant_id,
                trust_level=trust_level,
                risk_level=risk_level,
                decision=decision or ExecutionDecision.REQUIRE_APPROVAL,
            )
            self.db.add(matrix)

        if decision is not None:
            matrix.decision = decision
        if min_trust_score is not None:
            matrix.min_trust_score = min_trust_score
        if max_consecutive_failures is not None:
            matrix.max_consecutive_failures = max_consecutive_failures
        if require_recent_success is not None:
            matrix.require_recent_success = require_recent_success
        if cooldown_seconds is not None:
            matrix.cooldown_seconds = cooldown_seconds
        if description is not None:
            matrix.description = description

        matrix.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(matrix)

        logger.info(f"Updated matrix entry: Trust {trust_level} + {risk_level} -> {matrix.decision}")
        return matrix

    def reset_to_default(self, tenant_id: UUID) -> int:
        """기본값으로 리셋

        Returns:
            업데이트된 엔트리 수
        """
        updated = 0

        for (trust_level, risk_level), decision in DEFAULT_MATRIX.items():
            matrix = self.get_matrix_entry(tenant_id, trust_level, risk_level)

            if matrix:
                matrix.decision = decision
                matrix.min_trust_score = None
                matrix.max_consecutive_failures = None
                matrix.require_recent_success = False
                matrix.cooldown_seconds = None
                matrix.description = self._get_default_description(trust_level, risk_level, decision)
                matrix.updated_at = datetime.utcnow()
                updated += 1
            else:
                # 새로 생성
                self.db.add(DecisionMatrix(
                    matrix_id=uuid4(),
                    tenant_id=tenant_id,
                    trust_level=trust_level,
                    risk_level=risk_level,
                    decision=decision,
                    description=self._get_default_description(trust_level, risk_level, decision),
                ))
                updated += 1

        self.db.commit()
        logger.info(f"Reset decision matrix to default for tenant {tenant_id}: {updated} entries")
        return updated

    # ============================================
    # 조회 유틸리티
    # ============================================

    def get_matrix_summary(self, tenant_id: UUID) -> dict:
        """매트릭스 요약 정보 조회

        Returns:
            {
                "trust_level_0": {"LOW": "approval", "MEDIUM": "approval", ...},
                "trust_level_1": {...},
                ...
            }
        """
        matrix_entries = self.get_matrix(tenant_id)

        # 기본값으로 시작
        summary = {}
        for trust_level in range(4):
            key = f"trust_level_{trust_level}"
            summary[key] = {}
            for risk_level in RiskLevel.all():
                default = DEFAULT_MATRIX.get((trust_level, risk_level), ExecutionDecision.REQUIRE_APPROVAL)
                summary[key][risk_level] = default

        # DB 값으로 덮어쓰기
        for entry in matrix_entries:
            key = f"trust_level_{entry.trust_level}"
            summary[key][entry.risk_level] = entry.decision

        return summary

    def validate_decision(self, decision: str) -> bool:
        """유효한 decision 값인지 확인"""
        return decision in ExecutionDecision.all()

    def validate_risk_level(self, risk_level: str) -> bool:
        """유효한 risk_level 값인지 확인"""
        return risk_level in RiskLevel.all()
