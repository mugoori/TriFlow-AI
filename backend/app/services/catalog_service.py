# -*- coding: utf-8 -*-
"""
BI Catalog Repository
BI 카탈로그 조회 및 메타데이터 관리

스펙 참조: B-2-2 (BI Learning Design), B-4 (API Interface)
"""
import logging
from typing import Dict, List, Any, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.bi import BiDataset, BiMetric

logger = logging.getLogger(__name__)


class CatalogRepository:
    """BI 카탈로그 Repository"""

    def __init__(self, db: Session):
        self.db = db

    async def get_catalog(self, tenant_id: UUID) -> Dict[str, Any]:
        """
        테넌트의 전체 BI 카탈로그 조회

        LLM 프롬프트 생성용으로 사용됨

        Returns:
            {
                'datasets': [...],
                'metrics': [...],
                'dimensions': [...]
            }
        """
        datasets = self.db.query(BiDataset).filter(
            BiDataset.tenant_id == tenant_id
        ).all()

        metrics = self.db.query(BiMetric).filter(
            BiMetric.tenant_id == tenant_id
        ).all()

        return {
            'datasets': [
                {
                    'id': ds.source_ref,
                    'name': ds.name,
                    'description': ds.description,
                    'source_type': ds.source_type,
                    'columns': self._extract_columns(ds.source_ref),
                    'metrics': [m.name for m in ds.metrics],
                    'refresh_schedule': ds.refresh_schedule,
                    'last_refreshed': ds.last_refresh_at.isoformat() if ds.last_refresh_at else None,
                    'row_count': ds.row_count
                }
                for ds in datasets
            ],
            'metrics': [
                {
                    'id': m.name,
                    'name': m.name,
                    'dataset': m.dataset.source_ref if m.dataset else None,
                    'description': m.description,
                    'aggregation': m.agg_type,
                    'expression': m.expression_sql,
                    'format': m.format_type,
                    'default_chart': m.default_chart_type
                }
                for m in metrics
            ]
        }

    def _extract_columns(self, table_name: str) -> List[Dict[str, str]]:
        """
        PostgreSQL information_schema에서 컬럼 정보 추출

        Args:
            table_name: 테이블 이름

        Returns:
            컬럼 정보 리스트
        """
        query = text("""
            SELECT
                column_name,
                data_type,
                is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'bi'
              AND table_name = :table_name
            ORDER BY ordinal_position
        """)

        try:
            result = self.db.execute(query, {'table_name': table_name})
            columns = []

            for row in result:
                columns.append({
                    'name': row.column_name,
                    'type': row.data_type,
                    'nullable': row.is_nullable == 'YES'
                })

            return columns
        except Exception as e:
            logger.error(f"Failed to extract columns for {table_name}: {e}")
            return []

    def get_datasets(
        self,
        tenant_id: UUID,
        source_type: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[BiDataset]:
        """
        데이터셋 목록 조회 (필터링 지원)

        Args:
            tenant_id: 테넌트 ID
            source_type: 소스 타입 필터
            search: 검색 키워드

        Returns:
            데이터셋 리스트
        """
        query = self.db.query(BiDataset).filter(
            BiDataset.tenant_id == tenant_id
        )

        if source_type:
            query = query.filter(BiDataset.source_type == source_type)

        if search:
            query = query.filter(
                BiDataset.name.ilike(f'%{search}%') |
                BiDataset.description.ilike(f'%{search}%')
            )

        return query.all()

    def get_metrics(
        self,
        tenant_id: UUID,
        dataset_id: Optional[UUID] = None,
        agg_type: Optional[str] = None
    ) -> List[BiMetric]:
        """
        메트릭 목록 조회 (필터링 지원)

        Args:
            tenant_id: 테넌트 ID
            dataset_id: 데이터셋 ID 필터
            agg_type: 집계 타입 필터

        Returns:
            메트릭 리스트
        """
        query = self.db.query(BiMetric).filter(
            BiMetric.tenant_id == tenant_id
        )

        if dataset_id:
            query = query.filter(BiMetric.dataset_id == dataset_id)

        if agg_type:
            query = query.filter(BiMetric.agg_type == agg_type)

        return query.all()

    def create_metric(
        self,
        tenant_id: UUID,
        dataset_id: UUID,
        name: str,
        expression_sql: str,
        description: Optional[str] = None,
        agg_type: Optional[str] = None,
        format_type: Optional[str] = None,
        default_chart_type: Optional[str] = None,
        created_by: Optional[UUID] = None
    ) -> BiMetric:
        """
        새 메트릭 생성

        Returns:
            생성된 BiMetric
        """
        metric = BiMetric(
            tenant_id=tenant_id,
            dataset_id=dataset_id,
            name=name,
            description=description,
            expression_sql=expression_sql,
            agg_type=agg_type,
            format_type=format_type,
            default_chart_type=default_chart_type,
            created_by=created_by
        )

        self.db.add(metric)
        self.db.commit()
        self.db.refresh(metric)

        logger.info(f"Created metric: {name} for dataset {dataset_id}")

        return metric


def get_catalog_repository(db: Session) -> CatalogRepository:
    """CatalogRepository 인스턴스 반환"""
    return CatalogRepository(db)
