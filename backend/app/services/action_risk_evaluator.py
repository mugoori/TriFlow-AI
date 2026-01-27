# -*- coding: utf-8 -*-
"""
Action Risk Evaluator

작업 유형별 위험도 평가 서비스.

Default Action Risks:
┌─────────────────────────────┬─────────────┬────────────────────────────────┐
│ Action Type                 │ Risk Level  │ Description                    │
├─────────────────────────────┼─────────────┼────────────────────────────────┤
│ notification_*              │ LOW         │ 알림/로깅 작업                 │
│ log_*                       │ LOW         │ 로그 기록                      │
│ data_read_*                 │ LOW         │ 데이터 읽기                    │
├─────────────────────────────┼─────────────┼────────────────────────────────┤
│ data_write_*                │ MEDIUM      │ 데이터 쓰기                    │
│ parameter_adjust            │ MEDIUM      │ 파라미터 조정                  │
│ erp_order_create            │ MEDIUM      │ ERP 주문 생성                  │
├─────────────────────────────┼─────────────┼────────────────────────────────┤
│ mes_equipment_control       │ HIGH        │ 설비 제어                      │
│ erp_order_modify            │ HIGH        │ ERP 주문 수정                  │
│ production_schedule_change  │ HIGH        │ 생산 계획 변경                 │
├─────────────────────────────┼─────────────┼────────────────────────────────┤
│ production_line_stop        │ CRITICAL    │ 생산 라인 중단                 │
│ emergency_*                 │ CRITICAL    │ 긴급 작업                      │
│ financial_*                 │ CRITICAL    │ 재무 관련 작업                 │
└─────────────────────────────┴─────────────┴────────────────────────────────┘
"""
import fnmatch
import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.models.auto_execution import (
    ActionRiskDefinition,
    RiskLevel,
)

logger = logging.getLogger(__name__)


# 기본 Action Risk 정의
DEFAULT_ACTION_RISKS: dict[str, dict[str, Any]] = {
    # LOW Risk - 읽기 전용, 알림
    "notification_send": {
        "risk_level": RiskLevel.LOW,
        "category": "notification",
        "reversible": True,
        "affects_production": False,
        "description": "알림 발송 (Slack, Email 등)",
    },
    "notification_*": {
        "risk_level": RiskLevel.LOW,
        "category": "notification",
        "reversible": True,
        "affects_production": False,
        "description": "모든 알림 작업",
    },
    "log_*": {
        "risk_level": RiskLevel.LOW,
        "category": "data",
        "reversible": True,
        "affects_production": False,
        "description": "로그 기록 작업",
    },
    "data_read_*": {
        "risk_level": RiskLevel.LOW,
        "category": "data",
        "reversible": True,
        "affects_production": False,
        "description": "데이터 읽기 작업",
    },
    "report_generate": {
        "risk_level": RiskLevel.LOW,
        "category": "data",
        "reversible": True,
        "affects_production": False,
        "description": "리포트 생성",
    },

    # MEDIUM Risk - 데이터 변경, 일반 작업
    "data_write_*": {
        "risk_level": RiskLevel.MEDIUM,
        "category": "data",
        "reversible": True,
        "affects_production": False,
        "description": "데이터 쓰기 작업",
    },
    "parameter_adjust": {
        "risk_level": RiskLevel.MEDIUM,
        "category": "mes",
        "reversible": True,
        "affects_production": True,
        "description": "파라미터 조정",
    },
    "erp_order_create": {
        "risk_level": RiskLevel.MEDIUM,
        "category": "erp",
        "reversible": True,
        "affects_production": False,
        "affects_finance": True,
        "description": "ERP 주문 생성",
    },
    "inventory_adjust": {
        "risk_level": RiskLevel.MEDIUM,
        "category": "erp",
        "reversible": True,
        "affects_production": False,
        "description": "재고 조정",
    },
    "workflow_trigger": {
        "risk_level": RiskLevel.MEDIUM,
        "category": "workflow",
        "reversible": False,
        "affects_production": False,
        "description": "워크플로우 트리거",
    },

    # HIGH Risk - 생산 영향, 중요 변경
    "mes_equipment_control": {
        "risk_level": RiskLevel.HIGH,
        "category": "mes",
        "reversible": True,
        "affects_production": True,
        "description": "MES 설비 제어",
    },
    "erp_order_modify": {
        "risk_level": RiskLevel.HIGH,
        "category": "erp",
        "reversible": True,
        "affects_finance": True,
        "description": "ERP 주문 수정",
    },
    "erp_order_cancel": {
        "risk_level": RiskLevel.HIGH,
        "category": "erp",
        "reversible": False,
        "affects_finance": True,
        "description": "ERP 주문 취소",
    },
    "production_schedule_change": {
        "risk_level": RiskLevel.HIGH,
        "category": "mes",
        "reversible": True,
        "affects_production": True,
        "description": "생산 계획 변경",
    },
    "quality_hold": {
        "risk_level": RiskLevel.HIGH,
        "category": "quality",
        "reversible": True,
        "affects_production": True,
        "affects_compliance": True,
        "description": "품질 보류 처리",
    },

    # CRITICAL Risk - 긴급/위험 작업
    "production_line_stop": {
        "risk_level": RiskLevel.CRITICAL,
        "category": "mes",
        "reversible": True,
        "affects_production": True,
        "description": "생산 라인 중단",
    },
    "emergency_*": {
        "risk_level": RiskLevel.CRITICAL,
        "category": "emergency",
        "reversible": False,
        "affects_production": True,
        "description": "긴급 작업",
    },
    "financial_*": {
        "risk_level": RiskLevel.CRITICAL,
        "category": "finance",
        "reversible": False,
        "affects_finance": True,
        "description": "재무 관련 작업",
    },
    "compliance_report_submit": {
        "risk_level": RiskLevel.CRITICAL,
        "category": "compliance",
        "reversible": False,
        "affects_compliance": True,
        "description": "컴플라이언스 리포트 제출",
    },
}


class ActionRiskEvaluator:
    """Action Risk Evaluator

    작업 유형에 따른 위험도 평가.
    패턴 매칭과 테넌트별 커스터마이징 지원.
    """

    def __init__(self, db: Session):
        self.db = db

    # ============================================
    # Risk 평가
    # ============================================

    def evaluate_risk(
        self,
        tenant_id: UUID,
        action_type: str,
    ) -> tuple[str, Optional[int], dict]:
        """작업 위험도 평가

        Args:
            tenant_id: 테넌트 ID
            action_type: 작업 유형

        Returns:
            (risk_level, risk_score, risk_info) 튜플
            - risk_level: LOW, MEDIUM, HIGH, CRITICAL
            - risk_score: 0-100 (None if not set)
            - risk_info: 추가 위험 정보
        """
        # 1. DB에서 정확한 매칭 조회
        definition = self.db.query(ActionRiskDefinition).filter(
            ActionRiskDefinition.tenant_id == tenant_id,
            ActionRiskDefinition.action_type == action_type,
            ActionRiskDefinition.is_active == True,  # noqa: E712
        ).first()

        if definition:
            return self._extract_risk_info(definition)

        # 2. DB에서 패턴 매칭 조회
        pattern_definitions = self.db.query(ActionRiskDefinition).filter(
            ActionRiskDefinition.tenant_id == tenant_id,
            ActionRiskDefinition.action_pattern.isnot(None),
            ActionRiskDefinition.is_active == True,  # noqa: E712
        ).order_by(ActionRiskDefinition.priority).all()

        for definition in pattern_definitions:
            if fnmatch.fnmatch(action_type, definition.action_pattern):
                return self._extract_risk_info(definition)

        # 3. 기본값에서 정확한 매칭
        if action_type in DEFAULT_ACTION_RISKS:
            return self._extract_default_risk(action_type)

        # 4. 기본값에서 패턴 매칭
        for pattern, risk_info in DEFAULT_ACTION_RISKS.items():
            if "*" in pattern and fnmatch.fnmatch(action_type, pattern):
                risk_level = risk_info.get("risk_level", RiskLevel.MEDIUM)
                return risk_level, None, risk_info

        # 5. 기본값: MEDIUM (알 수 없는 작업은 중간 위험도)
        logger.warning(f"Unknown action type: {action_type}, defaulting to MEDIUM risk")
        return RiskLevel.MEDIUM, None, {"description": "Unknown action type"}

    def _extract_risk_info(self, definition: ActionRiskDefinition) -> tuple[str, Optional[int], dict]:
        """DB 정의에서 위험 정보 추출"""
        risk_info = {
            "category": definition.category,
            "reversible": definition.reversible,
            "affects_production": definition.affects_production,
            "affects_finance": definition.affects_finance,
            "affects_compliance": definition.affects_compliance,
            "description": definition.description,
            "risk_factors": definition.risk_factors,
            "source": "database",
        }
        return definition.risk_level, definition.risk_score, risk_info

    def _extract_default_risk(self, action_type: str) -> tuple[str, Optional[int], dict]:
        """기본 정의에서 위험 정보 추출"""
        risk_info = DEFAULT_ACTION_RISKS.get(action_type, {}).copy()
        risk_level = risk_info.pop("risk_level", RiskLevel.MEDIUM)
        risk_info["source"] = "default"
        return risk_level, None, risk_info

    def get_risk_level(self, tenant_id: UUID, action_type: str) -> str:
        """위험도 레벨만 조회"""
        risk_level, _, _ = self.evaluate_risk(tenant_id, action_type)
        return risk_level

    def is_critical(self, tenant_id: UUID, action_type: str) -> bool:
        """CRITICAL 위험도인지 확인"""
        return self.get_risk_level(tenant_id, action_type) == RiskLevel.CRITICAL

    def is_high_or_above(self, tenant_id: UUID, action_type: str) -> bool:
        """HIGH 이상 위험도인지 확인"""
        level = self.get_risk_level(tenant_id, action_type)
        return level in [RiskLevel.HIGH, RiskLevel.CRITICAL]

    # ============================================
    # 기본값 초기화
    # ============================================

    def initialize_defaults(self, tenant_id: UUID) -> list[ActionRiskDefinition]:
        """기본 위험도 정의 초기화

        테넌트에 기본 ActionRiskDefinition 레코드를 생성.

        Returns:
            생성된 ActionRiskDefinition 레코드 리스트
        """
        created = []

        for action_type, risk_info in DEFAULT_ACTION_RISKS.items():
            # 이미 존재하는지 확인
            existing = self.db.query(ActionRiskDefinition).filter(
                ActionRiskDefinition.tenant_id == tenant_id,
                ActionRiskDefinition.action_type == action_type,
            ).first()

            if existing:
                continue

            # 패턴 여부 확인
            action_pattern = action_type if "*" in action_type else None
            actual_action_type = action_type.replace("*", "_wildcard") if "*" in action_type else action_type

            definition = ActionRiskDefinition(
                risk_def_id=uuid4(),
                tenant_id=tenant_id,
                action_type=actual_action_type,
                action_pattern=action_pattern,
                category=risk_info.get("category"),
                risk_level=risk_info.get("risk_level", RiskLevel.MEDIUM),
                reversible=risk_info.get("reversible", True),
                affects_production=risk_info.get("affects_production", False),
                affects_finance=risk_info.get("affects_finance", False),
                affects_compliance=risk_info.get("affects_compliance", False),
                description=risk_info.get("description"),
                priority=100,
            )
            self.db.add(definition)
            created.append(definition)

        if created:
            self.db.commit()
            logger.info(f"Initialized {len(created)} action risk definitions for tenant {tenant_id}")

        return created

    # ============================================
    # CRUD Operations
    # ============================================

    def get_definitions(
        self,
        tenant_id: UUID,
        *,
        category: Optional[str] = None,
        risk_level: Optional[str] = None,
    ) -> list[ActionRiskDefinition]:
        """테넌트의 위험도 정의 목록 조회"""
        query = self.db.query(ActionRiskDefinition).filter(
            ActionRiskDefinition.tenant_id == tenant_id,
            ActionRiskDefinition.is_active == True,  # noqa: E712
        )

        if category:
            query = query.filter(ActionRiskDefinition.category == category)
        if risk_level:
            query = query.filter(ActionRiskDefinition.risk_level == risk_level)

        return query.order_by(
            ActionRiskDefinition.priority,
            ActionRiskDefinition.action_type,
        ).all()

    def get_definition(
        self,
        tenant_id: UUID,
        action_type: str,
    ) -> Optional[ActionRiskDefinition]:
        """특정 위험도 정의 조회"""
        return self.db.query(ActionRiskDefinition).filter(
            ActionRiskDefinition.tenant_id == tenant_id,
            ActionRiskDefinition.action_type == action_type,
        ).first()

    def create_definition(
        self,
        tenant_id: UUID,
        action_type: str,
        risk_level: str,
        *,
        action_pattern: Optional[str] = None,
        category: Optional[str] = None,
        risk_score: Optional[int] = None,
        reversible: bool = True,
        affects_production: bool = False,
        affects_finance: bool = False,
        affects_compliance: bool = False,
        description: Optional[str] = None,
        priority: int = 100,
    ) -> ActionRiskDefinition:
        """위험도 정의 생성"""
        definition = ActionRiskDefinition(
            risk_def_id=uuid4(),
            tenant_id=tenant_id,
            action_type=action_type,
            action_pattern=action_pattern,
            category=category,
            risk_level=risk_level,
            risk_score=risk_score,
            reversible=reversible,
            affects_production=affects_production,
            affects_finance=affects_finance,
            affects_compliance=affects_compliance,
            description=description,
            priority=priority,
        )
        self.db.add(definition)
        self.db.commit()
        self.db.refresh(definition)

        logger.info(f"Created risk definition: {action_type} -> {risk_level}")
        return definition

    def update_definition(
        self,
        tenant_id: UUID,
        action_type: str,
        *,
        risk_level: Optional[str] = None,
        action_pattern: Optional[str] = None,
        category: Optional[str] = None,
        risk_score: Optional[int] = None,
        reversible: Optional[bool] = None,
        affects_production: Optional[bool] = None,
        affects_finance: Optional[bool] = None,
        affects_compliance: Optional[bool] = None,
        description: Optional[str] = None,
        priority: Optional[int] = None,
    ) -> Optional[ActionRiskDefinition]:
        """위험도 정의 업데이트"""
        definition = self.get_definition(tenant_id, action_type)
        if not definition:
            return None

        if risk_level is not None:
            definition.risk_level = risk_level
        if action_pattern is not None:
            definition.action_pattern = action_pattern
        if category is not None:
            definition.category = category
        if risk_score is not None:
            definition.risk_score = risk_score
        if reversible is not None:
            definition.reversible = reversible
        if affects_production is not None:
            definition.affects_production = affects_production
        if affects_finance is not None:
            definition.affects_finance = affects_finance
        if affects_compliance is not None:
            definition.affects_compliance = affects_compliance
        if description is not None:
            definition.description = description
        if priority is not None:
            definition.priority = priority

        definition.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(definition)

        logger.info(f"Updated risk definition: {action_type}")
        return definition

    def delete_definition(
        self,
        tenant_id: UUID,
        action_type: str,
        *,
        soft_delete: bool = True,
    ) -> bool:
        """위험도 정의 삭제"""
        definition = self.get_definition(tenant_id, action_type)
        if not definition:
            return False

        if soft_delete:
            definition.is_active = False
            definition.updated_at = datetime.utcnow()
        else:
            self.db.delete(definition)

        self.db.commit()
        logger.info(f"Deleted risk definition: {action_type} (soft={soft_delete})")
        return True

    # ============================================
    # 유틸리티
    # ============================================

    def get_categories(self, tenant_id: UUID) -> list[str]:
        """사용 가능한 카테고리 목록 조회"""
        result = self.db.query(ActionRiskDefinition.category).filter(
            ActionRiskDefinition.tenant_id == tenant_id,
            ActionRiskDefinition.category.isnot(None),
            ActionRiskDefinition.is_active == True,  # noqa: E712
        ).distinct().all()

        categories = [r[0] for r in result]

        # 기본 카테고리 추가
        default_categories = set()
        for risk_info in DEFAULT_ACTION_RISKS.values():
            cat = risk_info.get("category")
            if cat:
                default_categories.add(cat)

        return sorted(set(categories) | default_categories)

    def get_risk_summary(self, tenant_id: UUID) -> dict:
        """위험도 요약 정보"""
        definitions = self.get_definitions(tenant_id)

        summary = {
            "total": len(definitions),
            "by_level": {
                RiskLevel.LOW: 0,
                RiskLevel.MEDIUM: 0,
                RiskLevel.HIGH: 0,
                RiskLevel.CRITICAL: 0,
            },
            "by_category": {},
        }

        for definition in definitions:
            summary["by_level"][definition.risk_level] = \
                summary["by_level"].get(definition.risk_level, 0) + 1

            if definition.category:
                summary["by_category"][definition.category] = \
                    summary["by_category"].get(definition.category, 0) + 1

        return summary
