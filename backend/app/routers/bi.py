"""
BI Analytics API Router
스펙 참조: B-3-2, B-4

엔드포인트:
- GET /api/v1/bi/dashboards: 대시보드 목록 조회
- GET /api/v1/bi/dashboards/{id}: 대시보드 상세 조회
- POST /api/v1/bi/dashboards: 대시보드 생성
- PUT /api/v1/bi/dashboards/{id}: 대시보드 수정
- DELETE /api/v1/bi/dashboards/{id}: 대시보드 삭제
- GET /api/v1/bi/datasets: 데이터셋 목록 조회
- GET /api/v1/bi/datasets/{id}/query: 데이터 쿼리
- GET /api/v1/bi/metrics: 지표 목록 조회
- GET /api/v1/bi/metrics/{id}/value: 지표 값 계산
- GET /api/v1/bi/analytics/defect-trend: 불량 추이
- GET /api/v1/bi/analytics/oee: OEE 조회
- GET /api/v1/bi/analytics/inventory: 재고 분석
- GET /api/v1/bi/analytics/production: 생산 실적
"""
import logging
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.bi import (
    BiDashboard,
    BiDataset,
    BiMetric,
    DimLine,
    DimProduct,
    DimKpi,
    FactDailyProduction,
    FactDailyDefect,
    FactInventorySnapshot,
)
from app.routers.auth import get_current_user
from app.models import User

logger = logging.getLogger(__name__)

router = APIRouter()


# ========== Pydantic Models ==========


class DashboardLayoutComponent(BaseModel):
    id: str
    type: str  # chart, table, kpi_card, gauge
    position: Dict[str, int]  # x, y, w, h
    config: Dict[str, Any]


class DashboardLayout(BaseModel):
    components: List[DashboardLayoutComponent]


class DashboardCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    layout: DashboardLayout
    is_public: bool = False


class DashboardUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    layout: Optional[DashboardLayout] = None
    is_public: Optional[bool] = None


class DashboardResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    layout: Dict[str, Any]
    is_public: bool
    owner_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DatasetResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    source_type: str
    source_ref: str
    default_filters: Optional[Dict[str, Any]]
    last_refresh_at: Optional[datetime]
    row_count: Optional[int]

    class Config:
        from_attributes = True


class MetricResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    dataset_id: UUID
    expression_sql: str
    agg_type: Optional[str]
    format_type: Optional[str]
    default_chart_type: Optional[str]

    class Config:
        from_attributes = True


class MetricValueResponse(BaseModel):
    metric_id: UUID
    metric_name: str
    value: float
    formatted_value: str
    comparison: Optional[Dict[str, Any]] = None
    calculated_at: datetime


class ProductionSummary(BaseModel):
    date: date
    line_code: str
    line_name: Optional[str] = None
    product_code: str
    product_name: Optional[str] = None
    shift: str
    total_qty: float
    good_qty: float
    defect_qty: float
    defect_rate: float
    yield_rate: float
    runtime_minutes: float
    downtime_minutes: float
    availability: float


class ProductionResponse(BaseModel):
    data: List[ProductionSummary]
    total: int
    summary: Dict[str, Any]


class DefectTrendItem(BaseModel):
    date: date
    line_code: str
    product_code: Optional[str] = None
    total_qty: float
    defect_qty: float
    defect_rate: float
    top_defect_types: Optional[List[Dict[str, Any]]] = None


class DefectTrendResponse(BaseModel):
    data: List[DefectTrendItem]
    total: int
    avg_defect_rate: float


class OEEItem(BaseModel):
    date: date
    line_code: str
    line_name: Optional[str] = None
    shift: str
    availability: float
    performance: float
    quality: float
    oee: float
    runtime_minutes: float
    downtime_minutes: float


class OEEResponse(BaseModel):
    data: List[OEEItem]
    total: int
    avg_oee: float
    avg_availability: float
    avg_performance: float
    avg_quality: float


class InventoryItem(BaseModel):
    date: date
    product_code: str
    product_name: Optional[str] = None
    location: str
    stock_qty: float
    safety_stock_qty: float
    available_qty: float
    coverage_days: Optional[float] = None
    stock_status: str


class InventoryResponse(BaseModel):
    data: List[InventoryItem]
    total: int
    summary: Dict[str, Any]


# ========== Dashboard Endpoints ==========


@router.get("/dashboards", response_model=List[DashboardResponse])
async def list_dashboards(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    include_public: bool = Query(True, description="공개 대시보드 포함 여부"),
):
    """대시보드 목록 조회"""
    query = db.query(BiDashboard).filter(
        BiDashboard.tenant_id == current_user.tenant_id
    )

    if include_public:
        query = query.filter(
            (BiDashboard.owner_id == current_user.user_id) | (BiDashboard.is_public == True)
        )
    else:
        query = query.filter(BiDashboard.owner_id == current_user.user_id)

    dashboards = query.order_by(desc(BiDashboard.updated_at)).all()
    return dashboards


@router.get("/dashboards/{dashboard_id}", response_model=DashboardResponse)
async def get_dashboard(
    dashboard_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """대시보드 상세 조회"""
    dashboard = db.query(BiDashboard).filter(
        BiDashboard.id == dashboard_id,
        BiDashboard.tenant_id == current_user.tenant_id,
    ).first()

    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    # 권한 확인: 소유자이거나 공개 대시보드
    if dashboard.owner_id != current_user.user_id and not dashboard.is_public:
        raise HTTPException(status_code=403, detail="Access denied")

    return dashboard


@router.post("/dashboards", response_model=DashboardResponse)
async def create_dashboard(
    data: DashboardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """대시보드 생성"""
    dashboard = BiDashboard(
        tenant_id=current_user.tenant_id,
        name=data.name,
        description=data.description,
        layout=data.layout.model_dump(),
        is_public=data.is_public,
        owner_id=current_user.user_id,
    )
    db.add(dashboard)
    db.commit()
    db.refresh(dashboard)

    logger.info(f"Dashboard created: {dashboard.id} by user {current_user.user_id}")
    return dashboard


@router.put("/dashboards/{dashboard_id}", response_model=DashboardResponse)
async def update_dashboard(
    dashboard_id: UUID,
    data: DashboardUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """대시보드 수정"""
    dashboard = db.query(BiDashboard).filter(
        BiDashboard.id == dashboard_id,
        BiDashboard.tenant_id == current_user.tenant_id,
        BiDashboard.owner_id == current_user.user_id,
    ).first()

    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found or access denied")

    if data.name is not None:
        dashboard.name = data.name
    if data.description is not None:
        dashboard.description = data.description
    if data.layout is not None:
        dashboard.layout = data.layout.model_dump()
    if data.is_public is not None:
        dashboard.is_public = data.is_public

    db.commit()
    db.refresh(dashboard)

    return dashboard


@router.delete("/dashboards/{dashboard_id}")
async def delete_dashboard(
    dashboard_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """대시보드 삭제"""
    dashboard = db.query(BiDashboard).filter(
        BiDashboard.id == dashboard_id,
        BiDashboard.tenant_id == current_user.tenant_id,
        BiDashboard.owner_id == current_user.user_id,
    ).first()

    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found or access denied")

    db.delete(dashboard)
    db.commit()

    return {"status": "deleted", "id": str(dashboard_id)}


# ========== Dataset Endpoints ==========


@router.get("/datasets", response_model=List[DatasetResponse])
async def list_datasets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """데이터셋 목록 조회"""
    datasets = db.query(BiDataset).filter(
        BiDataset.tenant_id == current_user.tenant_id
    ).order_by(BiDataset.name).all()
    return datasets


@router.get("/datasets/{dataset_id}/query")
async def query_dataset(
    dataset_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    start_date: Optional[date] = Query(None, description="시작 날짜"),
    end_date: Optional[date] = Query(None, description="종료 날짜"),
    line_code: Optional[str] = Query(None, description="라인 코드"),
    product_code: Optional[str] = Query(None, description="제품 코드"),
    limit: int = Query(100, ge=1, le=1000, description="결과 수 제한"),
    offset: int = Query(0, ge=0, description="오프셋"),
):
    """데이터셋 쿼리 (동적 필터 지원)"""
    dataset = db.query(BiDataset).filter(
        BiDataset.id == dataset_id,
        BiDataset.tenant_id == current_user.tenant_id,
    ).first()

    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # 데이터셋 소스에 따라 쿼리 실행
    # 현재는 fact_daily_production을 기본으로 지원
    if dataset.source_ref == "fact_daily_production":
        query = db.query(FactDailyProduction).filter(
            FactDailyProduction.tenant_id == current_user.tenant_id
        )

        if start_date:
            query = query.filter(FactDailyProduction.date >= start_date)
        if end_date:
            query = query.filter(FactDailyProduction.date <= end_date)
        if line_code:
            query = query.filter(FactDailyProduction.line_code == line_code)
        if product_code:
            query = query.filter(FactDailyProduction.product_code == product_code)

        total = query.count()
        data = query.order_by(desc(FactDailyProduction.date)).offset(offset).limit(limit).all()

        return {
            "dataset_id": str(dataset_id),
            "data": [
                {
                    "date": str(row.date),
                    "line_code": row.line_code,
                    "product_code": row.product_code,
                    "shift": row.shift,
                    "total_qty": float(row.total_qty),
                    "good_qty": float(row.good_qty),
                    "defect_qty": float(row.defect_qty),
                    "defect_rate": row.defect_rate,
                    "runtime_minutes": float(row.runtime_minutes),
                }
                for row in data
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    raise HTTPException(status_code=400, detail=f"Unsupported dataset source: {dataset.source_ref}")


# ========== Metric Endpoints ==========


@router.get("/metrics", response_model=List[MetricResponse])
async def list_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    dataset_id: Optional[UUID] = Query(None, description="데이터셋 ID 필터"),
):
    """지표 목록 조회"""
    query = db.query(BiMetric).filter(
        BiMetric.tenant_id == current_user.tenant_id
    )

    if dataset_id:
        query = query.filter(BiMetric.dataset_id == dataset_id)

    metrics = query.order_by(BiMetric.name).all()
    return metrics


@router.get("/metrics/{metric_id}/value", response_model=MetricValueResponse)
async def get_metric_value(
    metric_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    start_date: Optional[date] = Query(None, description="시작 날짜"),
    end_date: Optional[date] = Query(None, description="종료 날짜"),
    line_code: Optional[str] = Query(None, description="라인 코드"),
    compare_previous: bool = Query(False, description="이전 기간과 비교"),
):
    """지표 값 계산"""
    metric = db.query(BiMetric).filter(
        BiMetric.id == metric_id,
        BiMetric.tenant_id == current_user.tenant_id,
    ).first()

    if not metric:
        raise HTTPException(status_code=404, detail="Metric not found")

    # 기본 날짜 범위: 최근 30일
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    # 간단한 지표 계산 (예: 불량률)
    query = db.query(
        func.sum(FactDailyProduction.total_qty).label("total_qty"),
        func.sum(FactDailyProduction.defect_qty).label("defect_qty"),
        func.sum(FactDailyProduction.good_qty).label("good_qty"),
    ).filter(
        FactDailyProduction.tenant_id == current_user.tenant_id,
        FactDailyProduction.date >= start_date,
        FactDailyProduction.date <= end_date,
    )

    if line_code:
        query = query.filter(FactDailyProduction.line_code == line_code)

    result = query.first()

    # 지표 타입에 따른 값 계산
    value = 0.0
    formatted_value = "0"

    if result and result.total_qty:
        total_qty = float(result.total_qty)
        defect_qty = float(result.defect_qty or 0)
        good_qty = float(result.good_qty or 0)

        if "defect" in metric.name.lower() or "불량" in metric.name:
            value = (defect_qty / total_qty) * 100 if total_qty > 0 else 0
            formatted_value = f"{value:.2f}%"
        elif "yield" in metric.name.lower() or "수율" in metric.name:
            value = (good_qty / total_qty) * 100 if total_qty > 0 else 0
            formatted_value = f"{value:.2f}%"
        elif "total" in metric.name.lower() or "생산" in metric.name:
            value = total_qty
            formatted_value = f"{int(value):,}"
        else:
            value = total_qty
            formatted_value = f"{value:.2f}"

    comparison = None
    if compare_previous:
        # 이전 기간 계산
        period_days = (end_date - start_date).days
        prev_end = start_date - timedelta(days=1)
        prev_start = prev_end - timedelta(days=period_days)

        prev_query = db.query(
            func.sum(FactDailyProduction.total_qty).label("total_qty"),
            func.sum(FactDailyProduction.defect_qty).label("defect_qty"),
        ).filter(
            FactDailyProduction.tenant_id == current_user.tenant_id,
            FactDailyProduction.date >= prev_start,
            FactDailyProduction.date <= prev_end,
        )

        if line_code:
            prev_query = prev_query.filter(FactDailyProduction.line_code == line_code)

        prev_result = prev_query.first()
        prev_value = 0.0

        if prev_result and prev_result.total_qty:
            prev_total = float(prev_result.total_qty)
            prev_defect = float(prev_result.defect_qty or 0)
            if "defect" in metric.name.lower() or "불량" in metric.name:
                prev_value = (prev_defect / prev_total) * 100 if prev_total > 0 else 0

        change = value - prev_value
        change_pct = (change / prev_value * 100) if prev_value > 0 else 0

        comparison = {
            "previous_value": prev_value,
            "change": change,
            "change_percent": change_pct,
            "period": f"{prev_start} ~ {prev_end}",
        }

    return MetricValueResponse(
        metric_id=metric_id,
        metric_name=metric.name,
        value=value,
        formatted_value=formatted_value,
        comparison=comparison,
        calculated_at=datetime.utcnow(),
    )


# ========== Analytics Endpoints ==========


@router.get("/analytics/production", response_model=ProductionResponse)
async def get_production_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    start_date: Optional[date] = Query(None, description="시작 날짜"),
    end_date: Optional[date] = Query(None, description="종료 날짜"),
    line_code: Optional[str] = Query(None, description="라인 코드"),
    product_code: Optional[str] = Query(None, description="제품 코드"),
    shift: Optional[str] = Query(None, description="교대"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """생산 실적 분석"""
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    query = db.query(FactDailyProduction).filter(
        FactDailyProduction.tenant_id == current_user.tenant_id,
        FactDailyProduction.date >= start_date,
        FactDailyProduction.date <= end_date,
    )

    if line_code:
        query = query.filter(FactDailyProduction.line_code == line_code)
    if product_code:
        query = query.filter(FactDailyProduction.product_code == product_code)
    if shift:
        query = query.filter(FactDailyProduction.shift == shift)

    total = query.count()
    data = query.order_by(desc(FactDailyProduction.date)).offset(offset).limit(limit).all()

    # 요약 통계 계산
    summary_query = db.query(
        func.sum(FactDailyProduction.total_qty).label("total_qty"),
        func.sum(FactDailyProduction.good_qty).label("good_qty"),
        func.sum(FactDailyProduction.defect_qty).label("defect_qty"),
        func.sum(FactDailyProduction.runtime_minutes).label("runtime"),
        func.sum(FactDailyProduction.downtime_minutes).label("downtime"),
    ).filter(
        FactDailyProduction.tenant_id == current_user.tenant_id,
        FactDailyProduction.date >= start_date,
        FactDailyProduction.date <= end_date,
    )

    if line_code:
        summary_query = summary_query.filter(FactDailyProduction.line_code == line_code)
    if product_code:
        summary_query = summary_query.filter(FactDailyProduction.product_code == product_code)

    summary_result = summary_query.first()

    total_qty = float(summary_result.total_qty or 0)
    good_qty = float(summary_result.good_qty or 0)
    defect_qty = float(summary_result.defect_qty or 0)
    runtime = float(summary_result.runtime or 0)
    downtime = float(summary_result.downtime or 0)

    summary = {
        "total_production": total_qty,
        "total_good": good_qty,
        "total_defect": defect_qty,
        "avg_defect_rate": (defect_qty / total_qty * 100) if total_qty > 0 else 0,
        "avg_yield_rate": (good_qty / total_qty * 100) if total_qty > 0 else 0,
        "total_runtime_hours": runtime / 60,
        "total_downtime_hours": downtime / 60,
        "avg_availability": (runtime / (runtime + downtime) * 100) if (runtime + downtime) > 0 else 0,
    }

    production_data = []
    for row in data:
        total = float(row.total_qty) if row.total_qty else 0
        good = float(row.good_qty) if row.good_qty else 0
        defect = float(row.defect_qty) if row.defect_qty else 0
        rt = float(row.runtime_minutes) if row.runtime_minutes else 0
        dt = float(row.downtime_minutes) if row.downtime_minutes else 0

        production_data.append(ProductionSummary(
            date=row.date,
            line_code=row.line_code,
            product_code=row.product_code,
            shift=row.shift,
            total_qty=total,
            good_qty=good,
            defect_qty=defect,
            defect_rate=(defect / total * 100) if total > 0 else 0,
            yield_rate=(good / total * 100) if total > 0 else 0,
            runtime_minutes=rt,
            downtime_minutes=dt,
            availability=(rt / (rt + dt) * 100) if (rt + dt) > 0 else 0,
        ))

    return ProductionResponse(data=production_data, total=total, summary=summary)


@router.get("/analytics/defect-trend", response_model=DefectTrendResponse)
async def get_defect_trend(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    start_date: Optional[date] = Query(None, description="시작 날짜"),
    end_date: Optional[date] = Query(None, description="종료 날짜"),
    line_code: Optional[str] = Query(None, description="라인 코드"),
    group_by: str = Query("date", description="그룹핑 기준 (date, line, product)"),
):
    """불량 추이 분석"""
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=90)

    # 일별 불량률 집계
    query = db.query(
        FactDailyProduction.date,
        FactDailyProduction.line_code,
        func.sum(FactDailyProduction.total_qty).label("total_qty"),
        func.sum(FactDailyProduction.defect_qty).label("defect_qty"),
    ).filter(
        FactDailyProduction.tenant_id == current_user.tenant_id,
        FactDailyProduction.date >= start_date,
        FactDailyProduction.date <= end_date,
    )

    if line_code:
        query = query.filter(FactDailyProduction.line_code == line_code)

    if group_by == "date":
        query = query.group_by(FactDailyProduction.date, FactDailyProduction.line_code)
    elif group_by == "line":
        query = query.group_by(FactDailyProduction.line_code, FactDailyProduction.date)
    else:
        query = query.group_by(FactDailyProduction.date, FactDailyProduction.line_code)

    results = query.order_by(FactDailyProduction.date).all()

    data = []
    total_qty_sum = 0
    total_defect_sum = 0

    for row in results:
        total = float(row.total_qty) if row.total_qty else 0
        defect = float(row.defect_qty) if row.defect_qty else 0
        total_qty_sum += total
        total_defect_sum += defect

        data.append(DefectTrendItem(
            date=row.date,
            line_code=row.line_code,
            total_qty=total,
            defect_qty=defect,
            defect_rate=(defect / total * 100) if total > 0 else 0,
        ))

    avg_defect_rate = (total_defect_sum / total_qty_sum * 100) if total_qty_sum > 0 else 0

    return DefectTrendResponse(
        data=data,
        total=len(data),
        avg_defect_rate=avg_defect_rate,
    )


@router.get("/analytics/oee", response_model=OEEResponse)
async def get_oee_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    start_date: Optional[date] = Query(None, description="시작 날짜"),
    end_date: Optional[date] = Query(None, description="종료 날짜"),
    line_code: Optional[str] = Query(None, description="라인 코드"),
):
    """OEE (종합설비효율) 분석

    OEE = Availability × Performance × Quality
    - Availability: 가동률 (가동시간 / 계획시간)
    - Performance: 성능률 (생산량 × 표준CT / 가동시간)
    - Quality: 품질률 (양품수 / 총생산수)
    """
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    # 일별 OEE 계산
    query = db.query(
        FactDailyProduction.date,
        FactDailyProduction.line_code,
        FactDailyProduction.shift,
        func.sum(FactDailyProduction.total_qty).label("total_qty"),
        func.sum(FactDailyProduction.good_qty).label("good_qty"),
        func.sum(FactDailyProduction.runtime_minutes).label("runtime"),
        func.sum(FactDailyProduction.downtime_minutes).label("downtime"),
        func.sum(FactDailyProduction.setup_time_minutes).label("setup"),
        func.avg(FactDailyProduction.target_cycle_time).label("target_ct"),
    ).filter(
        FactDailyProduction.tenant_id == current_user.tenant_id,
        FactDailyProduction.date >= start_date,
        FactDailyProduction.date <= end_date,
    ).group_by(
        FactDailyProduction.date,
        FactDailyProduction.line_code,
        FactDailyProduction.shift,
    )

    if line_code:
        query = query.filter(FactDailyProduction.line_code == line_code)

    results = query.order_by(desc(FactDailyProduction.date)).all()

    data = []
    total_oee = 0
    total_availability = 0
    total_performance = 0
    total_quality = 0
    count = 0

    for row in results:
        total_qty = float(row.total_qty) if row.total_qty else 0
        good_qty = float(row.good_qty) if row.good_qty else 0
        runtime = float(row.runtime) if row.runtime else 0
        downtime = float(row.downtime) if row.downtime else 0
        target_ct = float(row.target_ct) if row.target_ct else 60  # 기본 60초

        # Availability = runtime / (runtime + downtime)
        total_time = runtime + downtime
        availability = (runtime / total_time * 100) if total_time > 0 else 0

        # Performance = (total_qty * target_ct / 60) / runtime (분 단위)
        expected_output = (runtime * 60) / target_ct if target_ct > 0 else 0
        performance = (total_qty / expected_output * 100) if expected_output > 0 else 0
        performance = min(performance, 100)  # 100% 상한

        # Quality = good_qty / total_qty
        quality = (good_qty / total_qty * 100) if total_qty > 0 else 0

        # OEE
        oee = (availability / 100) * (performance / 100) * (quality / 100) * 100

        data.append(OEEItem(
            date=row.date,
            line_code=row.line_code,
            shift=row.shift,
            availability=round(availability, 2),
            performance=round(performance, 2),
            quality=round(quality, 2),
            oee=round(oee, 2),
            runtime_minutes=runtime,
            downtime_minutes=downtime,
        ))

        total_oee += oee
        total_availability += availability
        total_performance += performance
        total_quality += quality
        count += 1

    avg_oee = total_oee / count if count > 0 else 0
    avg_availability = total_availability / count if count > 0 else 0
    avg_performance = total_performance / count if count > 0 else 0
    avg_quality = total_quality / count if count > 0 else 0

    return OEEResponse(
        data=data,
        total=len(data),
        avg_oee=round(avg_oee, 2),
        avg_availability=round(avg_availability, 2),
        avg_performance=round(avg_performance, 2),
        avg_quality=round(avg_quality, 2),
    )


@router.get("/analytics/inventory", response_model=InventoryResponse)
async def get_inventory_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    snapshot_date: Optional[date] = Query(None, description="스냅샷 날짜"),
    product_code: Optional[str] = Query(None, description="제품 코드"),
    location: Optional[str] = Query(None, description="위치"),
    stock_status: Optional[str] = Query(None, description="재고 상태 (normal, low, below_safety, excess)"),
):
    """재고 분석"""
    if not snapshot_date:
        snapshot_date = date.today()

    query = db.query(FactInventorySnapshot).filter(
        FactInventorySnapshot.tenant_id == current_user.tenant_id,
        FactInventorySnapshot.date == snapshot_date,
    )

    if product_code:
        query = query.filter(FactInventorySnapshot.product_code == product_code)
    if location:
        query = query.filter(FactInventorySnapshot.location == location)

    results = query.all()

    data = []
    status_counts = {"normal": 0, "low": 0, "below_safety": 0, "excess": 0}
    total_stock_value = 0

    for row in results:
        stock = float(row.stock_qty) if row.stock_qty else 0
        safety = float(row.safety_stock_qty) if row.safety_stock_qty else 0
        available = float(row.available_qty) if row.available_qty else 0
        coverage = float(row.coverage_days) if row.coverage_days else None
        value = float(row.stock_value) if row.stock_value else 0

        # 재고 상태 계산
        if stock < safety:
            status = "below_safety"
        elif stock < safety * 1.5:
            status = "low"
        elif stock > safety * 3:
            status = "excess"
        else:
            status = "normal"

        # 필터링
        if stock_status and status != stock_status:
            continue

        status_counts[status] += 1
        total_stock_value += value

        data.append(InventoryItem(
            date=row.date,
            product_code=row.product_code,
            location=row.location,
            stock_qty=stock,
            safety_stock_qty=safety,
            available_qty=available,
            coverage_days=coverage,
            stock_status=status,
        ))

    summary = {
        "snapshot_date": str(snapshot_date),
        "total_items": len(data),
        "total_stock_value": total_stock_value,
        "status_distribution": status_counts,
        "below_safety_count": status_counts["below_safety"],
        "low_stock_count": status_counts["low"],
    }

    return InventoryResponse(data=data, total=len(data), summary=summary)


# ========== Dimension Data Endpoints ==========


@router.get("/dimensions/lines")
async def get_lines(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    is_active: bool = Query(True, description="활성 라인만 조회"),
):
    """라인 목록 조회"""
    query = db.query(DimLine).filter(DimLine.tenant_id == current_user.tenant_id)

    if is_active:
        query = query.filter(DimLine.is_active == True)

    lines = query.order_by(DimLine.line_code).all()

    return [
        {
            "line_code": line.line_code,
            "name": line.name,
            "category": line.category,
            "capacity_per_hour": float(line.capacity_per_hour) if line.capacity_per_hour else None,
            "is_active": line.is_active,
        }
        for line in lines
    ]


@router.get("/dimensions/products")
async def get_products(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    is_active: bool = Query(True, description="활성 제품만 조회"),
    category: Optional[str] = Query(None, description="카테고리 필터"),
):
    """제품 목록 조회"""
    query = db.query(DimProduct).filter(DimProduct.tenant_id == current_user.tenant_id)

    if is_active:
        query = query.filter(DimProduct.is_active == True)
    if category:
        query = query.filter(DimProduct.category == category)

    products = query.order_by(DimProduct.product_code).all()

    return [
        {
            "product_code": product.product_code,
            "name": product.name,
            "category": product.category,
            "subcategory": product.subcategory,
            "unit": product.unit,
            "target_cycle_time_sec": float(product.target_cycle_time_sec) if product.target_cycle_time_sec else None,
            "is_active": product.is_active,
        }
        for product in products
    ]


@router.get("/dimensions/kpis")
async def get_kpis(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    category: Optional[str] = Query(None, description="카테고리 필터"),
):
    """KPI 정의 목록 조회"""
    query = db.query(DimKpi).filter(
        DimKpi.tenant_id == current_user.tenant_id,
        DimKpi.is_active == True,
    )

    if category:
        query = query.filter(DimKpi.category == category)

    kpis = query.order_by(DimKpi.category, DimKpi.kpi_code).all()

    return [
        {
            "kpi_code": kpi.kpi_code,
            "name": kpi.name,
            "category": kpi.category,
            "unit": kpi.unit,
            "default_target": float(kpi.default_target) if kpi.default_target else None,
            "higher_is_better": kpi.higher_is_better,
            "green_threshold": float(kpi.green_threshold) if kpi.green_threshold else None,
            "yellow_threshold": float(kpi.yellow_threshold) if kpi.yellow_threshold else None,
            "red_threshold": float(kpi.red_threshold) if kpi.red_threshold else None,
        }
        for kpi in kpis
    ]


# ========== Chart Builder Endpoints ==========


class ChartRequest(BaseModel):
    """차트 생성 요청"""
    chart_type: str = Field(..., description="차트 타입: line, bar, pie, scatter, heatmap, table")
    data_source: str = Field(..., description="데이터 소스: production, defect, oee, inventory")
    x_field: str = Field(..., description="X축 필드")
    y_fields: List[str] = Field(..., description="Y축 필드 목록")
    title: str = Field(..., description="차트 제목")
    subtitle: Optional[str] = Field(None, description="부제목")
    filters: Optional[Dict[str, Any]] = Field(None, description="필터 조건")
    options: Optional[Dict[str, Any]] = Field(None, description="차트 옵션")
    output_format: str = Field("chartjs", description="출력 형식: chartjs, echarts, raw")


class ChartResponse(BaseModel):
    """차트 응답"""
    chart_id: str
    chart_type: str
    title: str
    config: Dict[str, Any]
    data_count: int


@router.post("/charts/generate", response_model=ChartResponse)
async def generate_chart(
    request: ChartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    start_date: Optional[date] = Query(None, description="시작일"),
    end_date: Optional[date] = Query(None, description="종료일"),
):
    """
    차트 설정 생성

    데이터를 조회하고 Chart.js/ECharts 호환 차트 설정을 생성합니다.

    지원 차트 타입:
    - line: 라인 차트
    - bar: 바 차트
    - pie: 파이 차트
    - scatter: 산점도
    - heatmap: 히트맵
    - table: 테이블
    """
    from app.services.chart_builder import get_chart_builder, ChartType
    import uuid

    chart_builder = get_chart_builder()
    tenant_id = current_user.tenant_id

    # 기본 날짜 범위 설정
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=7)

    # 데이터 소스별 데이터 조회
    data = []
    if request.data_source == "production":
        data = _get_production_chart_data(db, tenant_id, start_date, end_date, request.filters)
    elif request.data_source == "defect":
        data = _get_defect_chart_data(db, tenant_id, start_date, end_date, request.filters)
    elif request.data_source == "oee":
        data = _get_oee_chart_data(db, tenant_id, start_date, end_date, request.filters)
    elif request.data_source == "inventory":
        data = _get_inventory_chart_data(db, tenant_id, start_date, end_date, request.filters)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown data source: {request.data_source}")

    if not data:
        raise HTTPException(status_code=404, detail="No data found for the given criteria")

    # 차트 타입 매핑
    chart_type_map = {
        "line": ChartType.LINE,
        "bar": ChartType.BAR,
        "pie": ChartType.PIE,
        "scatter": ChartType.SCATTER,
        "heatmap": ChartType.HEATMAP,
        "table": ChartType.TABLE,
    }

    chart_type = chart_type_map.get(request.chart_type.lower())
    if not chart_type:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid chart type: {request.chart_type}. Supported: line, bar, pie, scatter, heatmap, table"
        )

    # 차트 옵션 적용
    options = request.options or {}

    # 차트 설정 생성
    chart_id = f"chart-{uuid.uuid4().hex[:8]}"
    chart_config = chart_builder.build_chart(
        chart_id=chart_id,
        chart_type=chart_type,
        data=data,
        x_field=request.x_field,
        y_fields=request.y_fields,
        title=request.title,
        subtitle=request.subtitle or f"{start_date.isoformat()} ~ {end_date.isoformat()}",
        **options
    )

    # 출력 형식에 따라 변환
    if request.output_format == "chartjs":
        config = chart_builder.to_chartjs(chart_config)
    elif request.output_format == "echarts":
        config = chart_builder.to_echarts(chart_config)
    else:
        config = chart_config.model_dump()

    return ChartResponse(
        chart_id=chart_id,
        chart_type=request.chart_type,
        title=request.title,
        config=config,
        data_count=len(data),
    )


def _get_production_chart_data(
    db: Session,
    tenant_id: UUID,
    start_date: date,
    end_date: date,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """생산 실적 차트 데이터 조회"""
    query = db.query(
        FactDailyProduction.date,
        FactDailyProduction.line_code,
        func.sum(FactDailyProduction.total_qty).label("total_qty"),
        func.sum(FactDailyProduction.good_qty).label("good_qty"),
        func.sum(FactDailyProduction.defect_qty).label("defect_qty"),
    ).filter(
        FactDailyProduction.tenant_id == tenant_id,
        FactDailyProduction.date >= start_date,
        FactDailyProduction.date <= end_date,
    )

    if filters:
        if filters.get("line_code"):
            query = query.filter(FactDailyProduction.line_code == filters["line_code"])
        if filters.get("product_code"):
            query = query.filter(FactDailyProduction.product_code == filters["product_code"])

    query = query.group_by(
        FactDailyProduction.date,
        FactDailyProduction.line_code,
    ).order_by(FactDailyProduction.date)

    results = query.all()

    return [
        {
            "date": r.date.isoformat(),
            "line_code": r.line_code,
            "total_qty": float(r.total_qty or 0),
            "good_qty": float(r.good_qty or 0),
            "defect_qty": float(r.defect_qty or 0),
            "defect_rate": float(r.defect_qty / r.total_qty * 100) if r.total_qty else 0,
        }
        for r in results
    ]


def _get_defect_chart_data(
    db: Session,
    tenant_id: UUID,
    start_date: date,
    end_date: date,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """불량 추이 차트 데이터 조회"""
    query = db.query(
        FactDailyDefect.date,
        FactDailyDefect.line_code,
        FactDailyDefect.defect_type,
        func.sum(FactDailyDefect.defect_count).label("defect_count"),
    ).filter(
        FactDailyDefect.tenant_id == tenant_id,
        FactDailyDefect.date >= start_date,
        FactDailyDefect.date <= end_date,
    )

    if filters:
        if filters.get("line_code"):
            query = query.filter(FactDailyDefect.line_code == filters["line_code"])
        if filters.get("defect_type"):
            query = query.filter(FactDailyDefect.defect_type == filters["defect_type"])

    query = query.group_by(
        FactDailyDefect.date,
        FactDailyDefect.line_code,
        FactDailyDefect.defect_type,
    ).order_by(FactDailyDefect.date)

    results = query.all()

    return [
        {
            "date": r.date.isoformat(),
            "line_code": r.line_code,
            "defect_type": r.defect_type,
            "defect_count": int(r.defect_count or 0),
        }
        for r in results
    ]


def _get_oee_chart_data(
    db: Session,
    tenant_id: UUID,
    start_date: date,
    end_date: date,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """OEE 차트 데이터 조회"""
    query = db.query(
        FactDailyProduction.date,
        FactDailyProduction.line_code,
        func.sum(FactDailyProduction.planned_time_min).label("planned_time"),
        func.sum(FactDailyProduction.actual_time_min).label("actual_time"),
        func.sum(FactDailyProduction.downtime_min).label("downtime"),
        func.sum(FactDailyProduction.total_qty).label("total_qty"),
        func.sum(FactDailyProduction.good_qty).label("good_qty"),
    ).filter(
        FactDailyProduction.tenant_id == tenant_id,
        FactDailyProduction.date >= start_date,
        FactDailyProduction.date <= end_date,
    )

    if filters:
        if filters.get("line_code"):
            query = query.filter(FactDailyProduction.line_code == filters["line_code"])

    query = query.group_by(
        FactDailyProduction.date,
        FactDailyProduction.line_code,
    ).order_by(FactDailyProduction.date)

    results = query.all()

    data = []
    for r in results:
        planned = float(r.planned_time or 0)
        actual = float(r.actual_time or 0)
        downtime = float(r.downtime or 0)
        total = float(r.total_qty or 0)
        good = float(r.good_qty or 0)

        # OEE 계산
        availability = (actual - downtime) / actual * 100 if actual > 0 else 0
        performance = 80  # 기본값 (실제로는 cycle time 기반 계산)
        quality = good / total * 100 if total > 0 else 0
        oee = availability * performance * quality / 10000

        data.append({
            "date": r.date.isoformat(),
            "line_code": r.line_code,
            "availability": round(availability, 2),
            "performance": round(performance, 2),
            "quality": round(quality, 2),
            "oee": round(oee, 2),
        })

    return data


def _get_inventory_chart_data(
    db: Session,
    tenant_id: UUID,
    start_date: date,
    end_date: date,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """재고 차트 데이터 조회"""
    query = db.query(
        FactInventorySnapshot.snapshot_date,
        FactInventorySnapshot.product_code,
        func.sum(FactInventorySnapshot.quantity).label("quantity"),
        func.sum(FactInventorySnapshot.value).label("value"),
    ).filter(
        FactInventorySnapshot.tenant_id == tenant_id,
        FactInventorySnapshot.snapshot_date >= start_date,
        FactInventorySnapshot.snapshot_date <= end_date,
    )

    if filters:
        if filters.get("product_code"):
            query = query.filter(FactInventorySnapshot.product_code == filters["product_code"])
        if filters.get("location"):
            query = query.filter(FactInventorySnapshot.location == filters["location"])

    query = query.group_by(
        FactInventorySnapshot.snapshot_date,
        FactInventorySnapshot.product_code,
    ).order_by(FactInventorySnapshot.snapshot_date)

    results = query.all()

    return [
        {
            "date": r.snapshot_date.isoformat(),
            "product_code": r.product_code,
            "quantity": float(r.quantity or 0),
            "value": float(r.value or 0),
        }
        for r in results
    ]


@router.get("/charts/types")
async def get_chart_types():
    """지원하는 차트 타입 목록 조회"""
    return {
        "chart_types": [
            {
                "type": "line",
                "name": "라인 차트",
                "description": "시계열 데이터 시각화에 적합",
                "recommended_for": ["trend", "time_series"],
            },
            {
                "type": "bar",
                "name": "바 차트",
                "description": "범주별 비교에 적합",
                "recommended_for": ["comparison", "ranking"],
            },
            {
                "type": "pie",
                "name": "파이 차트",
                "description": "비율/구성 시각화에 적합",
                "recommended_for": ["composition", "proportion"],
            },
            {
                "type": "scatter",
                "name": "산점도",
                "description": "상관관계 분석에 적합",
                "recommended_for": ["correlation", "distribution"],
            },
            {
                "type": "heatmap",
                "name": "히트맵",
                "description": "다차원 데이터 패턴 시각화에 적합",
                "recommended_for": ["pattern", "matrix"],
            },
            {
                "type": "table",
                "name": "테이블",
                "description": "상세 데이터 표시에 적합",
                "recommended_for": ["detail", "raw_data"],
            },
        ],
        "output_formats": ["chartjs", "echarts", "raw"],
        "data_sources": ["production", "defect", "oee", "inventory"],
    }
