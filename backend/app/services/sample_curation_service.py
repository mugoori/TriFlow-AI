# -*- coding: utf-8 -*-
"""Sample Curation Service

피드백에서 학습 샘플을 추출하고 관리하는 서비스.

주요 기능:
- 피드백 → 샘플 자동 추출
- MD5 기반 중복 제거
- 품질 점수 계산 (confidence × rating × recency)
- 샘플 CRUD

LRN-FR-020 스펙 참조
"""
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Any
from uuid import UUID

from sqlalchemy import func, and_, desc
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.models import Sample, FeedbackLog, JudgmentExecution
from app.schemas.sample import (
    SampleCreate,
    SampleUpdate,
    SampleExtractRequest,
    SampleStats,
)

logger = logging.getLogger(__name__)


# 피드백 타입 → 샘플 카테고리 매핑
FEEDBACK_TYPE_TO_CATEGORY = {
    "threshold_exceeded": "threshold_adjustment",
    "threshold_not_exceeded": "threshold_adjustment",
    "field_error": "field_correction",
    "validation_failed": "validation_failure",
    "incorrect_result": "field_correction",
    "missing_data": "field_correction",
}


class SampleCurationService:
    """학습 샘플 큐레이션 서비스"""

    def __init__(self, db: Session):
        self.db = db

    # ============================================
    # 중복 제거
    # ============================================

    def compute_content_hash(
        self,
        input_data: dict[str, Any],
        expected_output: dict[str, Any],
    ) -> str:
        """콘텐츠 해시 계산 (MD5)

        입력과 기대 출력을 조합하여 중복 여부를 판단하는 해시 생성.
        정렬된 JSON으로 일관된 해시 보장.
        """
        combined = {
            "input": input_data,
            "output": expected_output,
        }
        json_str = json.dumps(combined, sort_keys=True, default=str)
        return hashlib.md5(json_str.encode()).hexdigest()

    def is_duplicate(self, tenant_id: UUID, content_hash: str) -> bool:
        """중복 샘플 여부 확인"""
        exists = self.db.query(Sample.sample_id).filter(
            and_(
                Sample.tenant_id == tenant_id,
                Sample.content_hash == content_hash,
            )
        ).first()
        return exists is not None

    # ============================================
    # 품질 점수 계산
    # ============================================

    def calculate_quality_score(
        self,
        feedback: FeedbackLog,
        execution: Optional[JudgmentExecution] = None,
    ) -> float:
        """품질 점수 계산

        Quality = (rating/5) × confidence × recency_factor

        Args:
            feedback: 피드백 로그
            execution: 연결된 판정 실행 (선택)

        Returns:
            품질 점수 (0.0 ~ 1.0)
        """
        # 1. 피드백 rating (1-5 → 0.2-1.0)
        rating = feedback.rating if feedback.rating else 3  # 기본값 3
        rating_score = rating / 5.0

        # 2. 실행 confidence (0.0-1.0)
        if execution and execution.confidence:
            confidence = float(execution.confidence)
        else:
            confidence = 0.7  # 기본값

        # 3. Recency factor (최신일수록 높음)
        # 30일 이상이면 0.5, 최신이면 1.0
        if feedback.created_at:
            days_old = (datetime.utcnow() - feedback.created_at).days
        else:
            days_old = 0
        recency_factor = max(0.5, 1.0 - days_old / 30)

        quality_score = rating_score * confidence * recency_factor
        return round(quality_score, 4)

    # ============================================
    # 샘플 추출
    # ============================================

    def extract_samples_from_feedback(
        self,
        tenant_id: UUID,
        request: SampleExtractRequest,
    ) -> tuple[list[Sample], int]:
        """피드백에서 샘플 자동 추출

        Args:
            tenant_id: 테넌트 ID
            request: 추출 요청 (days, min_confidence, categories, dry_run)

        Returns:
            (추출된 샘플 목록, 스킵된 중복 수)
        """
        # 기간 계산
        start_date = datetime.utcnow() - timedelta(days=request.days)

        # 피드백 조회 쿼리
        query = self.db.query(FeedbackLog).filter(
            and_(
                FeedbackLog.tenant_id == tenant_id,
                FeedbackLog.created_at >= start_date,
            )
        )

        # 카테고리 필터 (피드백 타입 기반)
        if request.categories:
            # 역매핑: 카테고리 → 피드백 타입들
            feedback_types = []
            for cat in request.categories:
                for fb_type, fb_cat in FEEDBACK_TYPE_TO_CATEGORY.items():
                    if fb_cat == cat:
                        feedback_types.append(fb_type)
            if feedback_types:
                query = query.filter(FeedbackLog.feedback_type.in_(feedback_types))

        feedbacks = query.order_by(desc(FeedbackLog.created_at)).all()

        extracted_samples = []
        skipped_duplicates = 0

        for feedback in feedbacks:
            sample = self._create_sample_from_feedback(
                feedback=feedback,
                min_confidence=request.min_confidence,
                dry_run=request.dry_run,
            )

            if sample is None:
                skipped_duplicates += 1
            elif sample:
                extracted_samples.append(sample)

        if not request.dry_run:
            self.db.commit()

        logger.info(
            f"Extracted {len(extracted_samples)} samples from {len(feedbacks)} feedbacks, "
            f"skipped {skipped_duplicates} duplicates"
        )

        return extracted_samples, skipped_duplicates

    def _create_sample_from_feedback(
        self,
        feedback: FeedbackLog,
        min_confidence: float = 0.5,
        dry_run: bool = False,
    ) -> Optional[Sample]:
        """단일 피드백에서 샘플 생성

        Returns:
            Sample: 생성된 샘플
            None: 중복이거나 품질 기준 미달
        """
        # 연결된 실행 조회
        execution = None
        if feedback.execution_id:
            execution = self.db.query(JudgmentExecution).filter(
                JudgmentExecution.execution_id == feedback.execution_id
            ).first()

        # 신뢰도 필터
        confidence = float(execution.confidence) if execution and execution.confidence else 0.7
        if confidence < min_confidence:
            return None

        # 카테고리 결정
        category = FEEDBACK_TYPE_TO_CATEGORY.get(
            feedback.feedback_type,
            "general"
        )

        # 입력/출력 데이터 구성
        input_data = self._build_input_data(feedback, execution)
        expected_output = self._build_expected_output(feedback, execution)

        # 콘텐츠 해시
        content_hash = self.compute_content_hash(input_data, expected_output)

        # 중복 체크
        if self.is_duplicate(feedback.tenant_id, content_hash):
            return None

        # 품질 점수 계산
        quality_score = self.calculate_quality_score(feedback, execution)

        # 샘플 생성
        sample = Sample(
            tenant_id=feedback.tenant_id,
            feedback_id=feedback.feedback_id,
            execution_id=feedback.execution_id,
            source_type="feedback",
            category=category,
            input_data=input_data,
            expected_output=expected_output,
            context=self._build_context(feedback, execution),
            quality_score=quality_score,
            confidence=confidence,
            content_hash=content_hash,
            status="pending",
        )

        if not dry_run:
            self.db.add(sample)

        return sample

    def _build_input_data(
        self,
        feedback: FeedbackLog,
        execution: Optional[JudgmentExecution],
    ) -> dict[str, Any]:
        """입력 데이터 구성"""
        input_data = {}

        # 실행 입력 데이터
        if execution and execution.input_data:
            input_data = dict(execution.input_data)

        # 피드백 컨텍스트 병합
        if feedback.context_data:
            input_data.update(feedback.context_data)

        return input_data

    def _build_expected_output(
        self,
        feedback: FeedbackLog,
        execution: Optional[JudgmentExecution],
    ) -> dict[str, Any]:
        """기대 출력 구성"""
        expected_output = {}

        # 피드백에 수정된 결과가 있으면 사용
        if feedback.corrected_result:
            expected_output = dict(feedback.corrected_result)

        # 없으면 원본 실행 결과에서 추론
        elif execution and execution.execution_result:
            # 피드백이 긍정적이면 실행 결과 그대로
            if feedback.rating and feedback.rating >= 4:
                expected_output = dict(execution.execution_result)

        return expected_output

    def _build_context(
        self,
        feedback: FeedbackLog,
        execution: Optional[JudgmentExecution],
    ) -> dict[str, Any]:
        """컨텍스트 데이터 구성"""
        context = {
            "feedback_type": feedback.feedback_type,
            "feedback_created_at": feedback.created_at.isoformat() if feedback.created_at else None,
        }

        if execution:
            context["execution_method"] = execution.method_used
            context["execution_trust_level"] = str(execution.trust_level) if execution.trust_level else None

        if feedback.comment:
            context["feedback_comment"] = feedback.comment

        return context

    # ============================================
    # CRUD
    # ============================================

    def create_sample(
        self,
        tenant_id: UUID,
        request: SampleCreate,
    ) -> Sample:
        """샘플 수동 생성"""
        # 콘텐츠 해시
        content_hash = self.compute_content_hash(
            request.input_data,
            request.expected_output,
        )

        # 중복 체크
        if self.is_duplicate(tenant_id, content_hash):
            raise ValueError("동일한 콘텐츠의 샘플이 이미 존재합니다")

        sample = Sample(
            tenant_id=tenant_id,
            feedback_id=request.feedback_id,
            execution_id=request.execution_id,
            source_type=request.source_type,
            category=request.category,
            input_data=request.input_data,
            expected_output=request.expected_output,
            context=request.context,
            quality_score=request.quality_score or 0.5,
            confidence=request.confidence or 0.5,
            content_hash=content_hash,
            status="pending",
        )

        self.db.add(sample)
        self.db.commit()
        self.db.refresh(sample)

        logger.info(f"Created sample: {sample.sample_id}")
        return sample

    def get_sample(self, sample_id: UUID) -> Optional[Sample]:
        """샘플 조회"""
        return self.db.query(Sample).filter(
            Sample.sample_id == sample_id
        ).first()

    def list_samples(
        self,
        tenant_id: UUID,
        category: Optional[str] = None,
        status: Optional[str] = None,
        source_type: Optional[str] = None,
        min_quality: Optional[float] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Sample], int]:
        """샘플 목록 조회"""
        query = self.db.query(Sample).filter(
            Sample.tenant_id == tenant_id
        )

        if category:
            query = query.filter(Sample.category == category)
        if status:
            query = query.filter(Sample.status == status)
        if source_type:
            query = query.filter(Sample.source_type == source_type)
        if min_quality is not None:
            query = query.filter(Sample.quality_score >= min_quality)

        # 총 개수
        total = query.count()

        # 페이지네이션
        samples = query.order_by(desc(Sample.created_at)).offset(
            (page - 1) * page_size
        ).limit(page_size).all()

        return samples, total

    def update_sample(
        self,
        sample_id: UUID,
        request: SampleUpdate,
    ) -> Sample:
        """샘플 수정"""
        sample = self.get_sample(sample_id)
        if not sample:
            raise ValueError("샘플을 찾을 수 없습니다")

        # 수정 가능 상태 체크
        if sample.status not in ("pending", "rejected"):
            raise ValueError("승인되거나 보관된 샘플은 수정할 수 없습니다")

        # 필드 업데이트
        update_data = request.model_dump(exclude_unset=True)

        # input_data나 expected_output이 변경되면 해시 재계산
        if "input_data" in update_data or "expected_output" in update_data:
            new_input = update_data.get("input_data", sample.input_data)
            new_output = update_data.get("expected_output", sample.expected_output)
            new_hash = self.compute_content_hash(new_input, new_output)

            # 새 해시가 다른 샘플과 중복되는지 확인
            if new_hash != sample.content_hash:
                if self.is_duplicate(sample.tenant_id, new_hash):
                    raise ValueError("수정된 콘텐츠가 기존 샘플과 중복됩니다")
                sample.content_hash = new_hash

        for key, value in update_data.items():
            setattr(sample, key, value)

        self.db.commit()
        self.db.refresh(sample)

        logger.info(f"Updated sample: {sample_id}")
        return sample

    def approve_sample(
        self,
        sample_id: UUID,
        approver_id: UUID,
    ) -> Sample:
        """샘플 승인"""
        sample = self.get_sample(sample_id)
        if not sample:
            raise ValueError("샘플을 찾을 수 없습니다")

        if sample.status != "pending":
            raise ValueError(f"대기 중 상태의 샘플만 승인할 수 있습니다 (현재: {sample.status})")

        sample.approve(approver_id)
        self.db.commit()
        self.db.refresh(sample)

        logger.info(f"Approved sample: {sample_id}")
        return sample

    def reject_sample(
        self,
        sample_id: UUID,
        reason: str,
    ) -> Sample:
        """샘플 거부"""
        sample = self.get_sample(sample_id)
        if not sample:
            raise ValueError("샘플을 찾을 수 없습니다")

        if sample.status not in ("pending", "approved"):
            raise ValueError(f"대기/승인 상태의 샘플만 거부할 수 있습니다 (현재: {sample.status})")

        sample.reject(reason)
        self.db.commit()
        self.db.refresh(sample)

        logger.info(f"Rejected sample: {sample_id}, reason: {reason}")
        return sample

    def archive_sample(self, sample_id: UUID) -> Sample:
        """샘플 보관"""
        sample = self.get_sample(sample_id)
        if not sample:
            raise ValueError("샘플을 찾을 수 없습니다")

        sample.archive()
        self.db.commit()
        self.db.refresh(sample)

        logger.info(f"Archived sample: {sample_id}")
        return sample

    def delete_sample(self, sample_id: UUID) -> bool:
        """샘플 삭제"""
        sample = self.get_sample(sample_id)
        if not sample:
            return False

        self.db.delete(sample)
        self.db.commit()

        logger.info(f"Deleted sample: {sample_id}")
        return True

    # ============================================
    # 통계
    # ============================================

    def get_sample_stats(self, tenant_id: UUID) -> SampleStats:
        """샘플 통계 조회"""
        # 전체 카운트
        total = self.db.query(func.count(Sample.sample_id)).filter(
            Sample.tenant_id == tenant_id
        ).scalar() or 0

        # 상태별 카운트
        status_counts = self.db.query(
            Sample.status,
            func.count(Sample.sample_id)
        ).filter(
            Sample.tenant_id == tenant_id
        ).group_by(Sample.status).all()

        status_dict = {s: c for s, c in status_counts}

        # 카테고리별 카운트
        category_counts = self.db.query(
            Sample.category,
            func.count(Sample.sample_id)
        ).filter(
            Sample.tenant_id == tenant_id
        ).group_by(Sample.category).all()

        # 소스 타입별 카운트
        source_counts = self.db.query(
            Sample.source_type,
            func.count(Sample.sample_id)
        ).filter(
            Sample.tenant_id == tenant_id
        ).group_by(Sample.source_type).all()

        # 품질 점수 통계
        quality_stats = self.db.query(
            func.avg(Sample.quality_score),
            func.min(Sample.quality_score),
            func.max(Sample.quality_score),
        ).filter(
            Sample.tenant_id == tenant_id
        ).first()

        return SampleStats(
            total_count=total,
            pending_count=status_dict.get("pending", 0),
            approved_count=status_dict.get("approved", 0),
            rejected_count=status_dict.get("rejected", 0),
            archived_count=status_dict.get("archived", 0),
            by_category={c: cnt for c, cnt in category_counts},
            by_source_type={s: cnt for s, cnt in source_counts},
            avg_quality_score=float(quality_stats[0]) if quality_stats[0] else 0.0,
            min_quality_score=float(quality_stats[1]) if quality_stats[1] else 0.0,
            max_quality_score=float(quality_stats[2]) if quality_stats[2] else 0.0,
        )
