# -*- coding: utf-8 -*-
"""
Prompt Service
프롬프트 템플릿 관리 및 버전 제어
"""
import logging
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.models import PromptTemplate, PromptTemplateBody

logger = logging.getLogger(__name__)


class PromptService:
    """프롬프트 템플릿 관리 서비스"""

    def __init__(self, db: Session):
        self.db = db

    def create_prompt_version(
        self,
        tenant_id: UUID,
        name: str,
        purpose: str,
        template_type: str,
        model_config: Dict[str, Any],
        variables: Dict[str, Any],
        system_prompt: str,
        user_prompt_template: str,
        locale: str = "ko-KR",
        few_shot_examples: Optional[List[Dict]] = None,
        created_by: Optional[UUID] = None,
    ) -> PromptTemplate:
        """
        새 프롬프트 템플릿 버전 생성

        Args:
            tenant_id: 테넌트 ID
            name: 템플릿 이름 (예: "LearningAgent", "JudgmentAgent")
            purpose: 템플릿 용도 설명
            template_type: judgment, chat, reasoning, extraction
            model_config: {model, temperature, max_tokens}
            variables: {required: [], optional: [], defaults: {}}
            system_prompt: 시스템 프롬프트
            user_prompt_template: 사용자 프롬프트 템플릿
            locale: 로케일 (기본: ko-KR)
            few_shot_examples: Few-shot 예제 리스트
            created_by: 생성자 user_id

        Returns:
            생성된 PromptTemplate
        """
        # Get next version number
        max_version = (
            self.db.query(PromptTemplate.version)
            .filter(
                and_(
                    PromptTemplate.tenant_id == tenant_id,
                    PromptTemplate.name == name,
                )
            )
            .order_by(desc(PromptTemplate.version))
            .first()
        )
        next_version = (max_version[0] + 1) if max_version else 1

        # Create template
        template = PromptTemplate(
            tenant_id=tenant_id,
            name=name,
            purpose=purpose,
            version=next_version,
            template_type=template_type,
            model_config=model_config,
            variables=variables,
            is_active=False,  # Not active by default
            created_by=created_by,
        )

        self.db.add(template)
        self.db.flush()  # Get template_id

        # Create template body
        body = PromptTemplateBody(
            template_id=template.template_id,
            locale=locale,
            system_prompt=system_prompt,
            user_prompt_template=user_prompt_template,
            few_shot_examples=few_shot_examples or [],
        )

        self.db.add(body)
        self.db.commit()
        self.db.refresh(template)

        logger.info(
            f"Created prompt template: {name} v{next_version} "
            f"(template_id={template.template_id})"
        )

        return template

    def get_active_prompt(
        self,
        tenant_id: UUID,
        name: str,
        locale: str = "ko-KR",
    ) -> Optional[PromptTemplateBody]:
        """
        활성화된 프롬프트 조회

        Args:
            tenant_id: 테넌트 ID
            name: 템플릿 이름
            locale: 로케일

        Returns:
            활성 PromptTemplateBody 또는 None
        """
        template = (
            self.db.query(PromptTemplate)
            .filter(
                and_(
                    PromptTemplate.tenant_id == tenant_id,
                    PromptTemplate.name == name,
                    PromptTemplate.is_active == True,
                )
            )
            .first()
        )

        if not template:
            return None

        # Get template body for locale
        body = (
            self.db.query(PromptTemplateBody)
            .filter(
                and_(
                    PromptTemplateBody.template_id == template.template_id,
                    PromptTemplateBody.locale == locale,
                )
            )
            .first()
        )

        return body

    def activate_prompt_version(
        self,
        template_id: UUID,
        deactivate_others: bool = True,
    ) -> PromptTemplate:
        """
        프롬프트 버전 활성화

        Args:
            template_id: 활성화할 템플릿 ID
            deactivate_others: 같은 이름의 다른 버전 비활성화 여부

        Returns:
            활성화된 PromptTemplate
        """
        template = self.db.query(PromptTemplate).get(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        if deactivate_others:
            # Deactivate other versions with same name
            self.db.query(PromptTemplate).filter(
                and_(
                    PromptTemplate.tenant_id == template.tenant_id,
                    PromptTemplate.name == template.name,
                    PromptTemplate.template_id != template_id,
                )
            ).update({"is_active": False})

        # Activate this version
        template.is_active = True
        template.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(template)

        logger.info(
            f"Activated prompt template: {template.name} v{template.version} "
            f"(template_id={template_id})"
        )

        return template

    def deactivate_prompt_version(self, template_id: UUID) -> PromptTemplate:
        """프롬프트 버전 비활성화"""
        template = self.db.query(PromptTemplate).get(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        template.is_active = False
        template.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(template)

        logger.info(f"Deactivated prompt template: {template.name} v{template.version}")

        return template

    def list_prompt_versions(
        self,
        tenant_id: UUID,
        name: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> List[PromptTemplate]:
        """
        프롬프트 템플릿 목록 조회

        Args:
            tenant_id: 테넌트 ID
            name: 템플릿 이름 필터 (선택)
            is_active: 활성 상태 필터 (선택)

        Returns:
            PromptTemplate 리스트
        """
        query = self.db.query(PromptTemplate).filter(
            PromptTemplate.tenant_id == tenant_id
        )

        if name:
            query = query.filter(PromptTemplate.name == name)

        if is_active is not None:
            query = query.filter(PromptTemplate.is_active == is_active)

        return query.order_by(
            desc(PromptTemplate.name), desc(PromptTemplate.version)
        ).all()

    def compare_prompt_versions(
        self,
        template_id_1: UUID,
        template_id_2: UUID,
    ) -> Dict[str, Any]:
        """
        두 프롬프트 버전 성능 비교

        Args:
            template_id_1: 첫 번째 템플릿 ID
            template_id_2: 두 번째 템플릿 ID

        Returns:
            비교 결과 딕셔너리
        """
        t1 = self.db.query(PromptTemplate).get(template_id_1)
        t2 = self.db.query(PromptTemplate).get(template_id_2)

        if not t1 or not t2:
            raise ValueError("One or both templates not found")

        def calc_delta(v1, v2):
            if v1 is None or v2 is None:
                return None
            return ((v2 - v1) / v1 * 100) if v1 != 0 else 0

        return {
            "template_1": {
                "id": t1.template_id,
                "name": t1.name,
                "version": t1.version,
                "avg_tokens": t1.avg_tokens_per_call,
                "avg_latency_ms": t1.avg_latency_ms,
                "success_rate": float(t1.success_rate) if t1.success_rate else None,
            },
            "template_2": {
                "id": t2.template_id,
                "name": t2.name,
                "version": t2.version,
                "avg_tokens": t2.avg_tokens_per_call,
                "avg_latency_ms": t2.avg_latency_ms,
                "success_rate": float(t2.success_rate) if t2.success_rate else None,
            },
            "delta": {
                "tokens_pct": calc_delta(t1.avg_tokens_per_call, t2.avg_tokens_per_call),
                "latency_pct": calc_delta(t1.avg_latency_ms, t2.avg_latency_ms),
                "success_rate_delta": (
                    float(t2.success_rate - t1.success_rate)
                    if t1.success_rate and t2.success_rate
                    else None
                ),
            },
        }

    def update_prompt_metrics(
        self,
        template_id: UUID,
        avg_tokens: int,
        avg_latency_ms: int,
        success_rate: float,
        validation_error_rate: float,
    ) -> PromptTemplate:
        """
        프롬프트 성능 메트릭 업데이트

        Args:
            template_id: 템플릿 ID
            avg_tokens: 평균 토큰 수
            avg_latency_ms: 평균 레이턴시 (밀리초)
            success_rate: 성공률 (0-1)
            validation_error_rate: 검증 에러율 (0-1)

        Returns:
            업데이트된 PromptTemplate
        """
        template = self.db.query(PromptTemplate).get(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        template.avg_tokens_per_call = avg_tokens
        template.avg_latency_ms = avg_latency_ms
        template.success_rate = success_rate
        template.validation_error_rate = validation_error_rate
        template.last_performance_update = datetime.utcnow()

        self.db.commit()
        self.db.refresh(template)

        logger.info(
            f"Updated metrics for {template.name} v{template.version}: "
            f"tokens={avg_tokens}, latency={avg_latency_ms}ms, success={success_rate:.2%}"
        )

        return template
