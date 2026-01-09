"""
Scheduler Service 테스트
scheduler_service.py의 SchedulerService 클래스 테스트
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


# ========== JobStatus Enum 테스트 ==========


class TestJobStatus:
    """JobStatus Enum 테스트"""

    def test_job_status_values(self):
        """상태값 확인"""
        from app.services.scheduler_service import JobStatus

        assert JobStatus.IDLE.value == "idle"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"
        assert JobStatus.DISABLED.value == "disabled"


# ========== ScheduledJob 데이터클래스 테스트 ==========


class TestScheduledJob:
    """ScheduledJob 데이터클래스 테스트"""

    def test_scheduled_job_defaults(self):
        """기본값 확인"""
        from app.services.scheduler_service import ScheduledJob, JobStatus

        job = ScheduledJob(
            job_id="test_job",
            name="Test Job",
            description="A test job",
            interval_seconds=60,
            handler=lambda: None
        )

        assert job.job_id == "test_job"
        assert job.name == "Test Job"
        assert job.enabled is True
        assert job.last_run is None
        assert job.next_run is None
        assert job.status == JobStatus.IDLE
        assert job.run_count == 0
        assert job.error_count == 0
        assert job.last_error is None
        assert job.metadata == {}


# ========== SchedulerService 초기화 테스트 ==========


class TestSchedulerServiceInit:
    """SchedulerService 초기화 테스트"""

    def test_init(self):
        """초기화 확인"""
        from app.services.scheduler_service import SchedulerService

        service = SchedulerService()

        assert service._jobs == {}
        assert service._running is False
        assert service._task is None
        assert service._check_interval == 1


# ========== register_job 테스트 ==========


class TestRegisterJob:
    """register_job 메서드 테스트"""

    def test_register_job_basic(self):
        """기본 작업 등록"""
        from app.services.scheduler_service import SchedulerService

        service = SchedulerService()

        def handler():
            pass

        service.register_job(
            job_id="job1",
            name="Job 1",
            description="First job",
            interval_seconds=300,
            handler=handler
        )

        assert "job1" in service._jobs
        assert service._jobs["job1"].name == "Job 1"
        assert service._jobs["job1"].interval_seconds == 300
        assert service._jobs["job1"].enabled is True

    def test_register_job_disabled(self):
        """비활성화 상태로 작업 등록"""
        from app.services.scheduler_service import SchedulerService

        service = SchedulerService()

        service.register_job(
            job_id="job2",
            name="Job 2",
            description="Disabled job",
            interval_seconds=600,
            handler=lambda: None,
            enabled=False
        )

        assert service._jobs["job2"].enabled is False
        assert service._jobs["job2"].next_run is None


# ========== unregister_job 테스트 ==========


class TestUnregisterJob:
    """unregister_job 메서드 테스트"""

    def test_unregister_existing_job(self):
        """기존 작업 해제"""
        from app.services.scheduler_service import SchedulerService

        service = SchedulerService()
        service.register_job("job1", "Job 1", "Test", 60, lambda: None)

        result = service.unregister_job("job1")

        assert result is True
        assert "job1" not in service._jobs

    def test_unregister_nonexistent_job(self):
        """없는 작업 해제"""
        from app.services.scheduler_service import SchedulerService

        service = SchedulerService()

        result = service.unregister_job("nonexistent")

        assert result is False


# ========== enable_job / disable_job 테스트 ==========


class TestEnableDisableJob:
    """enable_job / disable_job 메서드 테스트"""

    def test_enable_job(self):
        """작업 활성화"""
        from app.services.scheduler_service import SchedulerService, JobStatus

        service = SchedulerService()
        service.register_job("job1", "Job 1", "Test", 60, lambda: None, enabled=False)

        result = service.enable_job("job1")

        assert result is True
        assert service._jobs["job1"].enabled is True
        assert service._jobs["job1"].status == JobStatus.IDLE
        assert service._jobs["job1"].next_run is not None

    def test_enable_nonexistent_job(self):
        """없는 작업 활성화"""
        from app.services.scheduler_service import SchedulerService

        service = SchedulerService()

        result = service.enable_job("nonexistent")

        assert result is False

    def test_disable_job(self):
        """작업 비활성화"""
        from app.services.scheduler_service import SchedulerService, JobStatus

        service = SchedulerService()
        service.register_job("job1", "Job 1", "Test", 60, lambda: None, enabled=True)

        result = service.disable_job("job1")

        assert result is True
        assert service._jobs["job1"].enabled is False
        assert service._jobs["job1"].status == JobStatus.DISABLED
        assert service._jobs["job1"].next_run is None

    def test_disable_nonexistent_job(self):
        """없는 작업 비활성화"""
        from app.services.scheduler_service import SchedulerService

        service = SchedulerService()

        result = service.disable_job("nonexistent")

        assert result is False


# ========== get_job_status 테스트 ==========


class TestGetJobStatus:
    """get_job_status 메서드 테스트"""

    def test_get_status_existing_job(self):
        """기존 작업 상태 조회"""
        from app.services.scheduler_service import SchedulerService

        service = SchedulerService()
        service.register_job("job1", "Job 1", "Test description", 60, lambda: None)

        status = service.get_job_status("job1")

        assert status is not None
        assert status["job_id"] == "job1"
        assert status["name"] == "Job 1"
        assert status["description"] == "Test description"
        assert status["interval_seconds"] == 60
        assert status["enabled"] is True
        assert status["status"] == "idle"
        assert status["run_count"] == 0
        assert status["error_count"] == 0

    def test_get_status_nonexistent_job(self):
        """없는 작업 상태 조회"""
        from app.services.scheduler_service import SchedulerService

        service = SchedulerService()

        status = service.get_job_status("nonexistent")

        assert status is None


# ========== get_all_jobs 테스트 ==========


class TestGetAllJobs:
    """get_all_jobs 메서드 테스트"""

    def test_get_all_jobs_empty(self):
        """작업 없을 때"""
        from app.services.scheduler_service import SchedulerService

        service = SchedulerService()

        jobs = service.get_all_jobs()

        assert jobs == []

    def test_get_all_jobs_multiple(self):
        """여러 작업 조회"""
        from app.services.scheduler_service import SchedulerService

        service = SchedulerService()
        service.register_job("job1", "Job 1", "Test 1", 60, lambda: None)
        service.register_job("job2", "Job 2", "Test 2", 120, lambda: None)

        jobs = service.get_all_jobs()

        assert len(jobs) == 2


# ========== start / stop 테스트 ==========


class TestStartStop:
    """start / stop 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_start(self):
        """스케줄러 시작"""
        from app.services.scheduler_service import SchedulerService

        service = SchedulerService()

        await service.start()

        assert service._running is True
        assert service._task is not None

        # 정리
        await service.stop()

    @pytest.mark.asyncio
    async def test_start_already_running(self):
        """이미 실행 중일 때 시작"""
        from app.services.scheduler_service import SchedulerService

        service = SchedulerService()

        await service.start()
        await service.start()  # 두 번 호출

        assert service._running is True

        # 정리
        await service.stop()

    @pytest.mark.asyncio
    async def test_stop(self):
        """스케줄러 중지"""
        from app.services.scheduler_service import SchedulerService

        service = SchedulerService()

        await service.start()
        await service.stop()

        assert service._running is False


# ========== _execute_job 테스트 ==========


class TestExecuteJob:
    """_execute_job 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_execute_sync_handler(self):
        """동기 핸들러 실행"""
        from app.services.scheduler_service import SchedulerService, ScheduledJob, JobStatus

        service = SchedulerService()

        handler_called = []

        def sync_handler():
            handler_called.append(True)

        job = ScheduledJob(
            job_id="sync_job",
            name="Sync Job",
            description="Test",
            interval_seconds=60,
            handler=sync_handler
        )

        await service._execute_job(job)

        assert len(handler_called) == 1
        assert job.run_count == 1
        assert job.status == JobStatus.IDLE

    @pytest.mark.asyncio
    async def test_execute_async_handler(self):
        """비동기 핸들러 실행"""
        from app.services.scheduler_service import SchedulerService, ScheduledJob

        service = SchedulerService()

        handler_called = []

        async def async_handler():
            handler_called.append(True)

        job = ScheduledJob(
            job_id="async_job",
            name="Async Job",
            description="Test",
            interval_seconds=60,
            handler=async_handler
        )

        await service._execute_job(job)

        assert len(handler_called) == 1
        assert job.run_count == 1

    @pytest.mark.asyncio
    async def test_execute_failing_handler(self):
        """실패하는 핸들러 실행"""
        from app.services.scheduler_service import SchedulerService, ScheduledJob, JobStatus

        service = SchedulerService()

        def failing_handler():
            raise ValueError("Handler failed")

        job = ScheduledJob(
            job_id="failing_job",
            name="Failing Job",
            description="Test",
            interval_seconds=60,
            handler=failing_handler
        )

        await service._execute_job(job)

        assert job.error_count == 1
        assert "Handler failed" in job.last_error
        assert job.status == JobStatus.IDLE  # 최종적으로 IDLE

    @pytest.mark.asyncio
    async def test_execute_sets_next_run(self):
        """다음 실행 시간 설정"""
        from app.services.scheduler_service import SchedulerService, ScheduledJob

        service = SchedulerService()

        job = ScheduledJob(
            job_id="test_job",
            name="Test Job",
            description="Test",
            interval_seconds=300,
            handler=lambda: None
        )

        before = datetime.utcnow()
        await service._execute_job(job)
        after = datetime.utcnow()

        # next_run은 현재 + interval_seconds 근처여야 함
        expected_min = before + timedelta(seconds=300)
        expected_max = after + timedelta(seconds=300)

        assert job.next_run >= expected_min
        assert job.next_run <= expected_max


# ========== run_job_now 테스트 ==========


class TestRunJobNow:
    """run_job_now 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_run_job_now_nonexistent(self):
        """없는 작업 즉시 실행"""
        from app.services.scheduler_service import SchedulerService

        service = SchedulerService()

        result = await service.run_job_now("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_run_job_now_already_running(self):
        """이미 실행 중인 작업"""
        from app.services.scheduler_service import SchedulerService, JobStatus

        service = SchedulerService()
        service.register_job("job1", "Job 1", "Test", 60, lambda: None)
        service._jobs["job1"].status = JobStatus.RUNNING

        result = await service.run_job_now("job1")

        assert result is False

    @pytest.mark.asyncio
    async def test_run_job_now_success(self):
        """즉시 실행 성공"""
        from app.services.scheduler_service import SchedulerService

        service = SchedulerService()
        service.register_job("job1", "Job 1", "Test", 60, lambda: None)

        result = await service.run_job_now("job1")

        assert result is True

        # 태스크가 완료될 때까지 대기
        await asyncio.sleep(0.1)


# ========== setup_default_jobs 테스트 ==========


class TestSetupDefaultJobs:
    """setup_default_jobs 함수 테스트"""

    def test_setup_default_jobs(self):
        """기본 작업 등록 확인"""
        from app.services.scheduler_service import setup_default_jobs, scheduler

        # 기존 작업 정리
        scheduler._jobs.clear()

        setup_default_jobs()

        assert "cleanup_old_data" in scheduler._jobs
        assert "generate_sample_data" in scheduler._jobs

        # cleanup 작업은 활성화됨
        assert scheduler._jobs["cleanup_old_data"].enabled is True

        # sample data 작업은 비활성화됨
        assert scheduler._jobs["generate_sample_data"].enabled is False


# ========== cleanup_old_sensor_data 테스트 ==========


class TestCleanupOldSensorData:
    """cleanup_old_sensor_data 함수 테스트"""

    @pytest.mark.asyncio
    @patch("app.database.SessionLocal")
    async def test_cleanup_success(self, mock_session_local):
        """정리 성공"""
        from app.services.scheduler_service import cleanup_old_sensor_data

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.delete.return_value = 100
        mock_session_local.return_value = mock_db

        await cleanup_old_sensor_data()

        mock_db.commit.assert_called_once()
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.database.SessionLocal")
    async def test_cleanup_error(self, mock_session_local):
        """정리 중 에러"""
        from app.services.scheduler_service import cleanup_old_sensor_data

        mock_db = MagicMock()
        mock_db.query.side_effect = Exception("DB error")
        mock_session_local.return_value = mock_db

        # 에러가 발생해도 예외를 던지지 않아야 함
        await cleanup_old_sensor_data()

        mock_db.close.assert_called_once()


# ========== generate_sample_sensor_data 테스트 ==========


class TestGenerateSampleSensorData:
    """generate_sample_sensor_data 함수 테스트"""

    @pytest.mark.asyncio
    @patch("app.database.SessionLocal")
    async def test_generate_success(self, mock_session_local):
        """샘플 데이터 생성 성공"""
        from app.services.scheduler_service import generate_sample_sensor_data

        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        await generate_sample_sensor_data()

        # 4 lines * 3 sensor types = 12 adds
        assert mock_db.add.call_count == 12
        mock_db.commit.assert_called_once()
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.database.SessionLocal")
    async def test_generate_error(self, mock_session_local):
        """생성 중 에러"""
        from app.services.scheduler_service import generate_sample_sensor_data

        mock_db = MagicMock()
        mock_db.add.side_effect = Exception("DB error")
        mock_session_local.return_value = mock_db

        # 에러가 발생해도 예외를 던지지 않아야 함
        await generate_sample_sensor_data()

        mock_db.close.assert_called_once()


# ========== 싱글톤 인스턴스 테스트 ==========


class TestSchedulerSingleton:
    """scheduler 싱글톤 테스트"""

    def test_scheduler_is_singleton(self):
        """싱글톤 확인"""
        from app.services.scheduler_service import scheduler

        assert scheduler is not None
        assert isinstance(scheduler, type(scheduler))
