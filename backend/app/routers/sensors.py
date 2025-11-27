"""
Sensor Data Router
센서 데이터 조회 API - PostgreSQL DB 연동
"""
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Query, Depends
from pydantic import BaseModel
from sqlalchemy import func, distinct
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SensorData

router = APIRouter()


# Response Models
class SensorDataItem(BaseModel):
    sensor_id: str
    recorded_at: datetime
    line_code: str
    sensor_type: str
    value: float
    unit: Optional[str] = None

    class Config:
        from_attributes = True


class SensorDataResponse(BaseModel):
    data: List[SensorDataItem]
    total: int
    page: int
    page_size: int


class SensorFilterOptions(BaseModel):
    lines: List[str]
    sensor_types: List[str]


class LineSummary(BaseModel):
    line_code: str
    avg_temperature: Optional[float] = None
    avg_pressure: Optional[float] = None
    avg_humidity: Optional[float] = None
    total_readings: int
    last_updated: Optional[str] = None


class SensorSummaryResponse(BaseModel):
    summary: List[LineSummary]


@router.get("/data", response_model=SensorDataResponse)
async def get_sensor_data(
    db: Session = Depends(get_db),
    start_date: Optional[datetime] = Query(None, description="시작 날짜"),
    end_date: Optional[datetime] = Query(None, description="종료 날짜"),
    line_code: Optional[str] = Query(None, description="라인 코드"),
    sensor_type: Optional[str] = Query(None, description="센서 타입"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    page_size: int = Query(50, ge=1, le=200, description="페이지 크기"),
):
    """
    센서 데이터 조회 (PostgreSQL)

    필터링 옵션:
    - start_date: 시작 날짜
    - end_date: 종료 날짜
    - line_code: 생산 라인 코드 (LINE_A, LINE_B, etc.)
    - sensor_type: 센서 타입 (temperature, pressure, humidity, vibration, flow_rate)
    """
    # 기본값 설정
    if not end_date:
        end_date = datetime.utcnow()
    if not start_date:
        start_date = end_date - timedelta(days=1)

    # Base query
    query = db.query(SensorData).filter(
        SensorData.recorded_at >= start_date,
        SensorData.recorded_at <= end_date
    )

    # 필터 적용
    if line_code:
        query = query.filter(SensorData.line_code == line_code)
    if sensor_type:
        query = query.filter(SensorData.sensor_type == sensor_type)

    # Total count
    total = query.count()

    # 정렬 및 페이지네이션
    offset = (page - 1) * page_size
    data = query.order_by(SensorData.recorded_at.desc()).offset(offset).limit(page_size).all()

    # Response 변환
    items = [
        SensorDataItem(
            sensor_id=str(item.sensor_id),
            recorded_at=item.recorded_at,
            line_code=item.line_code,
            sensor_type=item.sensor_type,
            value=item.value,
            unit=item.unit
        )
        for item in data
    ]

    return SensorDataResponse(
        data=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/filters", response_model=SensorFilterOptions)
async def get_filter_options(db: Session = Depends(get_db)):
    """
    필터 옵션 조회 (DB에서 실제 사용 가능한 값 조회)

    사용 가능한 라인 코드와 센서 타입 목록을 반환합니다.
    """
    # DB에서 distinct 값 조회
    lines = db.query(distinct(SensorData.line_code)).all()
    sensor_types = db.query(distinct(SensorData.sensor_type)).all()

    line_list = [row[0] for row in lines if row[0]]
    sensor_type_list = [row[0] for row in sensor_types if row[0]]

    # DB에 데이터가 없으면 기본값 반환
    if not line_list:
        line_list = ["LINE_A", "LINE_B", "LINE_C", "LINE_D"]
    if not sensor_type_list:
        sensor_type_list = ["temperature", "pressure", "humidity", "vibration", "flow_rate"]

    return SensorFilterOptions(
        lines=sorted(line_list),
        sensor_types=sorted(sensor_type_list),
    )


@router.get("/summary", response_model=SensorSummaryResponse)
async def get_sensor_summary(
    db: Session = Depends(get_db),
    line_code: Optional[str] = Query(None, description="라인 코드"),
):
    """
    센서 데이터 요약 통계 (PostgreSQL)
    """
    # 최근 24시간 데이터 기준
    since = datetime.utcnow() - timedelta(hours=24)

    # Base query
    query = db.query(
        SensorData.line_code,
        SensorData.sensor_type,
        func.avg(SensorData.value).label("avg_value"),
        func.count(SensorData.sensor_id).label("count"),
        func.max(SensorData.recorded_at).label("last_recorded")
    ).filter(
        SensorData.recorded_at >= since
    )

    if line_code:
        query = query.filter(SensorData.line_code == line_code)

    # Group by line_code, sensor_type
    results = query.group_by(SensorData.line_code, SensorData.sensor_type).all()

    # 결과 집계 (line_code별로)
    line_stats = {}
    for row in results:
        lc = row.line_code
        if lc not in line_stats:
            line_stats[lc] = {
                "line_code": lc,
                "avg_temperature": None,
                "avg_pressure": None,
                "avg_humidity": None,
                "total_readings": 0,
                "last_updated": None,
            }

        # sensor_type별 평균값 저장
        if row.sensor_type == "temperature":
            line_stats[lc]["avg_temperature"] = round(row.avg_value, 1) if row.avg_value else None
        elif row.sensor_type == "pressure":
            line_stats[lc]["avg_pressure"] = round(row.avg_value, 2) if row.avg_value else None
        elif row.sensor_type == "humidity":
            line_stats[lc]["avg_humidity"] = round(row.avg_value, 1) if row.avg_value else None

        line_stats[lc]["total_readings"] += row.count

        # 최신 시간 업데이트
        if row.last_recorded:
            current_last = line_stats[lc]["last_updated"]
            row_time = row.last_recorded.isoformat()
            if not current_last or row_time > current_last:
                line_stats[lc]["last_updated"] = row_time

    # DB에 데이터가 없으면 빈 배열 반환
    summary = list(line_stats.values())

    return SensorSummaryResponse(summary=summary)
