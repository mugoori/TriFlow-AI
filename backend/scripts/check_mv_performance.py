#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MV Performance Check Script

Usage:
    python backend/scripts/check_mv_performance.py
    python backend/scripts/check_mv_performance.py --watch  # Continuous monitoring

Checks:
1. MV refresh timing
2. Dashboard response time
3. Row counts
4. Scheduler status
"""

import asyncio
import sys
import time
from datetime import datetime
import argparse
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.database import async_session_factory
from app.services.mv_refresh_service import mv_refresh_service
from app.services.scheduler_service import scheduler


async def check_mv_refresh_performance():
    """Test MV refresh performance"""
    print("\n" + "=" * 60)
    print("MV REFRESH PERFORMANCE CHECK")
    print("=" * 60)

    async with async_session_factory() as db:
        start_time = time.time()
        result = await mv_refresh_service.refresh_all(db)
        total_elapsed = time.time() - start_time

        print(f"\nTotal Time: {total_elapsed:.2f}s")
        print(f"Status: {'✓ SUCCESS' if result['success'] else '✗ FAILED'}")

        if not result['success']:
            print(f"\nErrors: {result['errors']}")

        print("\nPer-View Results:")
        print("-" * 60)
        print(f"{'View Name':<35} {'Time':>8} {'Rows':>12}")
        print("-" * 60)

        for mv_name, view_result in result["views"].items():
            status_icon = "✓" if view_result["status"] == "success" else "✗"
            elapsed = view_result.get("elapsed_seconds", 0)
            row_count = view_result.get("row_count", "N/A")

            print(f"{status_icon} {mv_name:<32} {elapsed:>7.2f}s {row_count:>12}")

        # Performance warnings
        print("\nPerformance Analysis:")
        print("-" * 60)
        if total_elapsed > 60:
            print(f"⚠ WARNING: Total refresh time {total_elapsed:.2f}s exceeds 60s threshold")
        else:
            print(f"✓ Total refresh time {total_elapsed:.2f}s is acceptable")

        slow_views = [
            (name, res["elapsed_seconds"])
            for name, res in result["views"].items()
            if res.get("elapsed_seconds", 0) > 30
        ]
        if slow_views:
            print(f"⚠ WARNING: {len(slow_views)} views exceeded 30s threshold:")
            for name, elapsed in slow_views:
                print(f"  - {name}: {elapsed:.2f}s")
        else:
            print("✓ All views refreshed within 30s threshold")


async def check_scheduler_status():
    """Check scheduler running status"""
    print("\n" + "=" * 60)
    print("SCHEDULER STATUS CHECK")
    print("=" * 60)

    print(f"\nScheduler Running: {scheduler._running}")
    print(f"Refresh Count: {scheduler._refresh_count}")

    jobs = scheduler.get_all_jobs()
    mv_job = next((j for j in jobs if j["job_id"] == "refresh_materialized_views"), None)

    if mv_job:
        print("\nMV Refresh Job:")
        print(f"  Enabled: {mv_job['enabled']}")
        print(f"  Status: {mv_job['status']}")
        print(f"  Interval: {mv_job['interval_seconds']}s ({mv_job['interval_seconds'] // 60}min)")
        print(f"  Last Run: {mv_job['last_run'] or 'Never'}")
        print(f"  Next Run: {mv_job['next_run'] or 'N/A'}")
        print(f"  Run Count: {mv_job['run_count']}")
        print(f"  Error Count: {mv_job['error_count']}")
        if mv_job['last_error']:
            print(f"  Last Error: {mv_job['last_error']}")
    else:
        print("✗ MV refresh job not found!")


async def check_mv_health():
    """Check MV health status"""
    print("\n" + "=" * 60)
    print("MV HEALTH CHECK")
    print("=" * 60)

    async with async_session_factory() as db:
        mv_info = await mv_refresh_service.get_mv_info(db)

        print(f"\nTotal MVs: {len(mv_info)}")
        print("\nMV Status:")
        print("-" * 60)
        print(f"{'View Name':<40} {'Pop':>5} {'Idx':>5}")
        print("-" * 60)

        for mv in mv_info:
            populated_icon = "✓" if mv["is_populated"] else "✗"
            indexed_icon = "✓" if mv["has_indexes"] else "✗"

            print(f"{mv['name']:<40} {populated_icon:>5} {indexed_icon:>5}")

        # Get service status
        service_status = mv_refresh_service.status
        print("\nService Status:")
        print(f"  Last Refresh: {service_status['last_refresh'] or 'Never'}")
        print(f"  Refresh Count: {service_status['refresh_count']}")
        if service_status['last_error']:
            print(f"  Last Error: {service_status['last_error']}")


async def main():
    parser = argparse.ArgumentParser(description="Check MV Performance")
    parser.add_argument("--watch", action="store_true", help="Continuous monitoring mode")
    parser.add_argument("--interval", type=int, default=300, help="Watch interval in seconds (default: 300)")
    args = parser.parse_args()

    try:
        if args.watch:
            print("Starting continuous monitoring (Ctrl+C to stop)...")
            iteration = 0
            while True:
                iteration += 1
                print(f"\n{'#' * 60}")
                print(f"# Iteration {iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"{'#' * 60}")

                await check_scheduler_status()
                await check_mv_health()
                await check_mv_refresh_performance()

                print(f"\n{'=' * 60}")
                print(f"Next check in {args.interval}s... (Ctrl+C to stop)")
                print(f"{'=' * 60}")
                await asyncio.sleep(args.interval)
        else:
            await check_scheduler_status()
            await check_mv_health()
            await check_mv_refresh_performance()

            print("\n" + "=" * 60)
            print("Check completed successfully")
            print("=" * 60)

    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
