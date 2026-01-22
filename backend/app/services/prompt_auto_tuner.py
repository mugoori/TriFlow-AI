"""
Prompt Auto-Tuner
긍정 피드백 샘플을 Few-shot 예시로 자동 추가
"""
import logging
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.models import (
    PromptTemplate,
    PromptTemplateBody,
    FeedbackLog,
    LlmCall,
)

logger = logging.getLogger(__name__)


class PromptAutoTuner:
    """프롬프트 자동 튜닝 서비스"""

    def __init__(self, db: Session):
        self.db = db

    def auto_add_few_shots(
        self,
        template_id: UUID,
        max_examples: int = 5,
        min_rating: float = 4.0,
        time_window_days: int = 30,
        locale: str = "ko-KR",
    ) -> Dict[str, Any]:
        """
        긍정 피드백 샘플을 Few-shot 예시로 자동 추가

        Args:
            template_id: 프롬프트 템플릿 ID
            max_examples: 최대 Few-shot 개수
            min_rating: 최소 평점 (1.0 - 5.0)
            time_window_days: 샘플 수집 기간 (일)
            locale: 언어 (ko-KR, en-US)

        Returns:
            {
                "added_count": int,
                "examples": List[dict],
                "template_id": UUID,
            }
        """
        # 1. 템플릿 조회
        template = self.db.query(PromptTemplate).get(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        # 2. 긍정 피드백 조회 (FeedbackLog 사용)
        since = datetime.utcnow() - timedelta(days=time_window_days)

        positive_feedbacks = (
            self.db.query(FeedbackLog)
            .filter(
                and_(
                    FeedbackLog.tenant_id == template.tenant_id,
                    FeedbackLog.feedback_type.in_(["positive", "correct", "helpful"]),
                    FeedbackLog.rating >= min_rating,
                    FeedbackLog.created_at >= since,
                )
            )
            .order_by(desc(FeedbackLog.rating), desc(FeedbackLog.created_at))
            .limit(max_examples)
            .all()
        )

        if not positive_feedbacks:
            logger.warning(
                f"No positive feedbacks found for template {template.name} "
                f"in last {time_window_days} days"
            )
            return {
                "added_count": 0,
                "examples": [],
                "template_id": str(template_id),
            }

        # 3. Few-shot 예시 생성
        few_shot_examples = []
        for feedback in positive_feedbacks:
            # FeedbackLog에서 original_output과 corrected_output 사용
            example = {
                "input": feedback.context_data.get("input") if feedback.context_data else {},
                "output": feedback.corrected_output or feedback.original_output or {},
                "rating": float(feedback.rating) if feedback.rating else 5.0,
                "created_at": feedback.created_at.isoformat() if feedback.created_at else None,
            }
            few_shot_examples.append(example)

        # 4. PromptTemplateBody 업데이트
        template_body = (
            self.db.query(PromptTemplateBody)
            .filter(
                and_(
                    PromptTemplateBody.template_id == template_id,
                    PromptTemplateBody.locale == locale,
                )
            )
            .first()
        )

        if not template_body:
            logger.warning(
                f"PromptTemplateBody not found for template {template.name}, locale {locale}"
            )
            return {
                "added_count": 0,
                "examples": [],
                "template_id": str(template_id),
            }

        # 기존 few_shot_examples와 병합 (중복 제거)
        existing_examples = template_body.few_shot_examples or []

        # 새로운 예시만 추가 (중복 방지)
        added_count = 0
        for new_example in few_shot_examples:
            # 중복 체크 (input이 동일한 경우)
            is_duplicate = any(
                ex.get("input") == new_example["input"] for ex in existing_examples
            )
            if not is_duplicate:
                existing_examples.append(new_example)
                added_count += 1

        # 최대 개수 제한
        if len(existing_examples) > max_examples:
            # 평점 높은 순으로 정렬하여 상위만 유지
            existing_examples.sort(key=lambda x: x.get("rating", 0), reverse=True)
            existing_examples = existing_examples[:max_examples]

        # DB 업데이트
        template_body.few_shot_examples = existing_examples
        self.db.commit()

        logger.info(
            f"Added {added_count} few-shot examples to {template.name} "
            f"(total: {len(existing_examples)})"
        )

        return {
            "added_count": added_count,
            "examples": few_shot_examples,
            "template_id": str(template_id),
            "total_examples": len(existing_examples),
        }

    def auto_tune_all_templates(
        self,
        max_examples: int = 5,
        min_rating: float = 4.0,
        time_window_days: int = 30,
    ) -> Dict[str, Any]:
        """
        모든 활성 템플릿에 Few-shot 자동 추가

        Args:
            max_examples: 최대 Few-shot 개수
            min_rating: 최소 평점
            time_window_days: 샘플 수집 기간

        Returns:
            {
                "tuned_count": int,
                "total_templates": int,
                "total_examples_added": int,
            }
        """
        active_templates = (
            self.db.query(PromptTemplate)
            .filter(PromptTemplate.is_active == True)
            .all()
        )

        tuned_count = 0
        total_examples_added = 0

        for template in active_templates:
            try:
                result = self.auto_add_few_shots(
                    template_id=template.template_id,
                    max_examples=max_examples,
                    min_rating=min_rating,
                    time_window_days=time_window_days,
                )

                if result["added_count"] > 0:
                    tuned_count += 1
                    total_examples_added += result["added_count"]

            except Exception as e:
                logger.error(
                    f"Failed to auto-tune template {template.name}: {e}",
                    exc_info=True,
                )

        logger.info(
            f"Auto-tuned {tuned_count} templates, "
            f"added {total_examples_added} examples total"
        )

        return {
            "tuned_count": tuned_count,
            "total_templates": len(active_templates),
            "total_examples_added": total_examples_added,
        }

    def get_tuning_candidates(
        self,
        template_id: UUID,
        min_rating: float = 4.0,
        time_window_days: int = 30,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Few-shot 후보 샘플 조회

        Args:
            template_id: 프롬프트 템플릿 ID
            min_rating: 최소 평점
            time_window_days: 샘플 수집 기간
            limit: 최대 개수

        Returns:
            후보 샘플 리스트
        """
        template = self.db.query(PromptTemplate).get(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        since = datetime.utcnow() - timedelta(days=time_window_days)

        feedbacks = (
            self.db.query(FeedbackLog)
            .filter(
                and_(
                    FeedbackLog.tenant_id == template.tenant_id,
                    FeedbackLog.feedback_type.in_(["positive", "correct", "helpful"]),
                    FeedbackLog.rating >= min_rating,
                    FeedbackLog.created_at >= since,
                )
            )
            .order_by(desc(FeedbackLog.rating), desc(FeedbackLog.created_at))
            .limit(limit)
            .all()
        )

        return [
            {
                "feedback_id": str(feedback.feedback_id),
                "input": feedback.context_data.get("input") if feedback.context_data else {},
                "output": feedback.corrected_output or feedback.original_output or {},
                "rating": float(feedback.rating) if feedback.rating else None,
                "created_at": feedback.created_at.isoformat() if feedback.created_at else None,
            }
            for feedback in feedbacks
        ]


def get_prompt_auto_tuner(db: Session) -> PromptAutoTuner:
    """
    Prompt Auto-Tuner 인스턴스 반환

    Args:
        db: 데이터베이스 세션

    Returns:
        PromptAutoTuner 인스턴스
    """
    return PromptAutoTuner(db)
