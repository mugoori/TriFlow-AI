# -*- coding: utf-8 -*-
"""
Prompt Metrics Aggregator
LlmCall 로그에서 프롬프트 성능 메트릭 집계
"""
import logging
from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.models import PromptTemplate, LlmCall
from app.services.prompt_service import PromptService

logger = logging.getLogger(__name__)


class PromptMetricsAggregator:
    """프롬프트 성능 메트릭 집계 서비스"""

    def __init__(self, db: Session):
        self.db = db
        self.prompt_service = PromptService(db)

    def update_prompt_metrics(
        self,
        template_id: UUID,
        time_window_hours: int = 24,
    ) -> Dict[str, Any]:
        """
        LlmCall 테이블에서 프롬프트 메트릭 집계

        Args:
            template_id: 프롬프트 템플릿 ID
            time_window_hours: 집계 기간 (시간)

        Returns:
            집계된 메트릭 딕셔너리
        """
        # Calculate time window
        since = datetime.utcnow() - timedelta(hours=time_window_hours)

        # Query LlmCall records for this template
        # Note: LlmCall 모델에 prompt_template_id 컬럼이 추가되어야 함
        # 현재는 call_type으로 매칭 (임시)
        template = self.db.query(PromptTemplate).get(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        # Query LlmCalls by prompt_template_id (직접 FK 사용)
        query = (
            self.db.query(
                func.avg(LlmCall.prompt_tokens + LlmCall.completion_tokens).label(
                    "avg_tokens"
                ),
                func.avg(LlmCall.latency_ms).label("avg_latency"),
                func.count(LlmCall.call_id).label("total_calls"),
                func.sum(
                    func.cast(LlmCall.success == True, Integer)
                ).label("successful_calls"),
                func.sum(
                    func.cast(LlmCall.validation_error == True, Integer)
                ).label("validation_errors"),
            )
            .filter(
                and_(
                    LlmCall.tenant_id == template.tenant_id,
                    LlmCall.prompt_template_id == template_id,
                    LlmCall.created_at >= since,
                )
            )
        )

        result = query.one()

        # Calculate metrics
        total_calls = result.total_calls or 0

        if total_calls == 0:
            logger.warning(
                f"No LlmCall records found for template {template.name} "
                f"in last {time_window_hours}h"
            )
            return {
                "avg_tokens_per_call": None,
                "avg_latency_ms": None,
                "success_rate": None,
                "validation_error_rate": None,
                "total_calls": 0,
            }

        avg_tokens = int(result.avg_tokens) if result.avg_tokens else None
        avg_latency = int(result.avg_latency) if result.avg_latency else None
        success_rate = (result.successful_calls / total_calls) if total_calls else 0
        validation_error_rate = (
            (result.validation_errors / total_calls) if total_calls else 0
        )

        # Update template metrics
        self.prompt_service.update_prompt_metrics(
            template_id=template_id,
            avg_tokens=avg_tokens or 0,
            avg_latency_ms=avg_latency or 0,
            success_rate=success_rate,
            validation_error_rate=validation_error_rate,
        )

        metrics = {
            "avg_tokens_per_call": avg_tokens,
            "avg_latency_ms": avg_latency,
            "success_rate": success_rate,
            "validation_error_rate": validation_error_rate,
            "total_calls": total_calls,
            "time_window_hours": time_window_hours,
        }

        logger.info(
            f"Updated metrics for {template.name} v{template.version}: "
            f"{total_calls} calls, {success_rate:.2%} success rate"
        )

        return metrics

    def update_all_active_prompts(self, time_window_hours: int = 24) -> int:
        """
        모든 활성 프롬프트의 메트릭 업데이트

        Args:
            time_window_hours: 집계 기간

        Returns:
            업데이트된 템플릿 수
        """
        active_templates = (
            self.db.query(PromptTemplate)
            .filter(PromptTemplate.is_active == True)
            .all()
        )

        updated_count = 0

        for template in active_templates:
            try:
                self.update_prompt_metrics(template.template_id, time_window_hours)
                updated_count += 1
            except Exception as e:
                logger.error(
                    f"Failed to update metrics for {template.name}: {e}",
                    exc_info=True,
                )

        logger.info(f"Updated metrics for {updated_count} active prompts")
        return updated_count

    def get_performance_summary(
        self, template_id: UUID
    ) -> Dict[str, Any]:
        """
        프롬프트 성능 요약 조회

        Args:
            template_id: 템플릿 ID

        Returns:
            성능 요약 딕셔너리
        """
        template = self.db.query(PromptTemplate).get(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        return {
            "template_id": template.template_id,
            "name": template.name,
            "version": template.version,
            "is_active": template.is_active,
            "metrics": {
                "avg_tokens_per_call": template.avg_tokens_per_call,
                "avg_latency_ms": template.avg_latency_ms,
                "success_rate": (
                    float(template.success_rate) if template.success_rate else None
                ),
                "validation_error_rate": (
                    float(template.validation_error_rate)
                    if template.validation_error_rate
                    else None
                ),
                "last_update": (
                    template.last_performance_update.isoformat()
                    if template.last_performance_update
                    else None
                ),
            },
            "model_config": template.model_config,
        }


# Import fix for Integer type
from sqlalchemy import Integer
