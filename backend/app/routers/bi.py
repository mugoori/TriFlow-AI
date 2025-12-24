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


# ========== GenBI: AI Insights (Executive Summary) ==========


@router.post("/insights")
async def create_insight(
    request: Dict[str, Any],
    current_user: User = Depends(get_current_user),
):
    """
    AI 인사이트 생성 (Executive Summary)

    AWS QuickSight GenBI 스타일의 Fact/Reasoning/Action 구조로 인사이트 생성

    Request Body:
    - source_type: "chart" | "dashboard" | "dataset"
    - source_id: UUID (선택)
    - source_data: Dict (선택, 직접 데이터 전달)
    - focus_metrics: List[str] (선택)
    - time_range: str (선택, 예: "24h", "7d")
    """
    from app.services.insight_service import get_insight_service
    from app.schemas.bi_insight import InsightRequest

    insight_service = get_insight_service()

    try:
        insight_request = InsightRequest(
            source_type=request.get("source_type", "dashboard"),
            source_id=request.get("source_id"),
            source_data=request.get("source_data"),
            focus_metrics=request.get("focus_metrics"),
            time_range=request.get("time_range"),
            comparison_period=request.get("comparison_period"),
        )

        insight = await insight_service.generate_insight(
            tenant_id=current_user.tenant_id,
            user_id=current_user.user_id,
            request=insight_request,
        )

        return {
            "success": True,
            "insight": {
                "insight_id": str(insight.insight_id),
                "title": insight.title,
                "summary": insight.summary,
                "facts": [f.model_dump() for f in insight.facts],
                "reasoning": insight.reasoning.model_dump(),
                "actions": [a.model_dump() for a in insight.actions],
                "generated_at": insight.generated_at.isoformat(),
            },
        }

    except Exception as e:
        logger.error(f"Failed to generate insight: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/insights")
async def list_insights(
    current_user: User = Depends(get_current_user),
    source_type: Optional[str] = Query(None, description="소스 유형 필터"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """인사이트 목록 조회"""
    from app.services.insight_service import get_insight_service

    insight_service = get_insight_service()

    insights = await insight_service.get_insights(
        tenant_id=current_user.tenant_id,
        source_type=source_type,
        limit=limit,
        offset=offset,
    )

    return {
        "insights": [
            {
                "insight_id": str(i.insight_id),
                "title": i.title,
                "summary": i.summary,
                "source_type": i.source_type,
                "fact_count": len(i.facts),
                "action_count": len(i.actions),
                "feedback_score": i.feedback_score,
                "generated_at": i.generated_at.isoformat(),
            }
            for i in insights
        ],
        "total": len(insights),
        "limit": limit,
        "offset": offset,
    }


@router.get("/insights/pinned")
async def get_pinned_insights(
    current_user: User = Depends(get_current_user),
):
    """고정된 인사이트 목록 조회"""
    from app.services.bi_chat_service import get_bi_chat_service

    chat_service = get_bi_chat_service()

    pinned = await chat_service.get_pinned_insights(
        tenant_id=current_user.tenant_id,
    )

    return {
        "pinned_insights": pinned,
        "total": len(pinned),
    }


@router.get("/insights/{insight_id}")
async def get_insight(
    insight_id: UUID,
    current_user: User = Depends(get_current_user),
):
    """인사이트 상세 조회"""
    from app.services.insight_service import get_insight_service

    insight_service = get_insight_service()

    insight = await insight_service.get_insight(
        tenant_id=current_user.tenant_id,
        insight_id=insight_id,
    )

    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")

    return {
        "insight_id": str(insight.insight_id),
        "title": insight.title,
        "summary": insight.summary,
        "source_type": insight.source_type,
        "source_id": str(insight.source_id) if insight.source_id else None,
        "facts": [f.model_dump() for f in insight.facts],
        "reasoning": insight.reasoning.model_dump(),
        "actions": [a.model_dump() for a in insight.actions],
        "model_used": insight.model_used,
        "feedback_score": insight.feedback_score,
        "generated_at": insight.generated_at.isoformat(),
    }


@router.post("/insights/{insight_id}/feedback")
async def submit_insight_feedback(
    insight_id: UUID,
    request: Dict[str, Any],
    current_user: User = Depends(get_current_user),
):
    """인사이트 피드백 제출"""
    from app.services.insight_service import get_insight_service

    insight_service = get_insight_service()

    score = request.get("score")
    if score not in [-1, 0, 1]:
        raise HTTPException(status_code=400, detail="Score must be -1, 0, or 1")

    success = await insight_service.submit_feedback(
        tenant_id=current_user.tenant_id,
        insight_id=insight_id,
        user_id=current_user.user_id,
        score=score,
        comment=request.get("comment"),
    )

    if not success:
        raise HTTPException(status_code=404, detail="Insight not found")

    return {"success": True, "message": "Feedback submitted"}


# ========== GenBI: Data Stories ==========


@router.post("/stories")
async def create_story(
    request: Dict[str, Any],
    current_user: User = Depends(get_current_user),
):
    """
    데이터 스토리 생성

    auto_generate=True일 경우 LLM이 자동으로 섹션 생성

    Request Body:
    - title: str (필수)
    - description: str (선택)
    - auto_generate: bool (기본 True)
    - focus_topic: str (선택, 자동 생성 시 집중 주제)
    - time_range: str (선택)
    - source_chart_ids: List[UUID] (선택, 포함할 차트 목록)
    """
    from app.services.story_service import get_story_service
    from app.schemas.bi_story import StoryCreateRequest

    story_service = get_story_service()

    try:
        story_request = StoryCreateRequest(
            title=request.get("title", "새 스토리"),
            description=request.get("description"),
            auto_generate=request.get("auto_generate", True),
            focus_topic=request.get("focus_topic"),
            time_range=request.get("time_range"),
            source_chart_ids=request.get("source_chart_ids"),
        )

        story = await story_service.create_story(
            tenant_id=current_user.tenant_id,
            user_id=current_user.user_id,
            request=story_request,
        )

        return {
            "success": True,
            "story": {
                "story_id": str(story.story_id),
                "title": story.title,
                "description": story.description,
                "section_count": len(story.sections),
                "sections": [
                    {
                        "section_id": str(s.section_id),
                        "section_type": s.section_type,
                        "title": s.title,
                        "order": s.order,
                    }
                    for s in story.sections
                ],
                "created_at": story.created_at.isoformat(),
            },
        }

    except Exception as e:
        logger.error(f"Failed to create story: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stories")
async def list_stories(
    current_user: User = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """스토리 목록 조회"""
    from app.services.story_service import get_story_service

    story_service = get_story_service()

    stories = await story_service.get_stories(
        tenant_id=current_user.tenant_id,
        limit=limit,
        offset=offset,
    )

    return {
        "stories": [
            {
                "story_id": str(s.story_id),
                "title": s.title,
                "description": s.description,
                "section_count": len(s.sections),
                "is_public": s.is_public,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
                "published_at": s.published_at.isoformat() if s.published_at else None,
            }
            for s in stories
        ],
        "total": len(stories),
        "limit": limit,
        "offset": offset,
    }


@router.get("/stories/{story_id}")
async def get_story(
    story_id: UUID,
    current_user: User = Depends(get_current_user),
):
    """스토리 상세 조회"""
    from app.services.story_service import get_story_service

    story_service = get_story_service()

    story = await story_service.get_story(
        tenant_id=current_user.tenant_id,
        story_id=story_id,
    )

    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    return {
        "story_id": str(story.story_id),
        "title": story.title,
        "description": story.description,
        "is_public": story.is_public,
        "sections": [
            {
                "section_id": str(s.section_id),
                "section_type": s.section_type,
                "order": s.order,
                "title": s.title,
                "narrative": s.narrative,
                "charts": [c.model_dump() for c in s.charts],
                "ai_generated": s.ai_generated,
            }
            for s in story.sections
        ],
        "created_at": story.created_at.isoformat(),
        "updated_at": story.updated_at.isoformat(),
        "published_at": story.published_at.isoformat() if story.published_at else None,
    }


@router.put("/stories/{story_id}")
async def update_story(
    story_id: UUID,
    request: Dict[str, Any],
    current_user: User = Depends(get_current_user),
):
    """스토리 수정"""
    from app.services.story_service import get_story_service

    story_service = get_story_service()

    success = await story_service.update_story(
        tenant_id=current_user.tenant_id,
        story_id=story_id,
        title=request.get("title"),
        description=request.get("description"),
        is_public=request.get("is_public"),
    )

    if not success:
        raise HTTPException(status_code=404, detail="Story not found")

    return {"success": True, "message": "Story updated"}


@router.delete("/stories/{story_id}")
async def delete_story(
    story_id: UUID,
    current_user: User = Depends(get_current_user),
):
    """스토리 삭제"""
    from app.services.story_service import get_story_service

    story_service = get_story_service()

    success = await story_service.delete_story(
        tenant_id=current_user.tenant_id,
        story_id=story_id,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Story not found")

    return {"success": True, "message": "Story deleted"}


@router.post("/stories/{story_id}/sections")
async def add_story_section(
    story_id: UUID,
    request: Dict[str, Any],
    current_user: User = Depends(get_current_user),
):
    """스토리에 섹션 추가"""
    from app.services.story_service import get_story_service
    from app.schemas.bi_story import StorySectionCreateRequest

    story_service = get_story_service()

    try:
        section_request = StorySectionCreateRequest(
            section_type=request.get("section_type", "analysis"),
            title=request.get("title", "새 섹션"),
            narrative=request.get("narrative", ""),
            order=request.get("order"),
        )

        section = await story_service.add_section(
            tenant_id=current_user.tenant_id,
            story_id=story_id,
            request=section_request,
        )

        return {
            "success": True,
            "section": {
                "section_id": str(section.section_id),
                "section_type": section.section_type,
                "title": section.title,
                "order": section.order,
            },
        }

    except Exception as e:
        logger.error(f"Failed to add section: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/stories/{story_id}/sections/{section_id}")
async def delete_story_section(
    story_id: UUID,
    section_id: UUID,
    current_user: User = Depends(get_current_user),
):
    """스토리 섹션 삭제"""
    from app.services.story_service import get_story_service

    story_service = get_story_service()

    success = await story_service.delete_section(
        tenant_id=current_user.tenant_id,
        story_id=story_id,
        section_id=section_id,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Section not found")

    return {"success": True, "message": "Section deleted"}


# ========== GenBI: Chart Refinement ==========


@router.post("/charts/refine")
async def refine_chart(
    request: Dict[str, Any],
    current_user: User = Depends(get_current_user),
):
    """
    차트 수정 (Refinement Loop)

    사용자 지시에 따라 기존 차트 설정을 수정

    Request Body:
    - original_chart_config: Dict (필수, 원본 차트 설정)
    - refinement_instruction: str (필수, 수정 지시)
    - preserve_data: bool (기본 True)
    """
    from app.agents.bi_planner import BIPlannerAgent

    original_config = request.get("original_chart_config")
    instruction = request.get("refinement_instruction")

    if not original_config:
        raise HTTPException(status_code=400, detail="original_chart_config is required")
    if not instruction:
        raise HTTPException(status_code=400, detail="refinement_instruction is required")

    try:
        agent = BIPlannerAgent()
        result = agent._refine_chart(
            original_config=original_config,
            instruction=instruction,
            preserve_data=request.get("preserve_data", True),
        )

        return {
            "success": result.get("success", False),
            "refined_chart_config": result.get("refined_config"),
            "changes_made": result.get("changes_made", []),
            "error": result.get("error"),
        }

    except Exception as e:
        logger.error(f"Chart refinement failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== GenBI: Chat (대화형 인사이트) ==========


@router.post("/chat")
async def chat(
    request: Dict[str, Any],
    current_user: User = Depends(get_current_user),
):
    """
    BI 채팅 (대화형 인사이트 생성)

    자연어 질문에 AI가 데이터 분석 결과를 제공

    Request Body:
    - message: str (필수, 사용자 메시지)
    - session_id: UUID (선택, 기존 세션 계속)
    - context_type: str (선택, general|dashboard|chart|dataset)
    - context_id: UUID (선택, 특정 대시보드/차트/데이터셋)
    """
    from app.services.bi_chat_service import get_bi_chat_service, ChatRequest

    chat_service = get_bi_chat_service()

    message = request.get("message")
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    try:
        chat_request = ChatRequest(
            message=message,
            session_id=UUID(request["session_id"]) if request.get("session_id") else None,
            context_type=request.get("context_type", "general"),
            context_id=UUID(request["context_id"]) if request.get("context_id") else None,
        )

        response = await chat_service.chat(
            tenant_id=current_user.tenant_id,
            user_id=current_user.user_id,
            request=chat_request,
        )

        return {
            "success": True,
            "session_id": str(response.session_id),
            "message_id": str(response.message_id),
            "content": response.content,
            "response_type": response.response_type,
            "response_data": response.response_data,
            "linked_insight_id": str(response.linked_insight_id) if response.linked_insight_id else None,
            "linked_chart_id": str(response.linked_chart_id) if response.linked_chart_id else None,
        }

    except Exception as e:
        logger.error(f"Chat failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/sessions")
async def list_chat_sessions(
    current_user: User = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """채팅 세션 목록 조회"""
    from app.services.bi_chat_service import get_bi_chat_service

    chat_service = get_bi_chat_service()

    sessions = await chat_service.get_sessions(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        limit=limit,
        offset=offset,
    )

    return {
        "sessions": [
            {
                "session_id": str(s.session_id),
                "title": s.title,
                "context_type": s.context_type,
                "is_active": s.is_active,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
                "last_message_at": s.last_message_at.isoformat() if s.last_message_at else None,
            }
            for s in sessions
        ],
        "total": len(sessions),
    }


@router.get("/chat/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """세션의 메시지 목록 조회"""
    from app.services.bi_chat_service import get_bi_chat_service

    chat_service = get_bi_chat_service()

    messages = await chat_service.get_session_messages(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        session_id=session_id,
        limit=limit,
        offset=offset,
    )

    return {
        "messages": [
            {
                "message_id": str(m.message_id),
                "role": m.role,
                "content": m.content,
                "response_type": m.response_type,
                "response_data": m.response_data,
                "linked_insight_id": str(m.linked_insight_id) if m.linked_insight_id else None,
                "linked_chart_id": str(m.linked_chart_id) if m.linked_chart_id else None,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
        "total": len(messages),
    }


@router.delete("/chat/sessions/{session_id}")
async def delete_chat_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
):
    """채팅 세션 삭제"""
    from app.services.bi_chat_service import get_bi_chat_service

    chat_service = get_bi_chat_service()

    success = await chat_service.delete_session(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        session_id=session_id,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"success": True, "message": "Session deleted"}


@router.put("/chat/sessions/{session_id}")
async def update_chat_session(
    session_id: UUID,
    request: Dict[str, Any],
    current_user: User = Depends(get_current_user),
):
    """채팅 세션 수정 (제목 변경)"""
    from app.services.bi_chat_service import get_bi_chat_service

    chat_service = get_bi_chat_service()

    title = request.get("title")
    if not title:
        raise HTTPException(status_code=400, detail="title is required")

    success = await chat_service.update_session_title(
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        session_id=session_id,
        title=title,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"success": True, "message": "Session updated"}


# ========== GenBI: Pinned Insights (고정된 인사이트) ==========


@router.post("/insights/{insight_id}/pin")
async def pin_insight(
    insight_id: UUID,
    request: Dict[str, Any],
    current_user: User = Depends(get_current_user),
):
    """인사이트 대시보드에 고정"""
    from app.services.bi_chat_service import get_bi_chat_service

    chat_service = get_bi_chat_service()

    try:
        pinned = await chat_service.pin_insight(
            tenant_id=current_user.tenant_id,
            user_id=current_user.user_id,
            insight_id=insight_id,
            display_mode=request.get("display_mode", "card"),
        )

        return {
            "pin_id": str(pinned.pin_id),
            "insight_id": str(insight_id),
            "pinned_at": pinned.pinned_at.isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to pin insight: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/insights/{insight_id}/pin")
async def unpin_insight(
    insight_id: UUID,
    current_user: User = Depends(get_current_user),
):
    """인사이트 고정 해제"""
    from app.services.bi_chat_service import get_bi_chat_service

    chat_service = get_bi_chat_service()

    success = await chat_service.unpin_insight(
        tenant_id=current_user.tenant_id,
        insight_id=insight_id,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Pinned insight not found")

    return {"success": True, "message": "Insight unpinned"}


# ========== StatCard Endpoints (Dynamic Dashboard Cards) ==========


@router.get("/stat-cards")
async def get_stat_cards(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    사용자의 StatCard 설정 및 현재 값 조회

    Returns:
        - cards: StatCard 목록 (설정 + 현재 값)
        - total: 전체 카드 수
    """
    from app.services.stat_card_service import StatCardService

    try:
        service = StatCardService(db)
        result = await service.get_card_values(
            tenant_id=current_user.tenant_id,
            user_id=current_user.user_id,
        )

        return {
            "cards": [
                {
                    "config": card.config.model_dump(),
                    "value": card.value.model_dump(),
                }
                for card in result.cards
            ],
            "total": result.total,
        }
    except Exception as e:
        logger.error(f"Failed to get stat cards: {e}")
        # 테이블이 없는 경우 빈 목록 반환
        if "stat_card_configs" in str(e) or "does not exist" in str(e):
            return {"cards": [], "total": 0}
        raise HTTPException(status_code=500, detail=f"Failed to get stat cards: {str(e)}")


@router.post("/stat-cards")
async def create_stat_card(
    request: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    새 StatCard 추가

    Request Body:
    - source_type: "kpi" | "db_query" | "mcp_tool" (필수)
    - kpi_code: str (source_type=kpi일 때 필수)
    - table_name, column_name, aggregation: (source_type=db_query일 때 필수)
    - mcp_server_id, mcp_tool_name: (source_type=mcp_tool일 때 필수)
    - custom_title, custom_icon, custom_unit: (선택)
    - green_threshold, yellow_threshold, red_threshold, higher_is_better: (선택)
    """
    from app.services.stat_card_service import StatCardService
    from app.schemas.statcard import StatCardConfigCreate

    service = StatCardService(db)

    try:
        config_data = StatCardConfigCreate(**request)
        config = service.create_config(
            tenant_id=current_user.tenant_id,
            user_id=current_user.user_id,
            data=config_data,
        )

        return {
            "success": True,
            "config": config.model_dump(),
        }

    except Exception as e:
        logger.error(f"Failed to create stat card: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/stat-cards/{config_id}")
async def update_stat_card(
    config_id: UUID,
    request: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """StatCard 설정 수정"""
    from app.services.stat_card_service import StatCardService
    from app.schemas.statcard import StatCardConfigUpdate

    service = StatCardService(db)

    try:
        update_data = StatCardConfigUpdate(**request)
        config = service.update_config(
            config_id=config_id,
            tenant_id=current_user.tenant_id,
            user_id=current_user.user_id,
            data=update_data,
        )

        if not config:
            raise HTTPException(status_code=404, detail="StatCard not found")

        return {
            "success": True,
            "config": config.model_dump(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update stat card: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/stat-cards/{config_id}")
async def delete_stat_card(
    config_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """StatCard 삭제"""
    from app.services.stat_card_service import StatCardService

    service = StatCardService(db)

    success = service.delete_config(
        config_id=config_id,
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
    )

    if not success:
        raise HTTPException(status_code=404, detail="StatCard not found")

    return {"success": True, "message": "StatCard deleted"}


@router.put("/stat-cards/reorder")
async def reorder_stat_cards(
    request: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """StatCard 순서 변경"""
    from app.services.stat_card_service import StatCardService

    service = StatCardService(db)

    card_ids = request.get("card_ids", [])
    if not card_ids:
        raise HTTPException(status_code=400, detail="card_ids is required")

    try:
        card_ids_uuid = [UUID(cid) if isinstance(cid, str) else cid for cid in card_ids]
        configs = service.reorder_configs(
            tenant_id=current_user.tenant_id,
            user_id=current_user.user_id,
            card_ids=card_ids_uuid,
        )

        return {
            "success": True,
            "configs": [c.model_dump() for c in configs],
        }

    except Exception as e:
        logger.error(f"Failed to reorder stat cards: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/stat-cards/kpis")
async def list_available_kpis(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """StatCard에서 사용 가능한 KPI 목록 조회"""
    from app.services.stat_card_service import StatCardService

    try:
        service = StatCardService(db)
        result = service.list_kpis(tenant_id=current_user.tenant_id)

        return {
            "kpis": [kpi.model_dump() for kpi in result.kpis],
            "categories": result.categories,
        }
    except Exception as e:
        logger.error(f"Failed to list KPIs: {e}")
        if "does not exist" in str(e):
            return {"kpis": [], "categories": []}
        raise HTTPException(status_code=500, detail=f"Failed to list KPIs: {str(e)}")


@router.get("/stat-cards/tables")
async def list_available_tables(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """StatCard DB 쿼리에서 사용 가능한 테이블/컬럼 목록"""
    from app.services.stat_card_service import StatCardService

    try:
        service = StatCardService(db)
        result = service.list_available_tables(tenant_id=current_user.tenant_id)

        return {
            "tables": [t.model_dump() for t in result.tables],
        }
    except Exception as e:
        logger.error(f"Failed to list tables: {e}")
        if "does not exist" in str(e):
            return {"tables": []}
        raise HTTPException(status_code=500, detail=f"Failed to list tables: {str(e)}")


@router.get("/stat-cards/mcp-tools")
async def list_available_mcp_tools(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """StatCard에서 사용 가능한 MCP 도구 목록"""
    from app.services.stat_card_service import StatCardService

    try:
        service = StatCardService(db)
        result = service.list_mcp_tools(tenant_id=current_user.tenant_id)

        return {
            "tools": [t.model_dump() for t in result.tools],
        }
    except Exception as e:
        logger.error(f"Failed to list MCP tools: {e}")
        if "does not exist" in str(e):
            return {"tools": []}
        raise HTTPException(status_code=500, detail=f"Failed to list MCP tools: {str(e)}")


# ========== Sample Data Seeding (개발용) ==========


class SeedSampleDataRequest(BaseModel):
    """샘플 데이터 생성 요청"""
    days: int = Field(14, ge=1, le=365, description="생성할 날짜 범위 (일)")
    clear_existing: bool = Field(True, description="기존 실적 데이터 삭제 여부")
    include_dimensions: bool = Field(True, description="차원 데이터(라인, 제품) 포함 여부")


class SeedSampleDataResponse(BaseModel):
    """샘플 데이터 생성 결과"""
    success: bool
    message: str
    created_lines: int = 0
    created_products: int = 0
    created_shifts: int = 0
    created_production_records: int = 0
    created_inventory_records: int = 0
    date_range: Dict[str, str] = {}


@router.post("/seed-sample-data", response_model=SeedSampleDataResponse)
async def seed_sample_production_data(
    request: SeedSampleDataRequest = SeedSampleDataRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    대시보드용 샘플 생산 데이터 생성 (개발/테스트용)

    StatCard에서 KPI를 표시하기 위한 가상 생산 데이터를 생성합니다.

    생성 데이터:
    - 라인(dim_line): 1라인~3라인
    - 제품(dim_product): 제품A, 제품B, 부품C
    - 교대(dim_shift): 주간, 야간
    - 생산실적(fact_daily_production): 최근 N일간 랜덤 생산 데이터

    KPI 값 범위:
    - 불량률: 1~5%
    - OEE: 75~90%
    - 수율: 95~99%
    - 다운타임: 0~60분
    - 일일생산량: 800~1200 EA
    - 달성률: 80~120%
    """
    import random
    from sqlalchemy import text

    tenant_id = current_user.tenant_id

    try:
        created_lines = 0
        created_products = 0
        created_shifts = 0
        created_production_records = 0
        created_inventory_records = 0

        # 1. 차원 데이터 생성 (include_dimensions=True일 때)
        if request.include_dimensions:
            # 1-1. 라인 데이터 (category: assembly, processing, packaging, inspection, warehouse)
            lines_data = [
                {"line_code": "L1", "name": "1라인", "category": "assembly", "capacity_per_hour": 100},
                {"line_code": "L2", "name": "2라인", "category": "assembly", "capacity_per_hour": 120},
                {"line_code": "L3", "name": "3라인", "category": "processing", "capacity_per_hour": 80},
            ]

            for line in lines_data:
                # UPSERT: 없으면 생성, 있으면 스킵
                result = db.execute(
                    text("""
                        INSERT INTO bi.dim_line (tenant_id, line_code, name, category, capacity_per_hour, is_active)
                        VALUES (:tenant_id, :line_code, :name, :category, :capacity_per_hour, true)
                        ON CONFLICT (tenant_id, line_code) DO NOTHING
                        RETURNING line_code
                    """),
                    {"tenant_id": str(tenant_id), **line}
                )
                if result.fetchone():
                    created_lines += 1

            # 1-2. 제품 데이터
            products_data = [
                {"product_code": "P001", "name": "제품A", "category": "완제품", "unit": "EA", "target_cycle_time_sec": 45},
                {"product_code": "P002", "name": "제품B", "category": "완제품", "unit": "EA", "target_cycle_time_sec": 50},
                {"product_code": "P003", "name": "부품C", "category": "반제품", "unit": "EA", "target_cycle_time_sec": 30},
            ]

            for product in products_data:
                result = db.execute(
                    text("""
                        INSERT INTO bi.dim_product (tenant_id, product_code, name, category, unit, target_cycle_time_sec, is_active)
                        VALUES (:tenant_id, :product_code, :name, :category, :unit, :target_cycle_time_sec, true)
                        ON CONFLICT (tenant_id, product_code) DO NOTHING
                        RETURNING product_code
                    """),
                    {"tenant_id": str(tenant_id), **product}
                )
                if result.fetchone():
                    created_products += 1

            # 1-3. 교대 데이터 (dim_shift 스키마에 맞게 수정)
            from datetime import time as dt_time
            shifts_data = [
                {"shift_code": "day", "name": "주간", "start_time": dt_time(8, 0), "end_time": dt_time(16, 0), "duration_hours": 8.0, "is_night_shift": False, "shift_order": 1},
                {"shift_code": "evening", "name": "오후", "start_time": dt_time(16, 0), "end_time": dt_time(0, 0), "duration_hours": 8.0, "is_night_shift": False, "shift_order": 2},
                {"shift_code": "night", "name": "야간", "start_time": dt_time(0, 0), "end_time": dt_time(8, 0), "duration_hours": 8.0, "is_night_shift": True, "shift_order": 3},
            ]

            for shift in shifts_data:
                result = db.execute(
                    text("""
                        INSERT INTO bi.dim_shift (tenant_id, shift_code, name, start_time, end_time, duration_hours, is_night_shift, shift_order)
                        VALUES (:tenant_id, :shift_code, :name, :start_time, :end_time, :duration_hours, :is_night_shift, :shift_order)
                        ON CONFLICT (tenant_id, shift_code) DO NOTHING
                        RETURNING shift_code
                    """),
                    {"tenant_id": str(tenant_id), **shift}
                )
                if result.fetchone():
                    created_shifts += 1

        # 2. 기존 실적 데이터 삭제 (clear_existing=True일 때)
        if request.clear_existing:
            db.execute(
                text("DELETE FROM bi.fact_daily_production WHERE tenant_id = :tenant_id"),
                {"tenant_id": str(tenant_id)}
            )
            db.execute(
                text("DELETE FROM bi.fact_inventory_snapshot WHERE tenant_id = :tenant_id"),
                {"tenant_id": str(tenant_id)}
            )

        # 3. 라인, 제품, 교대 코드 조회
        lines = db.execute(
            text("SELECT line_code, capacity_per_hour FROM bi.dim_line WHERE tenant_id = :tenant_id AND is_active = true"),
            {"tenant_id": str(tenant_id)}
        ).fetchall()

        products = db.execute(
            text("SELECT product_code, target_cycle_time_sec FROM bi.dim_product WHERE tenant_id = :tenant_id AND is_active = true"),
            {"tenant_id": str(tenant_id)}
        ).fetchall()

        shifts = db.execute(
            text("SELECT shift_code FROM bi.dim_shift WHERE tenant_id = :tenant_id"),
            {"tenant_id": str(tenant_id)}
        ).fetchall()

        if not lines or not products or not shifts:
            return SeedSampleDataResponse(
                success=False,
                message="차원 데이터(라인, 제품, 교대)가 없습니다. include_dimensions=true로 다시 시도하세요.",
            )

        # 4. 실적 데이터 생성
        end_date = date.today()
        start_date = end_date - timedelta(days=request.days)

        for day_offset in range(request.days + 1):
            production_date = start_date + timedelta(days=day_offset)

            for line in lines:
                line_code = line[0]
                for product in products:
                    product_code = product[0]
                    target_ct = float(product[1]) if product[1] else 45.0
                    for shift in shifts:
                        shift_code = shift[0]

                        # 랜덤 생산량 (800~1200)
                        total_qty = random.randint(800, 1200)

                        # 양품률 95~99%
                        yield_rate = random.uniform(0.95, 0.99)
                        good_qty = int(total_qty * yield_rate)
                        defect_qty = total_qty - good_qty

                        # 재작업/스크랩
                        rework_qty = random.randint(0, min(10, defect_qty))
                        scrap_qty = defect_qty - rework_qty

                        # 가동 시간 (분) - 8시간 기준 (480분), 400~480분
                        runtime_minutes = random.randint(400, 480)
                        downtime_minutes = random.randint(0, 60)
                        setup_time_minutes = random.randint(10, 30)

                        # 계획 생산량
                        planned_qty = 1000

                        # 사이클타임 (초)
                        cycle_time_avg = target_ct + random.uniform(-5, 10)
                        cycle_time_std = random.uniform(1, 5)

                        db.execute(
                            text("""
                                INSERT INTO bi.fact_daily_production (
                                    tenant_id, date, line_code, product_code, shift,
                                    total_qty, good_qty, defect_qty, rework_qty, scrap_qty,
                                    cycle_time_avg, cycle_time_std,
                                    runtime_minutes, downtime_minutes, setup_time_minutes,
                                    planned_qty, target_cycle_time
                                ) VALUES (
                                    :tenant_id, :date, :line_code, :product_code, :shift,
                                    :total_qty, :good_qty, :defect_qty, :rework_qty, :scrap_qty,
                                    :cycle_time_avg, :cycle_time_std,
                                    :runtime_minutes, :downtime_minutes, :setup_time_minutes,
                                    :planned_qty, :target_cycle_time
                                )
                                ON CONFLICT (tenant_id, date, line_code, product_code, shift) DO UPDATE SET
                                    total_qty = EXCLUDED.total_qty,
                                    good_qty = EXCLUDED.good_qty,
                                    defect_qty = EXCLUDED.defect_qty,
                                    rework_qty = EXCLUDED.rework_qty,
                                    scrap_qty = EXCLUDED.scrap_qty,
                                    cycle_time_avg = EXCLUDED.cycle_time_avg,
                                    cycle_time_std = EXCLUDED.cycle_time_std,
                                    runtime_minutes = EXCLUDED.runtime_minutes,
                                    downtime_minutes = EXCLUDED.downtime_minutes,
                                    setup_time_minutes = EXCLUDED.setup_time_minutes,
                                    planned_qty = EXCLUDED.planned_qty,
                                    target_cycle_time = EXCLUDED.target_cycle_time,
                                    updated_at = now()
                            """),
                            {
                                "tenant_id": str(tenant_id),
                                "date": production_date,
                                "line_code": line_code,
                                "product_code": product_code,
                                "shift": shift_code,
                                "total_qty": total_qty,
                                "good_qty": good_qty,
                                "defect_qty": defect_qty,
                                "rework_qty": rework_qty,
                                "scrap_qty": scrap_qty,
                                "cycle_time_avg": cycle_time_avg,
                                "cycle_time_std": cycle_time_std,
                                "runtime_minutes": runtime_minutes,
                                "downtime_minutes": downtime_minutes,
                                "setup_time_minutes": setup_time_minutes,
                                "planned_qty": planned_qty,
                                "target_cycle_time": target_ct,
                            }
                        )
                        created_production_records += 1

        # 5. 재고 스냅샷 데이터 생성 (fact_inventory_snapshot)
        # 재고일수(inventory_days) KPI 계산을 위한 데이터
        locations = ["창고A", "창고B", "생산현장"]

        for day_offset in range(request.days + 1):
            snapshot_date = start_date + timedelta(days=day_offset)

            for product in products:
                product_code = product[0]

                for location in locations:
                    # 재고 수량 (100~500)
                    stock_qty = random.randint(100, 500)
                    safety_stock_qty = random.randint(50, 100)
                    reserved_qty = random.randint(0, 50)
                    available_qty = max(0, stock_qty - reserved_qty)
                    in_transit_qty = random.randint(0, 30)

                    # 일평균 사용량 (30~80)
                    avg_daily_usage = random.uniform(30, 80)

                    # 재고 커버리지 일수 = 재고량 / 일평균 사용량
                    coverage_days = stock_qty / avg_daily_usage if avg_daily_usage > 0 else 0

                    # 재고 가치 (단가 1000원 기준)
                    stock_value = stock_qty * 1000

                    # 최근 입출고일 (최근 1~7일 이내)
                    last_receipt_date = snapshot_date - timedelta(days=random.randint(1, 7))
                    last_issue_date = snapshot_date - timedelta(days=random.randint(1, 3))

                    db.execute(
                        text("""
                            INSERT INTO bi.fact_inventory_snapshot (
                                tenant_id, date, product_code, location,
                                stock_qty, safety_stock_qty, reserved_qty, available_qty, in_transit_qty,
                                stock_value, avg_daily_usage, coverage_days,
                                last_receipt_date, last_issue_date
                            ) VALUES (
                                :tenant_id, :date, :product_code, :location,
                                :stock_qty, :safety_stock_qty, :reserved_qty, :available_qty, :in_transit_qty,
                                :stock_value, :avg_daily_usage, :coverage_days,
                                :last_receipt_date, :last_issue_date
                            )
                            ON CONFLICT (tenant_id, date, product_code, location) DO UPDATE SET
                                stock_qty = EXCLUDED.stock_qty,
                                safety_stock_qty = EXCLUDED.safety_stock_qty,
                                reserved_qty = EXCLUDED.reserved_qty,
                                available_qty = EXCLUDED.available_qty,
                                in_transit_qty = EXCLUDED.in_transit_qty,
                                stock_value = EXCLUDED.stock_value,
                                avg_daily_usage = EXCLUDED.avg_daily_usage,
                                coverage_days = EXCLUDED.coverage_days,
                                last_receipt_date = EXCLUDED.last_receipt_date,
                                last_issue_date = EXCLUDED.last_issue_date
                        """),
                        {
                            "tenant_id": str(tenant_id),
                            "date": snapshot_date,
                            "product_code": product_code,
                            "location": location,
                            "stock_qty": stock_qty,
                            "safety_stock_qty": safety_stock_qty,
                            "reserved_qty": reserved_qty,
                            "available_qty": available_qty,
                            "in_transit_qty": in_transit_qty,
                            "stock_value": stock_value,
                            "avg_daily_usage": avg_daily_usage,
                            "coverage_days": coverage_days,
                            "last_receipt_date": last_receipt_date,
                            "last_issue_date": last_issue_date,
                        }
                    )
                    created_inventory_records += 1

        db.commit()

        return SeedSampleDataResponse(
            success=True,
            message=f"샘플 데이터가 성공적으로 생성되었습니다.",
            created_lines=created_lines,
            created_products=created_products,
            created_shifts=created_shifts,
            created_production_records=created_production_records,
            created_inventory_records=created_inventory_records,
            date_range={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            }
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to seed sample data: {e}")
        raise HTTPException(status_code=500, detail=f"샘플 데이터 생성 실패: {str(e)}")
