"""Production Daily Scheduler Daemon.

Orchestrates the nightly quant data pipeline at 11:30 PM IST (18:00 UTC):
1. Ingests today's AMFI NAV feed (Rule Q7: Direct-Growth canonical).
2. Ingests today's NSE Benchmark TRI updates (Rule Q5: TRI only).
3. Precomputes all risk metrics, percentiles, and 2x2 screener snapshots (Rule 1).

Usage:
    python -m workers.daily_scheduler --once      # Run once immediately and exit
    python -m workers.daily_scheduler --daemon    # Run continuous daemon waiting for 23:30 IST
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, time, timedelta, timezone
import logging
from typing import Any

from workers.benchmark_worker import ingest_benchmark_tri_history
from workers.compute_worker import run_compute_job
from workers.ingestion_worker import ingest_amfi_and_historical

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("daily_scheduler")

# Indian Standard Time (UTC+05:30)
IST = timezone(timedelta(hours=5, minutes=30))
TARGET_RUN_TIME = time(hour=23, minute=30, second=0)


async def run_nightly_pipeline() -> dict[str, Any]:
    """Execute the end-to-end nightly ingestion and quant compute pipeline."""
    start_time = datetime.now(timezone.utc)
    logger.info("=" * 70)
    logger.info("STARTING NIGHTLY DATA & QUANT PIPELINE [%s]", start_time.isoformat())
    logger.info("=" * 70)

    results: dict[str, Any] = {"status": "SUCCESS", "started_at": start_time.isoformat()}

    # Step 1: Ingest AMFI Daily Feed (Direct-Growth Delta)
    try:
        logger.info("[Step 1/3] Ingesting AMFI daily NAV feed (max_history_schemes=0 for delta)...")
        amfi_res = await ingest_amfi_and_historical(concurrency=5, max_history_schemes=0)
        results["amfi_ingestion"] = amfi_res
        logger.info("AMFI ingestion completed: %s", amfi_res)
    except Exception as e:
        logger.exception("Failed during AMFI daily ingestion: %s", e)
        results["status"] = "FAILED_AT_AMFI"
        results["error"] = str(e)
        return results

    # Step 2: Ingest NSE Benchmark TRI Updates
    try:
        logger.info("[Step 2/3] Ingesting NSE Benchmark TRI updates (Rule Q5)...")
        bench_res = await ingest_benchmark_tri_history()
        results["benchmark_ingestion"] = bench_res
        logger.info("Benchmark ingestion completed: %s", bench_res)
    except Exception as e:
        logger.exception("Failed during Benchmark TRI ingestion: %s", e)
        results["status"] = "FAILED_AT_BENCHMARK"
        results["error"] = str(e)
        return results

    # Step 3: Run Quant Analytics & Scoring Precomputation
    try:
        logger.info("[Step 3/3] Precomputing rolling metrics, Alpha, Beta, IR, SHP, and screener snapshots...")
        await run_compute_job()
        logger.info("Quant compute job completed successfully.")
    except Exception as e:
        logger.exception("Failed during quant batch compute: %s", e)
        results["status"] = "FAILED_AT_COMPUTE"
        results["error"] = str(e)
        return results

    end_time = datetime.now(timezone.utc)
    elapsed = (end_time - start_time).total_seconds()
    results["completed_at"] = end_time.isoformat()
    results["elapsed_seconds"] = round(elapsed, 2)

    logger.info("=" * 70)
    logger.info("NIGHTLY PIPELINE FINISHED SUCCESSFULLY IN %0.1fs", elapsed)
    logger.info("=" * 70)
    return results


def seconds_until_next_run() -> float:
    """Calculate seconds until the next 23:30 IST run."""
    now_ist = datetime.now(IST)
    target_today = datetime.combine(now_ist.date(), TARGET_RUN_TIME, tzinfo=IST)
    if now_ist >= target_today:
        target_next = target_today + timedelta(days=1)
    else:
        target_next = target_today
    return (target_next - now_ist).total_seconds()


async def run_daemon_loop() -> None:
    """Run persistent scheduler daemon."""
    logger.info("Starting Daily Scheduler Daemon targeting 23:30 IST daily...")
    while True:
        wait_secs = seconds_until_next_run()
        next_run_ist = datetime.now(IST) + timedelta(seconds=wait_secs)
        logger.info("Next nightly run scheduled for: %s IST (%0.1f hours from now)", next_run_ist.strftime("%Y-%m-%d %H:%M:%S"), wait_secs / 3600.0)
        await asyncio.sleep(wait_secs)
        await run_nightly_pipeline()


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily Data & Quant Pipeline Scheduler")
    parser.add_argument("--once", action="store_true", help="Run the pipeline once immediately and exit")
    parser.add_argument("--daemon", action="store_true", help="Run in continuous daemon mode (triggers at 23:30 IST)")
    args = parser.parse_args()

    if args.daemon:
        asyncio.run(run_daemon_loop())
    else:
        # Default is to run once
        asyncio.run(run_nightly_pipeline())


if __name__ == "__main__":
    main()
