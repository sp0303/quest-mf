"""Integration test for AMFI feed parsing and MFAPI reconciliation.

Phase 1 Exit Criteria:
- Tests A, F, K, L pass.
- Reconciliation vs MFAPI < 0.01% error.
- Rule Q7 & Test L: IDCW cannot be canonical; only Direct-Growth allowed.
"""

import asyncpg
import pytest

from app.config import settings
from workers.ingestion_worker import (
    AsyncRateLimiter,
    _mfapi_rate_limiter,
    fetch_mfapi_history_with_client,
    parse_amfi_feed,
    reconcile_amfi_vs_mfapi,
    store_raw_payload,
)

SAMPLE_AMFI_SNIPPET = """Open Ended Schemes (Equity Scheme - Small Cap Fund)
Axis Mutual Fund
135762;INF846K01WO1;-;Axis Small Cap Fund;Direct Plan;Growth Option;29.7129;17-Sep-2026
135765;INF846K01WP8;-;Axis Small Cap Fund;Direct Plan;IDCW Option;27.3710;17-Sep-2026
135759;INF846K01WJ1;-;Axis Small Cap Fund;Regular Plan;Growth Option;25.8746;17-Sep-2026
135760;INF846K01WK9;-;Axis Small Cap Fund;Regular Plan;IDCW Option;23.8714;17-Sep-2026
"""


def test_amfi_feed_parsing_and_canonical_guard():
    """Verify that parsing extracts canonical Direct-Growth schemes and excludes IDCW."""
    schemes, rejected = parse_amfi_feed(SAMPLE_AMFI_SNIPPET)
    assert len(schemes) == 4
    assert rejected == 0

    direct_growth = [s for s in schemes if s.scheme_code == 135762][0]
    assert direct_growth.plan == "DIRECT"
    assert direct_growth.option == "GROWTH"
    assert direct_growth.is_canonical is True
    assert direct_growth.nav == pytest.approx(29.7129)

    direct_idcw = [s for s in schemes if s.scheme_code == 135765][0]
    assert direct_idcw.plan == "DIRECT"
    assert direct_idcw.option == "IDCW"
    # Rule Q7 & Test L: IDCW cannot be canonical
    assert direct_idcw.is_canonical is False

    regular_growth = [s for s in schemes if s.scheme_code == 135759][0]
    assert regular_growth.plan == "REGULAR"
    # Rule Q7: Regular plan cannot be canonical when Direct is available
    assert regular_growth.is_canonical is False


def test_mfapi_reconciliation_threshold():
    """Verify reconciliation error between AMFI and MFAPI is within < 0.01%."""
    # Test case with identical NAVs
    diff_zero = reconcile_amfi_vs_mfapi(125.40, 125.40)
    assert diff_zero == 0.0

    # Test case with tiny rounding discrepancy (0.005%)
    diff_tiny = reconcile_amfi_vs_mfapi(100.00, 100.005)
    assert diff_tiny < 0.0001  # < 0.01%
    assert diff_tiny == pytest.approx(0.00005)

    # Test case with large discrepancy violating threshold (> 0.01%)
    diff_large = reconcile_amfi_vs_mfapi(100.0, 100.50)
    assert diff_large >= 0.0001


@pytest.mark.asyncio
async def test_ops_ingest_log_audit():
    """Verify that AMFI ingestion records are properly logged in ops.ingest_log."""
    conn = await asyncpg.connect(settings.pg_dsn)
    try:
        row = await conn.fetchrow(
            """
            SELECT ingest_id, source, rows_loaded, raw_sha256
            FROM ops.ingest_log
            WHERE source = 'AMFI'
            ORDER BY ingest_id DESC
            LIMIT 1;
            """
        )
        assert row is not None
        assert row["source"] == "AMFI"
        assert row["rows_loaded"] > 0
        assert len(row["raw_sha256"]) == 64
    finally:
        await conn.close()


def test_raw_payload_storage_integrity(tmp_path):
    """Verify AGENTS.md §9 raw payload persistence with exact SHA-256 match."""
    import hashlib
    from pathlib import Path

    sample_bytes = b"Scheme Code;ISIN;Scheme Name;NAV;Date\n10001;INF0001;Test Fund;10.5;2026-09-18"
    expected_hash = hashlib.sha256(sample_bytes).hexdigest()

    sha256, rel_path = store_raw_payload("test_src", sample_bytes, "test_file.txt")
    assert sha256 == expected_hash

    # Check file exists and bytes match exactly
    full_path = Path(__file__).resolve().parent.parent.parent / rel_path
    assert full_path.exists()
    assert full_path.read_bytes() == sample_bytes


@pytest.mark.asyncio
async def test_async_rate_limiter_pacing():
    """Verify rate limiter enforces minimum interval spacing (AGENTS.md §9)."""
    import time

    # Pacing at 10 req/s -> 0.1s minimum interval
    limiter = AsyncRateLimiter(requests_per_second=10.0)

    t0 = time.perf_counter()
    await limiter.wait()
    await limiter.wait()
    t1 = time.perf_counter()

    elapsed = t1 - t0
    assert elapsed >= 0.08  # at least ~0.1s between two requests


def test_all_sebi_categories_parsed():
    """Verify parse_amfi_feed correctly maps all SEBI equity categories."""
    multi_category_feed = """Open Ended Schemes (Equity Scheme - Large Cap Fund)
HDFC Mutual Fund
10001;INF179K01BE2;-;HDFC Top 100 Fund;Direct Plan;Growth Option;950.50;18-Sep-2026

Open Ended Schemes (Equity Scheme - Value Fund)
ICICI Prudential Mutual Fund
10002;INF109K01588;-;ICICI Prudential Value Discovery Fund;Direct Plan;Growth Option;350.20;18-Sep-2026

Open Ended Schemes (Equity Scheme - ELSS)
Mirae Asset Mutual Fund
10003;INF769K01DG4;-;Mirae Asset ELSS Tax Saver Fund;Direct Plan;Growth Option;42.10;18-Sep-2026

Open Ended Schemes (Other Scheme - Index Funds)
UTI Mutual Fund
10004;INF789F01X85;-;UTI Nifty 50 Index Fund;Direct Plan;Growth Option;165.80;18-Sep-2026
"""
    schemes, rejected = parse_amfi_feed(multi_category_feed)
    assert len(schemes) == 4
    assert rejected == 0

    cats = {s.scheme_code: s.category_code for s in schemes}
    assert cats[10001] == "EQ_LARGE_CAP"
    assert cats[10002] == "EQ_VALUE"
    assert cats[10003] == "EQ_ELSS"
    assert cats[10004] == "EQ_INDEX"


@pytest.mark.asyncio
async def test_mfapi_proactive_rate_limiting(monkeypatch):
    """Verify that fetch_mfapi_history_with_client actually waits on _mfapi_rate_limiter."""
    import httpx

    wait_called = False

    async def mock_wait():
        nonlocal wait_called
        wait_called = True

    monkeypatch.setattr(_mfapi_rate_limiter, "wait", mock_wait)

    async with httpx.AsyncClient() as client:
        # Call with mock that doesn't actually connect
        async def mock_get(*args, **kwargs):
            return httpx.Response(200, json={"data": []}, content=b'{"data": []}')

        monkeypatch.setattr(client, "get", mock_get)
        await fetch_mfapi_history_with_client(client, 12345)

    assert wait_called is True, (
        "_mfapi_rate_limiter.wait() must be called proactively before every request"
    )
