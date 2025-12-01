"""
스케줄러 관리 라우터
"""
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.scheduler_service import scheduler

router = APIRouter()


class JobStatusResponse(BaseModel):
    job_id: str
    name: str
    description: str
    interval_seconds: int
    enabled: bool
    status: str
    last_run: str | None
    next_run: str | None
    run_count: int
    error_count: int
    last_error: str | None


class SchedulerStatusResponse(BaseModel):
    is_running: bool
    total_jobs: int
    enabled_jobs: int
    jobs: List[JobStatusResponse]


class JobActionResponse(BaseModel):
    success: bool
    message: str


@router.get("/status", response_model=SchedulerStatusResponse)
async def get_scheduler_status():
    """
    스케줄러 상태 및 모든 작업 조회
    """
    jobs = scheduler.get_all_jobs()
    enabled_count = sum(1 for j in jobs if j and j.get("enabled"))

    return SchedulerStatusResponse(
        is_running=scheduler._running,
        total_jobs=len(jobs),
        enabled_jobs=enabled_count,
        jobs=[JobStatusResponse(**j) for j in jobs if j],
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    특정 작업 상태 조회
    """
    status = scheduler.get_job_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return JobStatusResponse(**status)


@router.post("/jobs/{job_id}/enable", response_model=JobActionResponse)
async def enable_job(job_id: str):
    """
    작업 활성화
    """
    success = scheduler.enable_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return JobActionResponse(success=True, message=f"Job {job_id} enabled")


@router.post("/jobs/{job_id}/disable", response_model=JobActionResponse)
async def disable_job(job_id: str):
    """
    작업 비활성화
    """
    success = scheduler.disable_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return JobActionResponse(success=True, message=f"Job {job_id} disabled")


@router.post("/jobs/{job_id}/run", response_model=JobActionResponse)
async def run_job_now(job_id: str):
    """
    작업 즉시 실행
    """
    success = await scheduler.run_job_now(job_id)
    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Job {job_id} not found or already running"
        )
    return JobActionResponse(success=True, message=f"Job {job_id} started")


@router.post("/start", response_model=JobActionResponse)
async def start_scheduler():
    """
    스케줄러 시작
    """
    await scheduler.start()
    return JobActionResponse(success=True, message="Scheduler started")


@router.post("/stop", response_model=JobActionResponse)
async def stop_scheduler():
    """
    스케줄러 중지
    """
    await scheduler.stop()
    return JobActionResponse(success=True, message="Scheduler stopped")
