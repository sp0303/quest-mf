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
    parse_amfi_feed,
    reconcile_amfi_vs_mfapi,
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
