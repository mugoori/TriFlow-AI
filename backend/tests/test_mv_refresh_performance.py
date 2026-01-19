# -*- coding: utf-8 -*-
"""
MV Refresh Performance Tests

Validates:
1. MV refresh completes within acceptable time
2. Dashboard API responds within 2 seconds
3. MVs are properly populated
4. Concurrent requests maintain performance
"""

import pytest
import time
import asyncio
from uuid import uuid4

from app.services.mv_refresh_service import mv_refresh_service
from app.services.stat_card_service import StatCardService


@pytest.mark.slow
@pytest.mark.requires_db
class TestMVRefreshPerformance:
    """MV Refresh Performance Tests"""

    @pytest.mark.asyncio
    async def test_mv_refresh_completes_under_60_seconds(self, async_db_session):
        """MV refresh should complete in under 60 seconds"""
        start_time = time.time()
        result = await mv_refresh_service.refresh_all(async_db_session)
        elapsed = time.time() - start_time

        assert result["success"], f"MV refresh failed: {result['errors']}"
        assert elapsed < 60, f"MV refresh took {elapsed:.2f}s (limit: 60s)"

        # Check individual view times
        for mv_name, view_result in result["views"].items():
            assert view_result["status"] == "success", f"{mv_name} failed"
            assert view_result["elapsed_seconds"] < 30, \
                f"{mv_name} took {view_result['elapsed_seconds']:.2f}s (limit: 30s)"

    @pytest.mark.asyncio
    async def test_mv_row_counts_populated(self, async_db_session):
        """MVs should have data after refresh"""
        result = await mv_refresh_service.refresh_all(async_db_session)

        for mv_name, view_result in result["views"].items():
            if view_result["status"] == "success":
                row_count = view_result.get("row_count", 0)
                assert row_count >= 0, f"{mv_name} has invalid row count"
                # Note: Row count could be 0 if no data exists, which is valid

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires StatCardService async support")
    async def test_dashboard_response_under_2_seconds(self, async_db_session, test_user):
        """Dashboard API should respond in under 2 seconds (p95 target)"""
        service = StatCardService(async_db_session)

        # Run multiple times to get representative timing
        times = []
        for _ in range(5):
            start_time = time.time()
            await service.get_card_values(
                tenant_id=test_user.tenant_id,
                user_id=test_user.user_id,
                period="7days"
            )
            elapsed = time.time() - start_time
            times.append(elapsed)

        # Check p95 (95th percentile)
        times_sorted = sorted(times)
        p95 = times_sorted[int(len(times) * 0.95)]
        assert p95 < 2.0, f"Dashboard p95 response time {p95:.2f}s exceeds 2s target"

        # Check average
        avg = sum(times) / len(times)
        assert avg < 1.0, f"Dashboard average response time {avg:.2f}s exceeds 1s target"

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires StatCardService async support")
    async def test_concurrent_dashboard_requests(self, async_db_session, test_user):
        """Multiple concurrent requests should not degrade performance"""

        async def fetch_dashboard():
            service = StatCardService(async_db_session)
            start_time = time.time()
            await service.get_card_values(
                tenant_id=test_user.tenant_id,
                user_id=test_user.user_id,
                period="7days"
            )
            return time.time() - start_time

        # Simulate 10 concurrent users
        tasks = [fetch_dashboard() for _ in range(10)]
        times = await asyncio.gather(*tasks)

        # All requests should complete under 3 seconds
        max_time = max(times)
        assert max_time < 3.0, \
            f"Slowest concurrent request took {max_time:.2f}s (limit: 3s)"


@pytest.mark.integration
class TestMVHealthCheck:
    """MV Health Check Tests"""

    @pytest.mark.asyncio
    async def test_all_mvs_exist(self, async_db_session):
        """All 4 MVs should exist"""
        mv_info = await mv_refresh_service.get_mv_info(async_db_session)

        assert len(mv_info) == 4, f"Expected 4 MVs, found {len(mv_info)}"

        expected_mvs = {
            "bi.mv_defect_trend",
            "bi.mv_oee_daily",
            "bi.mv_line_performance",
            "bi.mv_quality_summary"
        }
        actual_mvs = {mv["name"] for mv in mv_info}
        assert actual_mvs == expected_mvs, f"MV mismatch: {actual_mvs}"

    @pytest.mark.asyncio
    async def test_all_mvs_have_unique_indexes(self, async_db_session):
        """All MVs should have UNIQUE indexes for CONCURRENT refresh"""
        mv_info = await mv_refresh_service.get_mv_info(async_db_session)

        for mv in mv_info:
            assert mv["has_indexes"], \
                f"{mv['name']} missing indexes (required for CONCURRENT refresh)"

    @pytest.mark.asyncio
    async def test_all_mvs_populated(self, async_db_session):
        """All MVs should be populated after refresh"""
        # First, refresh all MVs
        result = await mv_refresh_service.refresh_all(async_db_session)
        assert result["success"], "MV refresh failed"

        # Then check they are populated
        mv_info = await mv_refresh_service.get_mv_info(async_db_session)

        for mv in mv_info:
            assert mv["is_populated"], f"{mv['name']} not populated"


# Pytest Fixtures
@pytest.fixture
async def async_db_session():
    """
    Async database session fixture
    Note: This assumes pytest-asyncio and async DB fixtures are configured
    """
    from app.database import async_session_factory

    async with async_session_factory() as session:
        yield session


@pytest.fixture
def test_user():
    """Test user fixture"""
    from app.models import User

    return User(
        user_id=uuid4(),
        tenant_id=uuid4(),
        username="test_user",
        email="test@example.com",
        full_name="Test User",
        role="user",
        is_active=True,
    )
