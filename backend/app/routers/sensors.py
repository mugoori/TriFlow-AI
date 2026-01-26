"""
Sensor Data Router
센서 데이터 조회 API - PostgreSQL DB 연동 + WebSocket 실시간 스트리밍 + CSV/Excel Import

권한:
- sensors:read - 모든 역할 (viewer 이상) + Data Scope 필터
- sensors:create - operator 이상
- sensors:update - operator 이상
- sensors:delete - admin만
"""
import asyncio
import io
import json
import random
from datetime import datetime, timedelta
from typing import List, Optional, Set

import pandas as pd
from fastapi import APIRouter, Query, Depends, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, distinct, text
from sqlalchemy.orm import Session
from uuid import uuid4

from app.config import settings
from app.database import get_db
from app.models import SensorData, Tenant
from app.services.rbac_service import check_permission
from app.services.data_scope_service import DataScope, get_data_scope, apply_line_filter
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_or_create_tenant(db: Session) -> Tenant:
    """MVP용 기본 tenant 조회 또는 생성"""
    tenant = db.query(Tenant).first()
    if not tenant:
        tenant = Tenant(
            name=settings.default_tenant_name,
            slug="default",
            settings={},
        )
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
    return tenant


# 이미 생성된 파티션을 추적하여 중복 확인 방지
_created_partitions: set = set()


def _ensure_partition_exists(db: Session, recorded_at: datetime) -> None:
    """해당 월의 파티션이 없으면 자동 생성"""
    year = recorded_at.year
    month = recorded_at.month

    partition_name = f"sensor_data_{year}_{month:02d}"

    # 이미 이 세션에서 생성한 파티션이면 스킵
    if partition_name in _created_partitions:
        return

    # 다음 달 계산
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    start_date = f"{year}-{month:02d}-01"
    end_date = f"{next_year}-{next_month:02d}-01"

    try:
        # 파티션 존재 여부 확인
        check_sql = text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'core' AND c.relname = :partition_name
            )
        """)
        result = db.execute(check_sql, {"partition_name": partition_name})
        exists = result.scalar()

        if not exists:
            # 파티션 생성
            create_sql = text(f"""
                CREATE TABLE IF NOT EXISTS core.{partition_name}
                PARTITION OF core.sensor_data
                FOR VALUES FROM ('{start_date}') TO ('{end_date}')
            """)
            db.execute(create_sql)
            db.commit()

        # 생성된 파티션 기록
        _created_partitions.add(partition_name)
    except Exception as e:
        # 이미 존재하는 경우 무시 (동시 생성 시 발생할 수 있음)
        if "already exists" in str(e).lower():
            _created_partitions.add(partition_name)
        else:
            raise

# 연결된 WebSocket 클라이언트 관리
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._streaming_task: Optional[asyncio.Task] = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, message: dict):
        """모든 연결된 클라이언트에 메시지 전송"""
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.add(connection)
        # 끊어진 연결 정리
        self.active_connections -= disconnected

manager = ConnectionManager()


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


# 기본값 상수
DEFAULT_LINES = ["LINE_A", "LINE_B", "LINE_C", "LINE_D"]
DEFAULT_SENSOR_TYPES = ["temperature", "pressure", "humidity", "vibration", "flow_rate"]


@router.get("/data", response_model=SensorDataResponse)
async def get_sensor_data(
    db: Session = Depends(get_db),
    scope: DataScope = Depends(get_data_scope),
    start_date: Optional[datetime] = Query(None, description="시작 날짜"),
    end_date: Optional[datetime] = Query(None, description="종료 날짜"),
    line_code: Optional[str] = Query(None, description="라인 코드"),
    sensor_type: Optional[str] = Query(None, description="센서 타입"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    page_size: int = Query(50, ge=1, le=200, description="페이지 크기"),
    _: None = Depends(check_permission("sensors", "read")),
):
    """
    센서 데이터 조회 (PostgreSQL)

    필터링 옵션:
    - start_date: 시작 날짜
    - end_date: 종료 날짜
    - line_code: 생산 라인 코드 (LINE_A, LINE_B, etc.)
    - sensor_type: 센서 타입 (temperature, pressure, humidity, vibration, flow_rate)
    """
    try:
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

        # Data Scope 필터 적용
        query = apply_line_filter(query, scope, SensorData.line_code)

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
    except Exception:
        # DB 연결 실패 시 빈 데이터 반환
        return SensorDataResponse(
            data=[],
            total=0,
            page=page,
            page_size=page_size,
        )


@router.get("/filters", response_model=SensorFilterOptions)
async def get_filter_options(
    db: Session = Depends(get_db),
    scope: DataScope = Depends(get_data_scope),
    _: None = Depends(check_permission("sensors", "read")),
):
    """
    필터 옵션 조회 (DB에서 실제 사용 가능한 값 조회)

    사용 가능한 라인 코드와 센서 타입 목록을 반환합니다.
    Data Scope에 따라 접근 가능한 라인만 반환합니다.
    """
    try:
        # DB에서 distinct 값 조회
        lines = db.query(distinct(SensorData.line_code)).all()
        sensor_types = db.query(distinct(SensorData.sensor_type)).all()

        line_list = [row[0] for row in lines if row[0]]
        sensor_type_list = [row[0] for row in sensor_types if row[0]]

        # DB에 데이터가 없으면 기본값 반환
        if not line_list:
            line_list = DEFAULT_LINES
        if not sensor_type_list:
            sensor_type_list = DEFAULT_SENSOR_TYPES

        # Data Scope 필터 적용 (접근 가능한 라인만)
        if not scope.all_access and scope.line_codes:
            line_list = [line for line in line_list if line in scope.line_codes]

        return SensorFilterOptions(
            lines=sorted(line_list),
            sensor_types=sorted(sensor_type_list),
        )
    except Exception:
        # DB 연결 실패 시 기본값 반환 (Data Scope 적용)
        lines = DEFAULT_LINES
        if not scope.all_access and scope.line_codes:
            lines = [line for line in lines if line in scope.line_codes]
        return SensorFilterOptions(
            lines=lines,
            sensor_types=DEFAULT_SENSOR_TYPES,
        )


@router.get("/summary", response_model=SensorSummaryResponse)
async def get_sensor_summary(
    db: Session = Depends(get_db),
    scope: DataScope = Depends(get_data_scope),
    line_code: Optional[str] = Query(None, description="라인 코드"),
    _: None = Depends(check_permission("sensors", "read")),
):
    """
    센서 데이터 요약 통계 (PostgreSQL)
    Data Scope에 따라 접근 가능한 라인만 반환합니다.
    """
    try:
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

        # Data Scope 필터 적용
        query = apply_line_filter(query, scope, SensorData.line_code)

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
    except Exception:
        # DB 연결 실패 시 빈 배열 반환
        return SensorSummaryResponse(summary=[])


# ==================== WebSocket 실시간 스트리밍 ====================

def generate_simulated_sensor_data() -> dict:
    """
    시뮬레이션용 센서 데이터 생성

    실제 환경에서는 DB에서 최신 데이터를 조회하거나
    MQTT/Kafka 등의 메시지 브로커에서 데이터를 수신
    """
    lines = DEFAULT_LINES
    sensor_types = {
        "temperature": {"min": 20, "max": 100, "unit": "C"},
        "pressure": {"min": 0.8, "max": 2.5, "unit": "bar"},
        "humidity": {"min": 30, "max": 80, "unit": "%"},
        "vibration": {"min": 0, "max": 100, "unit": "Hz"},
        "flow_rate": {"min": 50, "max": 200, "unit": "L/min"},
    }

    data = []
    timestamp = datetime.utcnow().isoformat()

    for line in lines:
        for sensor_type, config in sensor_types.items():
            # 랜덤 값 생성 (정규 분포 근사)
            mid = (config["max"] + config["min"]) / 2
            spread = (config["max"] - config["min"]) / 4
            value = random.gauss(mid, spread)
            value = max(config["min"], min(config["max"], value))  # 범위 제한

            # 가끔 이상치 발생 (5% 확률)
            if random.random() < 0.05:
                if random.random() < 0.5:
                    value = config["max"] * 1.1  # 상한 초과
                else:
                    value = config["min"] * 0.9  # 하한 미달

            data.append({
                "sensor_id": f"{line}_{sensor_type}",
                "line_code": line,
                "sensor_type": sensor_type,
                "value": round(value, 2),
                "unit": config["unit"],
                "recorded_at": timestamp,
            })

    return {
        "type": "sensor_update",
        "timestamp": timestamp,
        "data": data,
    }


@router.websocket("/stream")
async def websocket_sensor_stream(websocket: WebSocket):
    """
    실시간 센서 데이터 WebSocket 스트리밍

    연결 후 1초 간격으로 센서 데이터 전송
    클라이언트는 'subscribe' 메시지로 특정 라인/센서만 구독 가능

    사용 예시:
    ```javascript
    const ws = new WebSocket('ws://localhost:8000/api/v1/sensors/stream');
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('Sensor data:', data);
    };

    // 특정 라인만 구독
    ws.send(JSON.stringify({
        type: 'subscribe',
        filters: { lines: ['LINE_A', 'LINE_B'] }
    }));
    ```
    """
    await manager.connect(websocket)

    # 클라이언트별 필터 설정
    filters = {
        "lines": None,  # None = 전체
        "sensor_types": None,
    }

    try:
        # 연결 확인 메시지
        await websocket.send_json({
            "type": "connected",
            "message": "WebSocket connected to sensor stream",
            "available_lines": DEFAULT_LINES,
            "available_sensor_types": DEFAULT_SENSOR_TYPES,
        })

        while True:
            # 1. 클라이언트 메시지 확인 (non-blocking)
            try:
                # 짧은 타임아웃으로 메시지 확인
                raw_data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=0.1
                )
                message = json.loads(raw_data)

                # 구독 필터 업데이트
                if message.get("type") == "subscribe":
                    msg_filters = message.get("filters", {})
                    if "lines" in msg_filters:
                        filters["lines"] = msg_filters["lines"]
                    if "sensor_types" in msg_filters:
                        filters["sensor_types"] = msg_filters["sensor_types"]

                    await websocket.send_json({
                        "type": "subscribed",
                        "filters": filters,
                    })

            except asyncio.TimeoutError:
                pass  # 타임아웃 - 메시지 없음
            except json.JSONDecodeError:
                pass  # 잘못된 JSON 무시

            # 2. 센서 데이터 전송
            sensor_data = generate_simulated_sensor_data()

            # 필터 적용
            if filters["lines"]:
                sensor_data["data"] = [
                    d for d in sensor_data["data"]
                    if d["line_code"] in filters["lines"]
                ]
            if filters["sensor_types"]:
                sensor_data["data"] = [
                    d for d in sensor_data["data"]
                    if d["sensor_type"] in filters["sensor_types"]
                ]

            await websocket.send_json(sensor_data)

            # 1초 대기
            await asyncio.sleep(1)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


@router.get("/stream/status")
async def get_stream_status():
    """
    WebSocket 스트림 상태 조회
    """
    return {
        "active_connections": len(manager.active_connections),
        "websocket_url": "/api/v1/sensors/stream",
    }


# ==================== CSV/Excel Import ====================

class ImportResult(BaseModel):
    success: bool
    message: str
    total_rows: int
    imported_rows: int
    failed_rows: int
    errors: List[str] = []


@router.post("/import", response_model=ImportResult)
async def import_sensor_data(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: None = Depends(check_permission("sensors", "create")),
):
    """
    CSV/Excel 파일에서 센서 데이터 Import (operator 이상)

    지원 파일 형식:
    - CSV (.csv)
    - Excel (.xlsx, .xls)

    필수 컬럼:
    - line_code: 생산 라인 코드 (예: LINE_A)
    - sensor_type: 센서 타입 (예: temperature)
    - value: 센서 값 (숫자)

    선택 컬럼:
    - recorded_at: 기록 시간 (ISO 형식, 없으면 현재 시간)
    - unit: 단위 (예: C, %, bar)

    예시 CSV:
    ```
    line_code,sensor_type,value,unit,recorded_at
    LINE_A,temperature,75.5,C,2024-01-15T10:30:00
    LINE_B,pressure,1.2,bar,
    ```
    """
    logger.info(f"CSV import started: filename={file.filename}")
    errors = []
    imported_rows = 0
    failed_rows = 0

    # 파일 확장자 확인
    filename = file.filename or ""
    if not filename.lower().endswith(('.csv', '.xlsx', '.xls')):
        raise HTTPException(
            status_code=400,
            detail="지원하지 않는 파일 형식입니다. CSV 또는 Excel 파일을 업로드하세요."
        )

    try:
        logger.info("Reading file content...")
        # 파일 읽기
        content = await file.read()
        logger.info(f"File read: {len(content)} bytes")

        # 파일 형식에 따라 DataFrame 로드
        if filename.lower().endswith('.csv'):
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))

        total_rows = len(df)

        # 필수 컬럼 확인
        required_columns = ['line_code', 'sensor_type', 'value']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise HTTPException(
                status_code=400,
                detail=f"필수 컬럼이 누락되었습니다: {', '.join(missing_columns)}"
            )

        # tenant_id 가져오기
        tenant = _get_or_create_tenant(db)

        # 데이터 정제 및 삽입
        for idx, row in df.iterrows():
            try:
                # 값 추출
                line_code = str(row['line_code']).strip()
                sensor_type = str(row['sensor_type']).strip()
                value = float(row['value'])

                # 선택 값
                unit = str(row.get('unit', '')).strip() if pd.notna(row.get('unit')) else None
                recorded_at = None
                if 'recorded_at' in df.columns and pd.notna(row.get('recorded_at')):
                    try:
                        recorded_at = pd.to_datetime(row['recorded_at']).to_pydatetime()
                    except Exception:
                        recorded_at = datetime.utcnow()
                else:
                    recorded_at = datetime.utcnow()

                # 유효성 검사
                if not line_code or not sensor_type:
                    raise ValueError("line_code와 sensor_type은 필수입니다")

                # 파티션 자동 생성 (해당 월 파티션이 없으면 생성)
                _ensure_partition_exists(db, recorded_at)

                # DB 삽입 - 파티션 테이블이므로 raw SQL 사용
                db.execute(
                    text("""
                        INSERT INTO core.sensor_data
                        (sensor_id, tenant_id, line_code, sensor_type, value, unit, recorded_at)
                        VALUES (:sensor_id, :tenant_id, :line_code, :sensor_type, :value, :unit, :recorded_at)
                    """),
                    {
                        "sensor_id": str(uuid4()),
                        "tenant_id": str(tenant.tenant_id),
                        "line_code": line_code,
                        "sensor_type": sensor_type,
                        "value": value,
                        "unit": unit,
                        "recorded_at": recorded_at,
                    }
                )
                imported_rows += 1

            except Exception as e:
                failed_rows += 1
                if len(errors) < 10:  # 최대 10개 에러만 기록
                    errors.append(f"Row {idx + 2}: {str(e)}")

        # 커밋
        if imported_rows > 0:
            db.commit()

        return ImportResult(
            success=failed_rows == 0,
            message=f"{imported_rows}개 행 import 완료" + (f", {failed_rows}개 실패" if failed_rows > 0 else ""),
            total_rows=total_rows,
            imported_rows=imported_rows,
            failed_rows=failed_rows,
            errors=errors,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CSV import error: {type(e).__name__}: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"파일 처리 중 오류 발생: {str(e)}"
        )


@router.get("/import/template")
async def get_import_template():
    """
    Import용 템플릿 CSV 다운로드

    Returns:
        CSV 템플릿 파일 내용
    """
    template = """line_code,sensor_type,value,unit,recorded_at
LINE_A,temperature,75.5,C,2024-01-15T10:30:00
LINE_A,pressure,1.2,bar,2024-01-15T10:30:00
LINE_A,humidity,45.0,%,2024-01-15T10:30:00
LINE_B,temperature,72.3,C,2024-01-15T10:30:00
LINE_B,vibration,23.5,Hz,2024-01-15T10:30:00
"""
    from fastapi.responses import Response
    return Response(
        content=template,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=sensor_import_template.csv"
        }
    )
