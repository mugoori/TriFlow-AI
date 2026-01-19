"""
Materialized View 리프레시 서비스

대시보드 성능 최적화를 위한 Materialized Views를 주기적으로 리프레시합니다.

MVs:
- bi.mv_defect_trend: 일일 결함 추이 (90일)
- bi.mv_oee_daily: OEE 일일 집계 (90일)
- bi.mv_line_performance: 라인별 성과 (30일)
- bi.mv_quality_summary: 품질 요약 (30일)
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from prometheus_client import Counter, Histogram, Gauge

logger = logging.getLogger(__name__)

# Prometheus Metrics
mv_refresh_duration_seconds = Histogram(
    'mv_refresh_duration_seconds',
    'Duration of MV refresh in seconds',
    ['mv_name', 'status']
)

mv_refresh_total = Counter(
    'mv_refresh_total',
    'Total number of MV refreshes',
    ['mv_name', 'status']
)

mv_row_count = Gauge(
    'mv_row_count',
    'Number of rows in MV after refresh',
    ['mv_name']
)


class MVRefreshService:
    """
    Materialized View 리프레시 서비스

    30분마다 4개의 MV를 CONCURRENTLY 리프레시합니다.
    CONCURRENTLY 옵션은 리프레시 중에도 읽기 쿼리가 가능합니다.
    """

    # 리프레시할 MV 목록
    MATERIALIZED_VIEWS = [
        "bi.mv_defect_trend",
        "bi.mv_oee_daily",
        "bi.mv_line_performance",
        "bi.mv_quality_summary",
    ]

    def __init__(self):
        self._last_refresh: Optional[datetime] = None
        self._refresh_count: int = 0
        self._last_error: Optional[str] = None
        self._mv_status: Dict[str, Dict[str, Any]] = {}

    @property
    def status(self) -> Dict[str, Any]:
        """리프레시 서비스 상태 조회"""
        return {
            "last_refresh": self._last_refresh.isoformat() if self._last_refresh else None,
            "refresh_count": self._refresh_count,
            "last_error": self._last_error,
            "mv_status": self._mv_status,
        }

    async def refresh_all(self, db: AsyncSession) -> Dict[str, Any]:
        """
        모든 MV를 CONCURRENTLY 리프레시

        Returns:
            리프레시 결과 (성공/실패 상태)
        """
        results: Dict[str, Any] = {
            "started_at": datetime.utcnow().isoformat(),
            "views": {},
            "success": True,
            "errors": [],
        }

        for mv_name in self.MATERIALIZED_VIEWS:
            try:
                start_time = datetime.utcnow()
                row_count = await self._refresh_mv(db, mv_name)
                elapsed = (datetime.utcnow() - start_time).total_seconds()

                # Prometheus 메트릭
                mv_refresh_duration_seconds.labels(mv_name=mv_name, status='success').observe(elapsed)
                mv_refresh_total.labels(mv_name=mv_name, status='success').inc()
                mv_row_count.labels(mv_name=mv_name).set(row_count)

                results["views"][mv_name] = {
                    "status": "success",
                    "elapsed_seconds": elapsed,
                    "row_count": row_count,
                }
                self._mv_status[mv_name] = {
                    "last_refresh": datetime.utcnow().isoformat(),
                    "status": "success",
                    "elapsed_seconds": elapsed,
                    "row_count": row_count,
                }
                logger.info(f"Refreshed {mv_name} in {elapsed:.2f}s ({row_count} rows)")

            except Exception as e:
                error_msg = str(e)

                # Prometheus 메트릭 (실패)
                mv_refresh_total.labels(mv_name=mv_name, status='failed').inc()

                results["views"][mv_name] = {
                    "status": "failed",
                    "error": error_msg,
                }
                results["success"] = False
                results["errors"].append(f"{mv_name}: {error_msg}")
                self._mv_status[mv_name] = {
                    "last_refresh": datetime.utcnow().isoformat(),
                    "status": "failed",
                    "error": error_msg,
                }
                logger.error(f"Failed to refresh {mv_name}: {e}")

        results["completed_at"] = datetime.utcnow().isoformat()
        self._last_refresh = datetime.utcnow()
        self._refresh_count += 1

        if not results["success"]:
            self._last_error = "; ".join(results["errors"])

        return results

    async def _refresh_mv(self, db: AsyncSession, mv_name: str) -> int:
        """
        단일 MV 리프레시 (CONCURRENTLY)

        CONCURRENTLY 옵션:
        - 리프레시 중에도 SELECT 쿼리 가능
        - UNIQUE INDEX가 필요함 (마이그레이션에서 생성됨)

        Returns:
            int: 리프레시 후 행 개수
        """
        query = text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {mv_name}")
        await db.execute(query)
        await db.commit()

        # 행 개수 조회
        count_query = text(f"SELECT COUNT(*) FROM {mv_name}")
        result = await db.execute(count_query)
        return result.scalar() or 0

    async def refresh_single(self, db: AsyncSession, mv_name: str) -> Dict[str, Any]:
        """
        단일 MV 리프레시

        Args:
            db: 데이터베이스 세션
            mv_name: MV 이름 (예: "bi.mv_oee_daily")

        Returns:
            리프레시 결과
        """
        if mv_name not in self.MATERIALIZED_VIEWS:
            return {
                "status": "error",
                "message": f"Unknown MV: {mv_name}. Available: {self.MATERIALIZED_VIEWS}",
            }

        try:
            start_time = datetime.utcnow()
            await self._refresh_mv(db, mv_name)
            elapsed = (datetime.utcnow() - start_time).total_seconds()

            self._mv_status[mv_name] = {
                "last_refresh": datetime.utcnow().isoformat(),
                "status": "success",
                "elapsed_seconds": elapsed,
            }

            return {
                "status": "success",
                "mv_name": mv_name,
                "elapsed_seconds": elapsed,
            }

        except Exception as e:
            error_msg = str(e)
            self._mv_status[mv_name] = {
                "last_refresh": datetime.utcnow().isoformat(),
                "status": "failed",
                "error": error_msg,
            }
            logger.error(f"Failed to refresh {mv_name}: {e}")
            return {
                "status": "failed",
                "mv_name": mv_name,
                "error": error_msg,
            }

    async def get_mv_info(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """
        MV 메타데이터 조회

        Returns:
            각 MV의 상태 및 통계 정보
        """
        query = text("""
            SELECT
                schemaname || '.' || matviewname as mv_name,
                definition,
                hasindexes,
                ispopulated
            FROM pg_matviews
            WHERE schemaname = 'bi'
            ORDER BY matviewname
        """)
        result = await db.execute(query)
        rows = result.fetchall()

        mv_info = []
        for row in rows:
            mv_name = row[0]
            mv_info.append({
                "name": mv_name,
                "has_indexes": row[2],
                "is_populated": row[3],
                "last_refresh": self._mv_status.get(mv_name, {}).get("last_refresh"),
                "status": self._mv_status.get(mv_name, {}).get("status", "unknown"),
            })

        return mv_info


# 싱글톤 인스턴스
mv_refresh_service = MVRefreshService()


async def refresh_materialized_views():
    """
    스케줄러용 리프레시 핸들러

    scheduler_service에서 호출됩니다.
    """
    from app.database import async_session_factory

    async with async_session_factory() as db:
        try:
            result = await mv_refresh_service.refresh_all(db)
            if result["success"]:
                logger.info(f"MV refresh completed: {result['views']}")
            else:
                logger.warning(f"MV refresh completed with errors: {result['errors']}")
        except Exception as e:
            logger.error(f"MV refresh failed: {e}")
            raise
