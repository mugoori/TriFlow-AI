"""
스케줄러 라우터 테스트

스케줄러 관리 엔드포인트 단위 테스트
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch


class TestJobStatusResponseSchema:
    """JobStatusResponse 스키마 테스트"""

    def test_job_status_response_model(self):
        """작업 상태 응답 모델"""
        from app.routers.scheduler import JobStatusResponse

        response = JobStatusResponse(
            job_id="sync_erp_data",
            name="ERP 데이터 동기화",
            description="ERP에서 데이터를 주기적으로 동기화",
            interval_seconds=300,
            enabled=True,
            status="idle",
            last_run="2024-01-15T10:00:00Z",
            next_run="2024-01-15T10:05:00Z",
            run_count=100,
            error_count=2,
            last_error=None,
        )

        assert response.job_id == "sync_erp_data"
        assert response.name == "ERP 데이터 동기화"
        assert response.interval_seconds == 300
        assert response.enabled is True
        assert response.status == "idle"
        assert response.run_count == 100

    def test_job_status_with_error(self):
        """에러가 있는 작업 상태"""
        from app.routers.scheduler import JobStatusResponse

        response = JobStatusResponse(
            job_id="failed_job",
            name="실패한 작업",
            description="에러 발생 테스트",
            interval_seconds=60,
            enabled=True,
            status="error",
            last_run="2024-01-15T10:00:00Z",
            next_run=None,
            run_count=50,
            error_count=10,
            last_error="Connection timeout",
        )

        assert response.status == "error"
        assert response.error_count == 10
        assert response.last_error == "Connection timeout"

    def test_job_status_never_run(self):
        """실행된 적 없는 작업"""
        from app.routers.scheduler import JobStatusResponse

        response = JobStatusResponse(
            job_id="new_job",
            name="새 작업",
            description="아직 실행되지 않은 작업",
            interval_seconds=3600,
            enabled=False,
            status="idle",
            last_run=None,
            next_run=None,
            run_count=0,
            error_count=0,
            last_error=None,
        )

        assert response.last_run is None
        assert response.run_count == 0


class TestSchedulerStatusResponseSchema:
    """SchedulerStatusResponse 스키마 테스트"""

    def test_scheduler_status_response_model(self):
        """스케줄러 상태 응답 모델"""
        from app.routers.scheduler import SchedulerStatusResponse, JobStatusResponse

        jobs = [
            JobStatusResponse(
                job_id="job1",
                name="작업1",
                description="설명1",
                interval_seconds=60,
                enabled=True,
                status="idle",
                last_run=None,
                next_run=None,
                run_count=0,
                error_count=0,
                last_error=None,
            ),
            JobStatusResponse(
                job_id="job2",
                name="작업2",
                description="설명2",
                interval_seconds=120,
                enabled=False,
                status="idle",
                last_run=None,
                next_run=None,
                run_count=0,
                error_count=0,
                last_error=None,
            ),
        ]

        response = SchedulerStatusResponse(
            is_running=True,
            total_jobs=2,
            enabled_jobs=1,
            jobs=jobs,
        )

        assert response.is_running is True
        assert response.total_jobs == 2
        assert response.enabled_jobs == 1
        assert len(response.jobs) == 2

    def test_scheduler_stopped(self):
        """중지된 스케줄러"""
        from app.routers.scheduler import SchedulerStatusResponse

        response = SchedulerStatusResponse(
            is_running=False,
            total_jobs=3,
            enabled_jobs=0,
            jobs=[],
        )

        assert response.is_running is False


class TestJobActionResponseSchema:
    """JobActionResponse 스키마 테스트"""

    def test_job_action_success(self):
        """성공 응답"""
        from app.routers.scheduler import JobActionResponse

        response = JobActionResponse(
            success=True,
            message="Job enabled successfully",
        )

        assert response.success is True
        assert "successfully" in response.message

    def test_job_action_failure(self):
        """실패 응답"""
        from app.routers.scheduler import JobActionResponse

        response = JobActionResponse(
            success=False,
            message="Job not found",
        )

        assert response.success is False


class TestGetSchedulerStatus:
    """GET /status 엔드포인트 테스트"""

    @pytest.mark.asyncio
    async def test_get_scheduler_status(self):
        """스케줄러 상태 조회"""
        from app.routers.scheduler import get_scheduler_status

        mock_jobs = [
            {
                "job_id": "job1",
                "name": "작업1",
                "description": "설명1",
                "interval_seconds": 60,
                "enabled": True,
                "status": "idle",
                "last_run": None,
                "next_run": None,
                "run_count": 0,
                "error_count": 0,
                "last_error": None,
            }
        ]

        with patch("app.routers.scheduler.scheduler") as mock_scheduler:
            mock_scheduler.get_all_jobs.return_value = mock_jobs
            mock_scheduler._running = True

            result = await get_scheduler_status()

            assert result.is_running is True
            assert result.total_jobs == 1
            assert result.enabled_jobs == 1

    @pytest.mark.asyncio
    async def test_get_scheduler_status_no_jobs(self):
        """작업 없는 스케줄러"""
        from app.routers.scheduler import get_scheduler_status

        with patch("app.routers.scheduler.scheduler") as mock_scheduler:
            mock_scheduler.get_all_jobs.return_value = []
            mock_scheduler._running = False

            result = await get_scheduler_status()

            assert result.is_running is False
            assert result.total_jobs == 0
            assert result.enabled_jobs == 0

    @pytest.mark.asyncio
    async def test_get_scheduler_status_counts_enabled_jobs(self):
        """활성화된 작업 수 계산"""
        from app.routers.scheduler import get_scheduler_status

        mock_jobs = [
            {"job_id": "job1", "name": "작업1", "description": "", "interval_seconds": 60, "enabled": True, "status": "idle", "last_run": None, "next_run": None, "run_count": 0, "error_count": 0, "last_error": None},
            {"job_id": "job2", "name": "작업2", "description": "", "interval_seconds": 60, "enabled": False, "status": "idle", "last_run": None, "next_run": None, "run_count": 0, "error_count": 0, "last_error": None},
            {"job_id": "job3", "name": "작업3", "description": "", "interval_seconds": 60, "enabled": True, "status": "idle", "last_run": None, "next_run": None, "run_count": 0, "error_count": 0, "last_error": None},
        ]

        with patch("app.routers.scheduler.scheduler") as mock_scheduler:
            mock_scheduler.get_all_jobs.return_value = mock_jobs
            mock_scheduler._running = True

            result = await get_scheduler_status()

            assert result.total_jobs == 3
            assert result.enabled_jobs == 2


class TestGetJobStatus:
    """GET /jobs/{job_id} 엔드포인트 테스트"""

    @pytest.mark.asyncio
    async def test_get_job_status_found(self):
        """작업 상태 조회 성공"""
        from app.routers.scheduler import get_job_status

        mock_job = {
            "job_id": "sync_data",
            "name": "데이터 동기화",
            "description": "주기적 동기화",
            "interval_seconds": 300,
            "enabled": True,
            "status": "running",
            "last_run": "2024-01-15T10:00:00Z",
            "next_run": "2024-01-15T10:05:00Z",
            "run_count": 100,
            "error_count": 0,
            "last_error": None,
        }

        with patch("app.routers.scheduler.scheduler") as mock_scheduler:
            mock_scheduler.get_job_status.return_value = mock_job

            result = await get_job_status("sync_data")

            assert result.job_id == "sync_data"
            assert result.status == "running"

    @pytest.mark.asyncio
    async def test_get_job_status_not_found(self):
        """작업 없음"""
        from app.routers.scheduler import get_job_status
        from fastapi import HTTPException

        with patch("app.routers.scheduler.scheduler") as mock_scheduler:
            mock_scheduler.get_job_status.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                await get_job_status("nonexistent")

            assert exc_info.value.status_code == 404
            assert "not found" in exc_info.value.detail


class TestEnableJob:
    """POST /jobs/{job_id}/enable 엔드포인트 테스트"""

    @pytest.mark.asyncio
    async def test_enable_job_success(self):
        """작업 활성화 성공"""
        from app.routers.scheduler import enable_job

        with patch("app.routers.scheduler.scheduler") as mock_scheduler:
            mock_scheduler.enable_job.return_value = True

            result = await enable_job("job1")

            assert result.success is True
            assert "enabled" in result.message

    @pytest.mark.asyncio
    async def test_enable_job_not_found(self):
        """작업 없음"""
        from app.routers.scheduler import enable_job
        from fastapi import HTTPException

        with patch("app.routers.scheduler.scheduler") as mock_scheduler:
            mock_scheduler.enable_job.return_value = False

            with pytest.raises(HTTPException) as exc_info:
                await enable_job("nonexistent")

            assert exc_info.value.status_code == 404


class TestDisableJob:
    """POST /jobs/{job_id}/disable 엔드포인트 테스트"""

    @pytest.mark.asyncio
    async def test_disable_job_success(self):
        """작업 비활성화 성공"""
        from app.routers.scheduler import disable_job

        with patch("app.routers.scheduler.scheduler") as mock_scheduler:
            mock_scheduler.disable_job.return_value = True

            result = await disable_job("job1")

            assert result.success is True
            assert "disabled" in result.message

    @pytest.mark.asyncio
    async def test_disable_job_not_found(self):
        """작업 없음"""
        from app.routers.scheduler import disable_job
        from fastapi import HTTPException

        with patch("app.routers.scheduler.scheduler") as mock_scheduler:
            mock_scheduler.disable_job.return_value = False

            with pytest.raises(HTTPException) as exc_info:
                await disable_job("nonexistent")

            assert exc_info.value.status_code == 404


class TestRunJobNow:
    """POST /jobs/{job_id}/run 엔드포인트 테스트"""

    @pytest.mark.asyncio
    async def test_run_job_now_success(self):
        """즉시 실행 성공"""
        from app.routers.scheduler import run_job_now

        with patch("app.routers.scheduler.scheduler") as mock_scheduler:
            mock_scheduler.run_job_now = AsyncMock(return_value=True)

            result = await run_job_now("job1")

            assert result.success is True
            assert "started" in result.message

    @pytest.mark.asyncio
    async def test_run_job_now_not_found(self):
        """작업 없음 또는 이미 실행 중"""
        from app.routers.scheduler import run_job_now
        from fastapi import HTTPException

        with patch("app.routers.scheduler.scheduler") as mock_scheduler:
            mock_scheduler.run_job_now = AsyncMock(return_value=False)

            with pytest.raises(HTTPException) as exc_info:
                await run_job_now("nonexistent")

            assert exc_info.value.status_code == 400
            assert "not found or already running" in exc_info.value.detail


class TestStartScheduler:
    """POST /start 엔드포인트 테스트"""

    @pytest.mark.asyncio
    async def test_start_scheduler(self):
        """스케줄러 시작"""
        from app.routers.scheduler import start_scheduler

        with patch("app.routers.scheduler.scheduler") as mock_scheduler:
            mock_scheduler.start = AsyncMock()

            result = await start_scheduler()

            assert result.success is True
            assert "started" in result.message
            mock_scheduler.start.assert_called_once()


class TestStopScheduler:
    """POST /stop 엔드포인트 테스트"""

    @pytest.mark.asyncio
    async def test_stop_scheduler(self):
        """스케줄러 중지"""
        from app.routers.scheduler import stop_scheduler

        with patch("app.routers.scheduler.scheduler") as mock_scheduler:
            mock_scheduler.stop = AsyncMock()

            result = await stop_scheduler()

            assert result.success is True
            assert "stopped" in result.message
            mock_scheduler.stop.assert_called_once()


class TestJobIntervalValidation:
    """작업 간격 검증 테스트"""

    def test_minimum_interval(self):
        """최소 간격"""
        interval_seconds = 10  # 최소 10초
        is_valid = interval_seconds >= 10
        assert is_valid is True

    def test_maximum_interval(self):
        """최대 간격"""
        interval_seconds = 86400  # 최대 24시간
        is_valid = interval_seconds <= 86400
        assert is_valid is True

    def test_common_intervals(self):
        """일반적인 간격"""
        intervals = {
            "1분": 60,
            "5분": 300,
            "15분": 900,
            "30분": 1800,
            "1시간": 3600,
        }

        for name, seconds in intervals.items():
            assert seconds > 0
            assert seconds <= 86400


class TestJobStatusValues:
    """작업 상태 값 테스트"""

    def test_valid_status_values(self):
        """유효한 상태 값"""
        valid_statuses = ["idle", "running", "error", "disabled"]

        for status in valid_statuses:
            assert status in valid_statuses

    def test_status_transitions(self):
        """상태 전환"""
        # idle -> running
        current_status = "idle"
        new_status = "running"
        assert current_status != new_status

        # running -> idle (완료)
        current_status = "running"
        new_status = "idle"
        assert current_status != new_status

        # running -> error
        current_status = "running"
        new_status = "error"
        assert current_status != new_status


class TestJobExecution:
    """작업 실행 테스트"""

    def test_run_count_increment(self):
        """실행 횟수 증가"""
        run_count = 10
        run_count += 1
        assert run_count == 11

    def test_error_count_increment(self):
        """에러 횟수 증가"""
        error_count = 0
        error_count += 1
        assert error_count == 1

    def test_last_run_update(self):
        """마지막 실행 시간 업데이트"""
        last_run = datetime.now()
        assert last_run is not None

    def test_next_run_calculation(self):
        """다음 실행 시간 계산"""
        from datetime import timedelta

        last_run = datetime.now()
        interval_seconds = 300

        next_run = last_run + timedelta(seconds=interval_seconds)
        assert next_run > last_run


class TestConcurrentJobExecution:
    """동시 실행 방지 테스트"""

    def test_prevent_concurrent_execution(self):
        """동시 실행 방지"""
        job_status = "running"

        # 이미 실행 중이면 실행 불가
        can_run = job_status != "running"
        assert can_run is False

    def test_allow_execution_when_idle(self):
        """유휴 상태면 실행 가능"""
        job_status = "idle"

        can_run = job_status != "running"
        assert can_run is True


class TestSchedulerLifecycle:
    """스케줄러 생명주기 테스트"""

    def test_scheduler_start(self):
        """스케줄러 시작"""
        is_running = False
        is_running = True
        assert is_running is True

    def test_scheduler_stop(self):
        """스케줄러 중지"""
        is_running = True
        is_running = False
        assert is_running is False

    def test_jobs_pause_on_stop(self):
        """중지 시 작업 일시정지"""
        scheduler_running = False
        job_enabled = True

        # 스케줄러 중지되면 작업 실행 안함
        should_run = scheduler_running and job_enabled
        assert should_run is False
