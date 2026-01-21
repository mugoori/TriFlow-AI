"""
데이터 동기화 스케줄러 서비스
- 센서 데이터 자동 수집
- 외부 시스템 연동 (ERP/MES)
- 주기적 정리 작업
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DISABLED = "disabled"


@dataclass
class ScheduledJob:
    """스케줄된 작업 정의"""
    job_id: str
    name: str
    description: str
    interval_seconds: int
    handler: Callable
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    status: JobStatus = JobStatus.IDLE
    run_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class SchedulerService:
    """
    데이터 동기화 스케줄러

    주요 기능:
    - 주기적 센서 데이터 시뮬레이션 생성
    - 오래된 데이터 정리
    - 외부 시스템 데이터 동기화 (확장 가능)
    """

    def __init__(self):
        self._jobs: Dict[str, ScheduledJob] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._check_interval = 1  # 1초마다 체크

    def register_job(
        self,
        job_id: str,
        name: str,
        description: str,
        interval_seconds: int,
        handler: Callable,
        enabled: bool = True,
    ) -> None:
        """작업 등록"""
        job = ScheduledJob(
            job_id=job_id,
            name=name,
            description=description,
            interval_seconds=interval_seconds,
            handler=handler,
            enabled=enabled,
            next_run=datetime.utcnow() if enabled else None,
        )
        self._jobs[job_id] = job
        logger.info(f"Registered job: {job_id} (interval: {interval_seconds}s)")

    def unregister_job(self, job_id: str) -> bool:
        """작업 해제"""
        if job_id in self._jobs:
            del self._jobs[job_id]
            logger.info(f"Unregistered job: {job_id}")
            return True
        return False

    def enable_job(self, job_id: str) -> bool:
        """작업 활성화"""
        if job_id in self._jobs:
            self._jobs[job_id].enabled = True
            self._jobs[job_id].status = JobStatus.IDLE
            self._jobs[job_id].next_run = datetime.utcnow()
            return True
        return False

    def disable_job(self, job_id: str) -> bool:
        """작업 비활성화"""
        if job_id in self._jobs:
            self._jobs[job_id].enabled = False
            self._jobs[job_id].status = JobStatus.DISABLED
            self._jobs[job_id].next_run = None
            return True
        return False

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """작업 상태 조회"""
        if job_id not in self._jobs:
            return None
        job = self._jobs[job_id]
        return {
            "job_id": job.job_id,
            "name": job.name,
            "description": job.description,
            "interval_seconds": job.interval_seconds,
            "enabled": job.enabled,
            "status": job.status.value,
            "last_run": job.last_run.isoformat() if job.last_run else None,
            "next_run": job.next_run.isoformat() if job.next_run else None,
            "run_count": job.run_count,
            "error_count": job.error_count,
            "last_error": job.last_error,
        }

    def get_all_jobs(self) -> List[Dict[str, Any]]:
        """모든 작업 상태 조회"""
        return [self.get_job_status(job_id) for job_id in self._jobs]

    async def start(self) -> None:
        """스케줄러 시작"""
        if self._running:
            logger.warning("Scheduler is already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Scheduler started")

    async def stop(self) -> None:
        """스케줄러 중지"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Scheduler stopped")

    async def _run_loop(self) -> None:
        """메인 스케줄러 루프"""
        while self._running:
            try:
                now = datetime.utcnow()

                for job in self._jobs.values():
                    if not job.enabled:
                        continue
                    if job.status == JobStatus.RUNNING:
                        continue
                    if job.next_run and job.next_run <= now:
                        # 작업 실행
                        asyncio.create_task(self._execute_job(job))

                await asyncio.sleep(self._check_interval)

            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                await asyncio.sleep(self._check_interval)

    async def _execute_job(self, job: ScheduledJob) -> None:
        """개별 작업 실행"""
        job.status = JobStatus.RUNNING
        job.last_run = datetime.utcnow()

        try:
            # 핸들러가 async인지 확인
            if asyncio.iscoroutinefunction(job.handler):
                await job.handler()
            else:
                job.handler()

            job.status = JobStatus.COMPLETED
            job.run_count += 1
            logger.debug(f"Job {job.job_id} completed successfully")

        except Exception as e:
            job.status = JobStatus.FAILED
            job.error_count += 1
            job.last_error = str(e)
            logger.error(f"Job {job.job_id} failed: {e}")

        finally:
            # 다음 실행 시간 설정
            job.next_run = datetime.utcnow() + timedelta(seconds=job.interval_seconds)
            job.status = JobStatus.IDLE

    async def run_job_now(self, job_id: str) -> bool:
        """작업 즉시 실행"""
        if job_id not in self._jobs:
            return False
        job = self._jobs[job_id]
        if job.status == JobStatus.RUNNING:
            return False
        asyncio.create_task(self._execute_job(job))
        return True


# 기본 작업 핸들러들

async def cleanup_old_sensor_data():
    """
    오래된 센서 데이터 정리 (30일 이상)
    """
    from app.database import SessionLocal
    from app.models import SensorData

    try:
        db = SessionLocal()
        cutoff = datetime.utcnow() - timedelta(days=30)
        deleted = db.query(SensorData).filter(SensorData.recorded_at < cutoff).delete()
        db.commit()
        logger.info(f"Cleaned up {deleted} old sensor records")
    except Exception as e:
        logger.error(f"Failed to cleanup old sensor data: {e}")
    finally:
        db.close()


async def generate_sample_sensor_data():
    """
    샘플 센서 데이터 생성 (시뮬레이션용)
    """
    import random
    from app.database import SessionLocal
    from app.models import SensorData

    lines = ["LINE_A", "LINE_B", "LINE_C", "LINE_D"]
    sensor_types = {
        "temperature": {"min": 20, "max": 100, "unit": "C"},
        "pressure": {"min": 0.8, "max": 2.5, "unit": "bar"},
        "humidity": {"min": 30, "max": 80, "unit": "%"},
    }

    try:
        db = SessionLocal()
        now = datetime.utcnow()

        for line in lines:
            for sensor_type, config in sensor_types.items():
                value = random.uniform(config["min"], config["max"])
                sensor_data = SensorData(
                    line_code=line,
                    sensor_type=sensor_type,
                    value=round(value, 2),
                    unit=config["unit"],
                    recorded_at=now,
                )
                db.add(sensor_data)

        db.commit()
        logger.debug(f"Generated {len(lines) * len(sensor_types)} sample sensor records")
    except Exception as e:
        logger.error(f"Failed to generate sample sensor data: {e}")
    finally:
        db.close()


async def auto_extract_samples_from_feedback():
    """피드백에서 샘플 자동 추출 (설정된 주기마다)"""
    from app.database import SessionLocal
    from app.services.sample_curation_service import SampleCurationService
    from app.services.settings_service import settings_service

    try:
        # 설정 확인
        enabled = settings_service.get_setting("learning_auto_extract_enabled")
        if enabled != "true":
            logger.debug("Auto sample extraction is disabled")
            return

        db = SessionLocal()
        service = SampleCurationService(db)

        # 활성 테넌트 조회
        from app.models import Tenant
        tenants = db.query(Tenant).filter(Tenant.is_active is True).all()

        total_extracted = 0
        for tenant in tenants:
            try:
                samples, _ = service.extract_samples_from_feedback(
                    tenant_id=tenant.tenant_id,
                    request={"days": 1, "dry_run": False}
                )
                total_extracted += len(samples)
                logger.info(f"Extracted {len(samples)} samples for tenant {tenant.tenant_id}")
            except Exception as e:
                logger.error(f"Failed to extract samples for tenant {tenant.tenant_id}: {e}")

        logger.info(f"Auto-extracted {total_extracted} samples across all tenants")
    except Exception as e:
        logger.error(f"Failed to auto-extract samples: {e}")
    finally:
        db.close()


async def auto_update_golden_sets():
    """골든 샘플셋 자동 업데이트"""
    from app.database import SessionLocal
    from app.services.golden_sample_set_service import GoldenSampleSetService
    from app.services.settings_service import settings_service

    try:
        # 설정 확인
        enabled = settings_service.get_setting("learning_golden_set_auto_update")
        if enabled != "true":
            logger.debug("Golden set auto-update is disabled")
            return

        db = SessionLocal()
        service = GoldenSampleSetService(db)

        # 활성 골든셋 조회
        from app.models import GoldenSampleSet
        active_sets = db.query(GoldenSampleSet).filter(
            GoldenSampleSet.is_active is True
        ).all()

        total_updated = 0
        for sample_set in active_sets:
            try:
                result = service.auto_update_set(
                    set_id=sample_set.set_id,
                    request=None  # Use defaults
                )
                if result["added_count"] > 0 or result["removed_count"] > 0:
                    total_updated += 1
                    logger.info(
                        f"Updated golden set {sample_set.set_id}: "
                        f"+{result['added_count']}, -{result['removed_count']}"
                    )
            except Exception as e:
                logger.error(f"Failed to update golden set {sample_set.set_id}: {e}")

        logger.info(f"Auto-updated {total_updated} golden sets")
    except Exception as e:
        logger.error(f"Failed to auto-update golden sets: {e}")
    finally:
        db.close()


# 싱글톤 인스턴스
scheduler = SchedulerService()


def setup_default_jobs():
    """기본 스케줄 작업 등록"""
    from app.services.mv_refresh_service import refresh_materialized_views
    from app.services.metrics_exporter import update_business_metrics

    # 비즈니스 메트릭 업데이트 (1분마다)
    scheduler.register_job(
        job_id="update_business_metrics",
        name="비즈니스 메트릭 업데이트",
        description="DB 데이터를 Prometheus 메트릭으로 변환",
        interval_seconds=60,  # 1분
        handler=update_business_metrics,
        enabled=True,
    )

    # 데이터 정리 (매일 자정)
    scheduler.register_job(
        job_id="cleanup_old_data",
        name="센서 데이터 정리",
        description="30일 이상 된 센서 데이터 삭제",
        interval_seconds=86400,  # 24시간
        handler=cleanup_old_sensor_data,
        enabled=True,
    )

    # 샘플 데이터 생성 (5분마다) - 개발/데모용
    scheduler.register_job(
        job_id="generate_sample_data",
        name="샘플 데이터 생성",
        description="시뮬레이션용 센서 데이터 생성",
        interval_seconds=300,  # 5분
        handler=generate_sample_sensor_data,
        enabled=False,  # 기본 비활성화
    )

    # Materialized View 리프레시 (30분마다)
    scheduler.register_job(
        job_id="refresh_materialized_views",
        name="MV 리프레시",
        description="대시보드 Materialized Views 리프레시",
        interval_seconds=1800,  # 30분
        handler=refresh_materialized_views,
        enabled=True,
    )

    # Sample auto-extraction (6시간 간격)
    scheduler.register_job(
        job_id="auto_extract_samples",
        name="샘플 자동 추출",
        description="피드백에서 학습 샘플 자동 추출",
        interval_seconds=21600,  # 6 hours
        handler=auto_extract_samples_from_feedback,
        enabled=False,  # 설정에서 활성화
    )

    # Golden set auto-update (24시간 간격)
    scheduler.register_job(
        job_id="auto_update_golden_sets",
        name="골든셋 자동 업데이트",
        description="골든 샘플셋 자동 업데이트",
        interval_seconds=86400,  # 24 hours
        handler=auto_update_golden_sets,
        enabled=False,  # 설정에서 활성화
    )
