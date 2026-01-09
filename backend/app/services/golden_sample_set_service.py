# -*- coding: utf-8 -*-
"""Golden Sample Set Service

골든 샘플셋 관리 서비스.

주요 기능:
- 골든 샘플셋 CRUD
- 샘플 추가/제거
- 자동 업데이트 (품질 기준 충족 샘플 자동 추가)
- 샘플셋 내보내기 (JSON/CSV)

LRN-FR-020 스펙 참조
"""
import csv
import io
import json
import logging
from datetime import datetime
from typing import Optional, Any
from uuid import UUID

from sqlalchemy import func, and_, desc
from sqlalchemy.orm import Session, joinedload

from app.models import Sample, GoldenSampleSet, GoldenSampleSetMember
from app.schemas.sample import (
    GoldenSetCreate,
    GoldenSetUpdate,
    GoldenSetAutoUpdateRequest,
    ExportFormat,
)

logger = logging.getLogger(__name__)


class GoldenSampleSetService:
    """골든 샘플셋 관리 서비스"""

    def __init__(self, db: Session):
        self.db = db

    # ============================================
    # CRUD
    # ============================================

    def create_set(
        self,
        tenant_id: UUID,
        request: GoldenSetCreate,
        created_by: Optional[UUID] = None,
    ) -> GoldenSampleSet:
        """골든 샘플셋 생성"""
        sample_set = GoldenSampleSet(
            tenant_id=tenant_id,
            name=request.name,
            description=request.description,
            category=request.category,
            min_quality_score=request.min_quality_score,
            max_samples=request.max_samples,
            auto_update=request.auto_update,
            config=request.config,
            created_by=created_by,
        )

        self.db.add(sample_set)
        self.db.commit()
        self.db.refresh(sample_set)

        logger.info(f"Created golden sample set: {sample_set.set_id}")
        return sample_set

    def get_set(self, set_id: UUID) -> Optional[GoldenSampleSet]:
        """골든 샘플셋 조회"""
        return self.db.query(GoldenSampleSet).filter(
            GoldenSampleSet.set_id == set_id
        ).first()

    def list_sets(
        self,
        tenant_id: UUID,
        is_active: Optional[bool] = None,
        category: Optional[str] = None,
    ) -> list[GoldenSampleSet]:
        """골든 샘플셋 목록 조회"""
        query = self.db.query(GoldenSampleSet).filter(
            GoldenSampleSet.tenant_id == tenant_id
        )

        if is_active is not None:
            query = query.filter(GoldenSampleSet.is_active == is_active)
        if category:
            query = query.filter(GoldenSampleSet.category == category)

        return query.order_by(desc(GoldenSampleSet.created_at)).all()

    def update_set(
        self,
        set_id: UUID,
        request: GoldenSetUpdate,
    ) -> GoldenSampleSet:
        """골든 샘플셋 수정"""
        sample_set = self.get_set(set_id)
        if not sample_set:
            raise ValueError("골든 샘플셋을 찾을 수 없습니다")

        update_data = request.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(sample_set, key, value)

        self.db.commit()
        self.db.refresh(sample_set)

        logger.info(f"Updated golden sample set: {set_id}")
        return sample_set

    def delete_set(self, set_id: UUID) -> bool:
        """골든 샘플셋 삭제"""
        sample_set = self.get_set(set_id)
        if not sample_set:
            return False

        self.db.delete(sample_set)
        self.db.commit()

        logger.info(f"Deleted golden sample set: {set_id}")
        return True

    # ============================================
    # 멤버 관리
    # ============================================

    def add_sample(
        self,
        set_id: UUID,
        sample_id: UUID,
        added_by: Optional[UUID] = None,
    ) -> bool:
        """샘플 추가"""
        sample_set = self.get_set(set_id)
        if not sample_set:
            raise ValueError("골든 샘플셋을 찾을 수 없습니다")

        # 샘플 존재 확인
        sample = self.db.query(Sample).filter(
            and_(
                Sample.sample_id == sample_id,
                Sample.tenant_id == sample_set.tenant_id,
            )
        ).first()
        if not sample:
            raise ValueError("샘플을 찾을 수 없습니다")

        # 샘플 상태 확인 (승인된 샘플만 추가 가능)
        if sample.status != "approved":
            raise ValueError("승인된 샘플만 골든 샘플셋에 추가할 수 있습니다")

        # 최대 샘플 수 확인
        if sample_set.is_full:
            raise ValueError(f"최대 샘플 수({sample_set.max_samples})에 도달했습니다")

        # 이미 추가되어 있는지 확인
        exists = self.db.query(GoldenSampleSetMember).filter(
            and_(
                GoldenSampleSetMember.set_id == set_id,
                GoldenSampleSetMember.sample_id == sample_id,
            )
        ).first()
        if exists:
            return False  # 이미 있음

        # 카테고리 필터 확인
        if sample_set.category and sample.category != sample_set.category:
            raise ValueError(
                f"이 샘플셋은 '{sample_set.category}' 카테고리만 허용합니다"
            )

        member = GoldenSampleSetMember(
            set_id=set_id,
            sample_id=sample_id,
            added_by=added_by,
        )
        self.db.add(member)
        self.db.commit()

        logger.info(f"Added sample {sample_id} to golden set {set_id}")
        return True

    def remove_sample(
        self,
        set_id: UUID,
        sample_id: UUID,
    ) -> bool:
        """샘플 제거"""
        member = self.db.query(GoldenSampleSetMember).filter(
            and_(
                GoldenSampleSetMember.set_id == set_id,
                GoldenSampleSetMember.sample_id == sample_id,
            )
        ).first()

        if not member:
            return False

        self.db.delete(member)
        self.db.commit()

        logger.info(f"Removed sample {sample_id} from golden set {set_id}")
        return True

    def get_samples(
        self,
        set_id: UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Sample], int]:
        """샘플셋 샘플 목록 조회"""
        # 총 개수
        total = self.db.query(func.count(GoldenSampleSetMember.sample_id)).filter(
            GoldenSampleSetMember.set_id == set_id
        ).scalar() or 0

        # 샘플 조회 (조인)
        samples = self.db.query(Sample).join(
            GoldenSampleSetMember,
            Sample.sample_id == GoldenSampleSetMember.sample_id
        ).filter(
            GoldenSampleSetMember.set_id == set_id
        ).order_by(
            desc(GoldenSampleSetMember.added_at)
        ).offset((page - 1) * page_size).limit(page_size).all()

        return samples, total

    # ============================================
    # 자동 업데이트
    # ============================================

    def auto_update_set(
        self,
        set_id: UUID,
        request: Optional[GoldenSetAutoUpdateRequest] = None,
    ) -> dict[str, int]:
        """품질 기준 충족 샘플 자동 추가

        Returns:
            {"added_count": N, "removed_count": N, "current_sample_count": N}
        """
        sample_set = self.get_set(set_id)
        if not sample_set:
            raise ValueError("골든 샘플셋을 찾을 수 없습니다")

        force = request.force if request else False

        added_count = 0
        removed_count = 0

        # 1. 기존 멤버 중 품질 기준 미달 샘플 제거
        if not force:
            low_quality_members = self.db.query(GoldenSampleSetMember).join(
                Sample,
                GoldenSampleSetMember.sample_id == Sample.sample_id
            ).filter(
                and_(
                    GoldenSampleSetMember.set_id == set_id,
                    Sample.quality_score < sample_set.min_quality_score,
                )
            ).all()

            for member in low_quality_members:
                self.db.delete(member)
                removed_count += 1

        # 2. 품질 기준 충족 & 미포함 샘플 추가
        # 현재 멤버 수
        current_count = self.db.query(func.count(GoldenSampleSetMember.sample_id)).filter(
            GoldenSampleSetMember.set_id == set_id
        ).scalar() or 0

        available_slots = sample_set.max_samples - current_count
        if force:
            available_slots = 999999  # force 모드면 무제한

        if available_slots > 0:
            # 이미 포함된 샘플 ID 목록
            existing_ids = self.db.query(GoldenSampleSetMember.sample_id).filter(
                GoldenSampleSetMember.set_id == set_id
            ).all()
            existing_ids = {row[0] for row in existing_ids}

            # 후보 샘플 조회 (품질 점수 내림차순)
            query = self.db.query(Sample).filter(
                and_(
                    Sample.tenant_id == sample_set.tenant_id,
                    Sample.status == "approved",
                    Sample.quality_score >= sample_set.min_quality_score,
                )
            )

            # 카테고리 필터
            if sample_set.category:
                query = query.filter(Sample.category == sample_set.category)

            candidates = query.order_by(
                desc(Sample.quality_score)
            ).limit(available_slots + len(existing_ids)).all()

            for sample in candidates:
                if sample.sample_id in existing_ids:
                    continue
                if added_count >= available_slots:
                    break

                member = GoldenSampleSetMember(
                    set_id=set_id,
                    sample_id=sample.sample_id,
                )
                self.db.add(member)
                added_count += 1

        self.db.commit()

        # 최종 카운트
        final_count = self.db.query(func.count(GoldenSampleSetMember.sample_id)).filter(
            GoldenSampleSetMember.set_id == set_id
        ).scalar() or 0

        logger.info(
            f"Auto-updated golden set {set_id}: "
            f"added={added_count}, removed={removed_count}, total={final_count}"
        )

        return {
            "added_count": added_count,
            "removed_count": removed_count,
            "current_sample_count": final_count,
        }

    # ============================================
    # 내보내기
    # ============================================

    def export_set(
        self,
        set_id: UUID,
        format: ExportFormat = "json",
        include_metadata: bool = True,
    ) -> tuple[bytes, int]:
        """샘플셋 내보내기

        Returns:
            (파일 데이터, 샘플 수)
        """
        sample_set = self.get_set(set_id)
        if not sample_set:
            raise ValueError("골든 샘플셋을 찾을 수 없습니다")

        # 모든 샘플 조회
        samples = self.db.query(Sample).join(
            GoldenSampleSetMember,
            Sample.sample_id == GoldenSampleSetMember.sample_id
        ).filter(
            GoldenSampleSetMember.set_id == set_id
        ).order_by(desc(Sample.quality_score)).all()

        if format == "json":
            data = self._export_to_json(sample_set, samples, include_metadata)
        elif format == "csv":
            data = self._export_to_csv(samples, include_metadata)
        else:
            raise ValueError(f"지원하지 않는 형식: {format}")

        return data, len(samples)

    def _export_to_json(
        self,
        sample_set: GoldenSampleSet,
        samples: list[Sample],
        include_metadata: bool,
    ) -> bytes:
        """JSON 형식으로 내보내기"""
        export_data = {
            "samples": [],
        }

        if include_metadata:
            export_data["metadata"] = {
                "set_id": str(sample_set.set_id),
                "name": sample_set.name,
                "description": sample_set.description,
                "category": sample_set.category,
                "sample_count": len(samples),
                "exported_at": datetime.utcnow().isoformat(),
            }

        for sample in samples:
            sample_data = {
                "input": sample.input_data,
                "expected_output": sample.expected_output,
            }

            if include_metadata:
                sample_data["metadata"] = {
                    "sample_id": str(sample.sample_id),
                    "category": sample.category,
                    "quality_score": float(sample.quality_score) if sample.quality_score else 0,
                    "confidence": float(sample.confidence) if sample.confidence else 0,
                    "source_type": sample.source_type,
                    "context": sample.context,
                }

            export_data["samples"].append(sample_data)

        return json.dumps(export_data, indent=2, ensure_ascii=False).encode("utf-8")

    def _export_to_csv(
        self,
        samples: list[Sample],
        include_metadata: bool,
    ) -> bytes:
        """CSV 형식으로 내보내기"""
        output = io.StringIO()

        # 헤더 결정
        fieldnames = ["input", "expected_output"]
        if include_metadata:
            fieldnames.extend([
                "sample_id",
                "category",
                "quality_score",
                "confidence",
                "source_type",
            ])

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for sample in samples:
            row = {
                "input": json.dumps(sample.input_data, ensure_ascii=False),
                "expected_output": json.dumps(sample.expected_output, ensure_ascii=False),
            }

            if include_metadata:
                row.update({
                    "sample_id": str(sample.sample_id),
                    "category": sample.category,
                    "quality_score": float(sample.quality_score) if sample.quality_score else 0,
                    "confidence": float(sample.confidence) if sample.confidence else 0,
                    "source_type": sample.source_type,
                })

            writer.writerow(row)

        return output.getvalue().encode("utf-8-sig")  # BOM 포함 (Excel 호환)
