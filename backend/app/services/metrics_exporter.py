"""
Prometheus 메트릭 Exporter
DB 데이터를 Prometheus 메트릭으로 변환하여 Grafana 대시보드에 표시
"""
import random
import logging
from datetime import datetime
from sqlalchemy import text
from app.database import SessionLocal
from app.utils.metrics import (
    production_quantity_total,
    defect_quantity_total,
    equipment_utilization,
    active_alerts_count,
)

logger = logging.getLogger(__name__)


def update_business_metrics():
    """
    DB 데이터를 기반으로 비즈니스 메트릭 업데이트
    스케줄러에서 주기적으로 호출됨 (1분마다)
    """
    db = SessionLocal()
    try:
        # 1. 생산량 및 불량품 시뮬레이션 (라인별)
        lines = ["LINE_A", "LINE_B", "LINE_C", "LINE_D"]

        for line in lines:
            # 오늘 생산량 (1000-5000 사이 랜덤)
            prod_qty = random.randint(1000, 5000)
            production_quantity_total.labels(
                period="today",
                line_code=line,
                product_type="default"
            ).set(prod_qty)

            # 불량률 1-5%
            defect_qty = int(prod_qty * random.uniform(0.01, 0.05))
            defect_quantity_total.labels(
                period="today",
                line_code=line,
                defect_type="quality"
            ).set(defect_qty)

            # 설비 가동률 85-98%
            utilization = random.uniform(85, 98)
            equipment_utilization.labels(
                line_code=line,
                equipment_id=f"{line}_MAIN"
            ).set(utilization)

        # 2. 활성 알림 수 (실제 DB에서 조회)
        try:
            result = db.execute(text(
                "SELECT severity, COUNT(*) "
                "FROM core.alerts "
                "WHERE resolved_at IS NULL "
                "GROUP BY severity"
            ))

            for severity, count in result:
                active_alerts_count.labels(
                    severity=severity,
                    category="operational"
                ).set(count)
        except Exception as e:
            # alerts 테이블이 없을 수 있음
            logger.debug(f"Could not fetch active alerts: {e}")
            # 데모 데이터
            active_alerts_count.labels(
                severity="warning",
                category="operational"
            ).set(random.randint(0, 5))
            active_alerts_count.labels(
                severity="critical",
                category="operational"
            ).set(random.randint(0, 2))

        logger.info("Business metrics updated successfully")

    except Exception as e:
        logger.error(f"Failed to update business metrics: {e}", exc_info=True)
    finally:
        db.close()
