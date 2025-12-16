"""
현재 시간 기준으로 샘플 센서 데이터 생성
JudgmentAgent 테스트용
"""
import os
import sys
from datetime import datetime, timedelta
from uuid import uuid4
import random

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models import Tenant, SensorData

def generate_sample_data():
    """현재 시간 기준으로 최근 2시간치 센서 데이터 생성"""
    db = SessionLocal()

    try:
        # Default 테넌트 조회
        tenant = db.query(Tenant).filter(Tenant.name == "Default").first()
        if not tenant:
            print("Default tenant not found!")
            return

        print(f"Tenant: {tenant.tenant_id}")

        # LINE_A, LINE_B 센서 설정
        lines = ["LINE_A", "LINE_B"]
        sensor_types = [
            ("temperature", "°C", 20, 80),
            ("pressure", "bar", 1, 10),
            ("vibration", "mm/s", 0, 5),
            ("humidity", "%", 30, 90),
        ]

        # 최근 2시간 데이터 생성 (5분 간격)
        now = datetime.utcnow()
        start_time = now - timedelta(hours=2)

        data_count = 0
        current_time = start_time

        while current_time <= now:
            for line in lines:
                for sensor_type, unit, min_val, max_val in sensor_types:
                    # 랜덤 값 생성 (정상 범위 내)
                    value = round(random.uniform(min_val, max_val), 2)

                    # 일부 데이터는 경고/위험 수준으로
                    if random.random() < 0.1:  # 10% 확률로 높은 값
                        value = round(random.uniform(max_val * 0.9, max_val * 1.1), 2)

                    data = SensorData(
                        sensor_id=uuid4(),
                        tenant_id=tenant.tenant_id,
                        line_code=line,
                        sensor_type=sensor_type,
                        value=value,
                        unit=unit,
                        recorded_at=current_time,
                        sensor_metadata={"line": line, "type": sensor_type}
                    )
                    db.add(data)
                    data_count += 1

            current_time += timedelta(minutes=5)

        db.commit()
        print(f"\nGenerated {data_count} sensor data points")
        print(f"Time range: {start_time} ~ {now}")

        # 확인
        recent_data = db.query(SensorData).filter(
            SensorData.recorded_at >= now - timedelta(hours=1)
        ).count()
        print(f"Data in last 1 hour: {recent_data} records")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    generate_sample_data()
