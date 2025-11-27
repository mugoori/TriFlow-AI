"""
Sensor Data Router
센서 데이터 조회 API
"""
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

router = APIRouter()


# Response Models
class SensorDataItem(BaseModel):
    sensor_id: str
    recorded_at: datetime
    line_code: str
    sensor_type: str
    value: float
    unit: Optional[str] = None


class SensorDataResponse(BaseModel):
    data: List[SensorDataItem]
    total: int
    page: int
    page_size: int


class SensorFilterOptions(BaseModel):
    lines: List[str]
    sensor_types: List[str]


# Mock 데이터 생성 함수
def generate_mock_sensor_data(
    start_date: datetime,
    end_date: datetime,
    line_code: Optional[str] = None,
    sensor_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 50
) -> tuple[List[dict], int]:
    """Mock 센서 데이터 생성"""
    import random

    lines = ["LINE_A", "LINE_B", "LINE_C", "LINE_D"]
    sensor_types_map = {
        "temperature": {"unit": "°C", "min": 20, "max": 80},
        "pressure": {"unit": "bar", "min": 1, "max": 10},
        "humidity": {"unit": "%", "min": 30, "max": 90},
        "vibration": {"unit": "mm/s", "min": 0, "max": 5},
        "flow_rate": {"unit": "L/min", "min": 10, "max": 100},
    }

    # 필터링
    if line_code:
        lines = [line_code] if line_code in lines else lines

    sensor_types_list = list(sensor_types_map.keys())
    if sensor_type:
        sensor_types_list = [sensor_type] if sensor_type in sensor_types_map else sensor_types_list

    # 데이터 생성
    all_data = []
    current = start_date
    sensor_counter = 1

    while current <= end_date:
        for line in lines:
            for st in sensor_types_list:
                config = sensor_types_map[st]
                value = round(random.uniform(config["min"], config["max"]), 2)

                all_data.append({
                    "sensor_id": f"SENSOR_{sensor_counter:05d}",
                    "recorded_at": current,
                    "line_code": line,
                    "sensor_type": st,
                    "value": value,
                    "unit": config["unit"],
                })
                sensor_counter += 1

        current += timedelta(hours=1)

    # 페이지네이션
    total = len(all_data)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_data = all_data[start_idx:end_idx]

    return paginated_data, total


@router.get("/data", response_model=SensorDataResponse)
async def get_sensor_data(
    start_date: Optional[datetime] = Query(None, description="시작 날짜"),
    end_date: Optional[datetime] = Query(None, description="종료 날짜"),
    line_code: Optional[str] = Query(None, description="라인 코드"),
    sensor_type: Optional[str] = Query(None, description="센서 타입"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    page_size: int = Query(50, ge=1, le=200, description="페이지 크기"),
):
    """
    센서 데이터 조회

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

    # Mock 데이터 사용 (실제 환경에서는 DB 조회)
    data, total = generate_mock_sensor_data(
        start_date=start_date,
        end_date=end_date,
        line_code=line_code,
        sensor_type=sensor_type,
        page=page,
        page_size=page_size,
    )

    return SensorDataResponse(
        data=[SensorDataItem(**item) for item in data],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/filters", response_model=SensorFilterOptions)
async def get_filter_options():
    """
    필터 옵션 조회

    사용 가능한 라인 코드와 센서 타입 목록을 반환합니다.
    """
    return SensorFilterOptions(
        lines=["LINE_A", "LINE_B", "LINE_C", "LINE_D"],
        sensor_types=["temperature", "pressure", "humidity", "vibration", "flow_rate"],
    )


@router.get("/summary")
async def get_sensor_summary(
    line_code: Optional[str] = Query(None, description="라인 코드"),
):
    """
    센서 데이터 요약 통계
    """
    import random

    lines = ["LINE_A", "LINE_B", "LINE_C", "LINE_D"]
    if line_code:
        lines = [line_code] if line_code in lines else lines

    summary = []
    for line in lines:
        summary.append({
            "line_code": line,
            "avg_temperature": round(random.uniform(35, 55), 1),
            "avg_pressure": round(random.uniform(3, 7), 2),
            "avg_humidity": round(random.uniform(45, 65), 1),
            "total_readings": random.randint(1000, 5000),
            "last_updated": datetime.utcnow().isoformat(),
        })

    return {"summary": summary}
