# -*- coding: utf-8 -*-
"""
Trust Service - V2.0 Progressive Trust Model

A-2-5 스펙 기반 구현:
- Trust Score 계산: 0.35×Accuracy + 0.25×Consistency + 0.15×Frequency + 0.15×Feedback + 0.10×Age
- Trust Level 승격/강등 조건 평가
- Trust Level 변경 이력 관리

Trust Levels:
- Level 0 (Proposed): 새로운 룰, 검증 필요
- Level 1 (Alert Only): 알림만, 자동 실행 없음
- Level 2 (Low Risk Auto): 저위험 작업 자동 실행
- Level 3 (Full Auto): 모든 작업 자동 실행
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.core import Ruleset, JudgmentExecution, FeedbackLog, TrustLevelHistory

logger = logging.getLogger(__name__)


class TrustLevel:
    """Trust Level 상수"""
    PROPOSED = 0       # 새 룰, 검증 필요
    ALERT_ONLY = 1     # 알림만
    LOW_RISK_AUTO = 2  # 저위험 자동
    FULL_AUTO = 3      # 완전 자동


class TrustService:
    """Progressive Trust Model 서비스

    A-2-5 스펙 기반 Trust Score 계산 및 Level 관리
    """

    # Trust Score 가중치 (A-2-5 스펙)
    WEIGHT_ACCURACY = Decimal("0.35")
    WEIGHT_CONSISTENCY = Decimal("0.25")
    WEIGHT_FREQUENCY = Decimal("0.15")
    WEIGHT_FEEDBACK = Decimal("0.15")
    WEIGHT_AGE = Decimal("0.10")

    # 승격 조건 (A-2-5 스펙)
    PROMOTION_CONDITIONS = {
        # Level 0 → 1: 50회 실행, 85% 정확도, 7일 운영
        0: {"min_executions": 50, "min_accuracy": 0.85, "min_days": 7},
        # Level 1 → 2: 100회 실행, 90% 정확도, 14일 운영
        1: {"min_executions": 100, "min_accuracy": 0.90, "min_days": 14},
        # Level 2 → 3: 200회 실행, 95% 정확도, 30일 운영
        2: {"min_executions": 200, "min_accuracy": 0.95, "min_days": 30},
    }

    # 강등 조건
    DEMOTION_CONDITIONS = {
        # Level 3 → 2: 정확도 90% 미만 또는 연속 3회 부정 피드백
        3: {"max_accuracy": 0.90, "consecutive_negative": 3},
        # Level 2 → 1: 정확도 85% 미만 또는 연속 5회 부정 피드백
        2: {"max_accuracy": 0.85, "consecutive_negative": 5},
        # Level 1 → 0: 정확도 80% 미만 또는 연속 10회 부정 피드백
        1: {"max_accuracy": 0.80, "consecutive_negative": 10},
    }

    def __init__(self, db: Session):
        self.db = db

    def calculate_trust_score(
        self,
        ruleset_id: UUID,
    ) -> Tuple[Decimal, Dict[str, Decimal]]:
        """Trust Score 계산

        공식: 0.35×Accuracy + 0.25×Consistency + 0.15×Frequency + 0.15×Feedback + 0.10×Age

        Returns:
            Tuple[total_score, components_dict]
        """
        ruleset = self.db.query(Ruleset).filter(Ruleset.ruleset_id == ruleset_id).first()
        if not ruleset:
            raise ValueError(f"Ruleset {ruleset_id} not found")

        # 1. Accuracy 컴포넌트 (정확도)
        accuracy = self._calculate_accuracy_component(ruleset)

        # 2. Consistency 컴포넌트 (일관성)
        consistency = self._calculate_consistency_component(ruleset)

        # 3. Frequency 컴포넌트 (실행 빈도)
        frequency = self._calculate_frequency_component(ruleset)

        # 4. Feedback 컴포넌트 (피드백 비율)
        feedback = self._calculate_feedback_component(ruleset)

        # 5. Age 컴포넌트 (운영 기간)
        age = self._calculate_age_component(ruleset)

        # 가중 합계
        total_score = (
            self.WEIGHT_ACCURACY * accuracy +
            self.WEIGHT_CONSISTENCY * consistency +
            self.WEIGHT_FREQUENCY * frequency +
            self.WEIGHT_FEEDBACK * feedback +
            self.WEIGHT_AGE * age
        )

        # 0.0 ~ 1.0 범위로 제한
        total_score = max(Decimal("0.0"), min(Decimal("1.0"), total_score))

        components = {
            "accuracy": round(accuracy, 4),
            "consistency": round(consistency, 4),
            "frequency": round(frequency, 4),
            "feedback": round(feedback, 4),
            "age": round(age, 4),
        }

        return round(total_score, 4), components

    def _calculate_accuracy_component(self, ruleset: Ruleset) -> Decimal:
        """정확도 컴포넌트 계산

        피드백 기반 정확도: positive / (positive + negative)
        """
        total_feedback = ruleset.positive_feedback_count + ruleset.negative_feedback_count
        if total_feedback == 0:
            return Decimal("0.5")  # 피드백 없으면 중립

        accuracy = Decimal(ruleset.positive_feedback_count) / Decimal(total_feedback)
        return accuracy

    def _calculate_consistency_component(self, ruleset: Ruleset) -> Decimal:
        """일관성 컴포넌트 계산

        최근 30일간 결과의 일관성 (동일 결과 비율)
        """
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        # 최근 30일간 실행 결과 조회
        executions = self.db.query(JudgmentExecution).filter(
            JudgmentExecution.ruleset_id == ruleset.ruleset_id,
            JudgmentExecution.created_at >= thirty_days_ago,
        ).all()

        if len(executions) < 5:
            return Decimal("0.5")  # 데이터 부족

        # 결과별 카운트
        result_counts: Dict[str, int] = {}
        for exec in executions:
            result_counts[exec.result] = result_counts.get(exec.result, 0) + 1

        # 가장 많은 결과의 비율
        max_count = max(result_counts.values())
        consistency = Decimal(max_count) / Decimal(len(executions))

        return consistency

    def _calculate_frequency_component(self, ruleset: Ruleset) -> Decimal:
        """빈도 컴포넌트 계산

        최근 7일간 실행 빈도를 기준으로 점수화
        - 0회: 0.0
        - 1-10회: 0.3
        - 11-50회: 0.6
        - 51회 이상: 1.0
        """
        seven_days_ago = datetime.utcnow() - timedelta(days=7)

        recent_count = self.db.query(func.count(JudgmentExecution.execution_id)).filter(
            JudgmentExecution.ruleset_id == ruleset.ruleset_id,
            JudgmentExecution.created_at >= seven_days_ago,
        ).scalar() or 0

        if recent_count == 0:
            return Decimal("0.0")
        elif recent_count <= 10:
            return Decimal("0.3")
        elif recent_count <= 50:
            return Decimal("0.6")
        else:
            return Decimal("1.0")

    def _calculate_feedback_component(self, ruleset: Ruleset) -> Decimal:
        """피드백 컴포넌트 계산

        긍정 피드백 비율 (최근 30일)
        """
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        # 최근 30일간 피드백 조회
        positive_count = self.db.query(func.count(FeedbackLog.log_id)).filter(
            FeedbackLog.ruleset_id == ruleset.ruleset_id,
            FeedbackLog.feedback_type == "positive",
            FeedbackLog.created_at >= thirty_days_ago,
        ).scalar() or 0

        negative_count = self.db.query(func.count(FeedbackLog.log_id)).filter(
            FeedbackLog.ruleset_id == ruleset.ruleset_id,
            FeedbackLog.feedback_type == "negative",
            FeedbackLog.created_at >= thirty_days_ago,
        ).scalar() or 0

        total = positive_count + negative_count
        if total == 0:
            return Decimal("0.5")  # 피드백 없으면 중립

        return Decimal(positive_count) / Decimal(total)

    def _calculate_age_component(self, ruleset: Ruleset) -> Decimal:
        """운영 기간 컴포넌트 계산

        - 0-7일: 0.2
        - 8-14일: 0.4
        - 15-30일: 0.6
        - 31-60일: 0.8
        - 61일 이상: 1.0
        """
        days_active = (datetime.utcnow() - ruleset.created_at).days

        if days_active <= 7:
            return Decimal("0.2")
        elif days_active <= 14:
            return Decimal("0.4")
        elif days_active <= 30:
            return Decimal("0.6")
        elif days_active <= 60:
            return Decimal("0.8")
        else:
            return Decimal("1.0")

    def evaluate_promotion(self, ruleset_id: UUID) -> Optional[int]:
        """승격 조건 평가

        Returns:
            승격 가능한 새 레벨, 또는 None (승격 불가)
        """
        ruleset = self.db.query(Ruleset).filter(Ruleset.ruleset_id == ruleset_id).first()
        if not ruleset:
            return None

        current_level = ruleset.trust_level
        if current_level >= TrustLevel.FULL_AUTO:
            return None  # 이미 최고 레벨

        conditions = self.PROMOTION_CONDITIONS.get(current_level)
        if not conditions:
            return None

        # 조건 확인
        if ruleset.execution_count < conditions["min_executions"]:
            logger.debug(f"Promotion blocked: execution_count {ruleset.execution_count} < {conditions['min_executions']}")
            return None

        accuracy = float(ruleset.accuracy_rate or 0)
        if accuracy < conditions["min_accuracy"]:
            logger.debug(f"Promotion blocked: accuracy {accuracy} < {conditions['min_accuracy']}")
            return None

        days_since_last_promotion = 0
        if ruleset.last_promoted_at:
            days_since_last_promotion = (datetime.utcnow() - ruleset.last_promoted_at).days
        else:
            days_since_last_promotion = (datetime.utcnow() - ruleset.created_at).days

        if days_since_last_promotion < conditions["min_days"]:
            logger.debug(f"Promotion blocked: days {days_since_last_promotion} < {conditions['min_days']}")
            return None

        # 모든 조건 충족
        return current_level + 1

    def evaluate_demotion(self, ruleset_id: UUID) -> Optional[int]:
        """강등 조건 평가

        Returns:
            강등되어야 할 새 레벨, 또는 None (강등 불필요)
        """
        ruleset = self.db.query(Ruleset).filter(Ruleset.ruleset_id == ruleset_id).first()
        if not ruleset:
            return None

        current_level = ruleset.trust_level
        if current_level <= TrustLevel.PROPOSED:
            return None  # 이미 최저 레벨

        conditions = self.DEMOTION_CONDITIONS.get(current_level)
        if not conditions:
            return None

        # 정확도 조건 확인
        accuracy = float(ruleset.accuracy_rate or 1.0)
        if accuracy < conditions["max_accuracy"]:
            logger.info(f"Demotion triggered: accuracy {accuracy} < {conditions['max_accuracy']}")
            return current_level - 1

        # 연속 부정 피드백 확인
        consecutive_negative = self._get_consecutive_negative_feedback(ruleset.ruleset_id)
        if consecutive_negative >= conditions["consecutive_negative"]:
            logger.info(f"Demotion triggered: consecutive negative {consecutive_negative} >= {conditions['consecutive_negative']}")
            return current_level - 1

        return None

    def _get_consecutive_negative_feedback(self, ruleset_id: UUID) -> int:
        """연속 부정 피드백 수 조회"""
        # 최근 피드백 조회 (최신순)
        feedbacks = self.db.query(FeedbackLog).filter(
            FeedbackLog.ruleset_id == ruleset_id,
        ).order_by(FeedbackLog.created_at.desc()).limit(20).all()

        consecutive = 0
        for fb in feedbacks:
            if fb.feedback_type == "negative":
                consecutive += 1
            else:
                break  # 긍정 피드백이 나오면 중단

        return consecutive

    def update_trust_level(
        self,
        ruleset_id: UUID,
        new_level: int,
        reason: str,
        triggered_by: str = "auto",
        user_id: Optional[UUID] = None,
    ) -> TrustLevelHistory:
        """Trust Level 업데이트 및 이력 기록

        Args:
            ruleset_id: 룰셋 ID
            new_level: 새 Trust Level (0-3)
            reason: 변경 사유
            triggered_by: 트리거 유형 (auto, manual, feedback, schedule)
            user_id: 수동 변경 시 사용자 ID

        Returns:
            생성된 TrustLevelHistory 레코드
        """
        ruleset = self.db.query(Ruleset).filter(Ruleset.ruleset_id == ruleset_id).first()
        if not ruleset:
            raise ValueError(f"Ruleset {ruleset_id} not found")

        if new_level < 0 or new_level > 3:
            raise ValueError(f"Invalid trust level: {new_level}")

        previous_level = ruleset.trust_level

        if previous_level == new_level:
            logger.debug(f"Trust level unchanged for {ruleset_id}: {new_level}")
            return None

        # 메트릭 스냅샷 생성
        metrics_snapshot = {
            "trust_score": float(ruleset.trust_score),
            "accuracy_rate": float(ruleset.accuracy_rate) if ruleset.accuracy_rate else None,
            "execution_count": ruleset.execution_count,
            "positive_feedback_count": ruleset.positive_feedback_count,
            "negative_feedback_count": ruleset.negative_feedback_count,
            "trust_score_components": ruleset.trust_score_components,
        }

        # 이력 기록
        history = TrustLevelHistory(
            ruleset_id=ruleset_id,
            previous_level=previous_level,
            new_level=new_level,
            reason=reason,
            triggered_by=triggered_by,
            metrics_snapshot=metrics_snapshot,
            created_by=user_id,
        )
        self.db.add(history)

        # 룰셋 업데이트
        ruleset.trust_level = new_level
        if new_level > previous_level:
            ruleset.last_promoted_at = datetime.utcnow()
        else:
            ruleset.last_demoted_at = datetime.utcnow()

        self.db.commit()

        logger.info(f"Trust level updated for {ruleset_id}: {previous_level} -> {new_level} ({reason})")

        return history

    def update_trust_score(self, ruleset_id: UUID) -> Decimal:
        """Trust Score 재계산 및 저장

        Returns:
            새로운 Trust Score
        """
        ruleset = self.db.query(Ruleset).filter(Ruleset.ruleset_id == ruleset_id).first()
        if not ruleset:
            raise ValueError(f"Ruleset {ruleset_id} not found")

        score, components = self.calculate_trust_score(ruleset_id)

        # 저장
        ruleset.trust_score = score
        ruleset.trust_score_components = {k: float(v) for k, v in components.items()}

        self.db.commit()

        logger.debug(f"Trust score updated for {ruleset_id}: {score}")

        return score

    def update_execution_metrics(
        self,
        ruleset_id: UUID,
        result: str,
    ) -> None:
        """실행 후 메트릭 업데이트

        판단 실행 후 호출하여 execution_count, accuracy_rate 등 업데이트
        """
        ruleset = self.db.query(Ruleset).filter(Ruleset.ruleset_id == ruleset_id).first()
        if not ruleset:
            return

        # 실행 카운트 증가
        ruleset.execution_count += 1
        ruleset.last_execution_at = datetime.utcnow()

        # 정확도 재계산 (피드백 기반)
        total_feedback = ruleset.positive_feedback_count + ruleset.negative_feedback_count
        if total_feedback > 0:
            ruleset.accuracy_rate = Decimal(ruleset.positive_feedback_count) / Decimal(total_feedback)

        self.db.commit()

    def update_feedback_metrics(
        self,
        ruleset_id: UUID,
        is_positive: bool,
    ) -> None:
        """피드백 후 메트릭 업데이트

        피드백 수신 후 호출하여 feedback_count, accuracy_rate 업데이트
        """
        ruleset = self.db.query(Ruleset).filter(Ruleset.ruleset_id == ruleset_id).first()
        if not ruleset:
            return

        if is_positive:
            ruleset.positive_feedback_count += 1
        else:
            ruleset.negative_feedback_count += 1

        # 정확도 재계산
        total_feedback = ruleset.positive_feedback_count + ruleset.negative_feedback_count
        if total_feedback > 0:
            ruleset.accuracy_rate = Decimal(ruleset.positive_feedback_count) / Decimal(total_feedback)

        self.db.commit()

    def get_trust_info(self, ruleset_id: UUID) -> Optional[Dict[str, Any]]:
        """룰셋의 Trust 정보 조회

        Returns:
            Trust 정보 딕셔너리 또는 None
        """
        ruleset = self.db.query(Ruleset).filter(Ruleset.ruleset_id == ruleset_id).first()
        if not ruleset:
            return None

        return {
            "ruleset_id": str(ruleset.ruleset_id),
            "name": ruleset.name,
            "trust_level": ruleset.trust_level,
            "trust_level_name": self._level_to_name(ruleset.trust_level),
            "trust_score": float(ruleset.trust_score),
            "trust_score_components": ruleset.trust_score_components,
            "execution_count": ruleset.execution_count,
            "positive_feedback_count": ruleset.positive_feedback_count,
            "negative_feedback_count": ruleset.negative_feedback_count,
            "accuracy_rate": float(ruleset.accuracy_rate) if ruleset.accuracy_rate else None,
            "last_execution_at": ruleset.last_execution_at.isoformat() if ruleset.last_execution_at else None,
            "last_promoted_at": ruleset.last_promoted_at.isoformat() if ruleset.last_promoted_at else None,
            "last_demoted_at": ruleset.last_demoted_at.isoformat() if ruleset.last_demoted_at else None,
            "created_at": ruleset.created_at.isoformat(),
        }

    def get_trust_history(
        self,
        ruleset_id: UUID,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Trust Level 변경 이력 조회"""
        history = self.db.query(TrustLevelHistory).filter(
            TrustLevelHistory.ruleset_id == ruleset_id,
        ).order_by(TrustLevelHistory.created_at.desc()).limit(limit).all()

        return [
            {
                "id": str(h.id),
                "previous_level": h.previous_level,
                "previous_level_name": self._level_to_name(h.previous_level),
                "new_level": h.new_level,
                "new_level_name": self._level_to_name(h.new_level),
                "reason": h.reason,
                "triggered_by": h.triggered_by,
                "metrics_snapshot": h.metrics_snapshot,
                "created_at": h.created_at.isoformat(),
                "created_by": str(h.created_by) if h.created_by else None,
            }
            for h in history
        ]

    @staticmethod
    def _level_to_name(level: int) -> str:
        """Trust Level을 이름으로 변환"""
        names = {
            0: "Proposed",
            1: "Alert Only",
            2: "Low Risk Auto",
            3: "Full Auto",
        }
        return names.get(level, "Unknown")

    def evaluate_and_update(self, ruleset_id: UUID) -> Optional[Dict[str, Any]]:
        """Trust Score 재계산, 승격/강등 평가 및 적용

        Returns:
            변경된 경우 변경 정보, 그렇지 않으면 None
        """
        # Trust Score 업데이트
        self.update_trust_score(ruleset_id)

        # 승격 평가
        new_level = self.evaluate_promotion(ruleset_id)
        if new_level is not None:
            history = self.update_trust_level(
                ruleset_id=ruleset_id,
                new_level=new_level,
                reason="Auto promotion: conditions met",
                triggered_by="auto",
            )
            return {
                "action": "promoted",
                "previous_level": history.previous_level,
                "new_level": history.new_level,
                "reason": history.reason,
            }

        # 강등 평가
        new_level = self.evaluate_demotion(ruleset_id)
        if new_level is not None:
            history = self.update_trust_level(
                ruleset_id=ruleset_id,
                new_level=new_level,
                reason="Auto demotion: conditions triggered",
                triggered_by="auto",
            )
            return {
                "action": "demoted",
                "previous_level": history.previous_level,
                "new_level": history.new_level,
                "reason": history.reason,
            }

        return None
