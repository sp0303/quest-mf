"""Benchmark TRI ingestion worker.

Fetches historical Total Return Index (TRI) data for NSE benchmarks:
- NIFTY 50 TRI
- NIFTY MIDCAP 150 TRI
- NIFTY SMALLCAP 250 TRI
- NIFTY 500 TRI

Stores raw payloads in var/data/raw/benchmarks/ (AGENTS.md §9),
and inserts daily values into market.benchmark_values via COPY staging.
Adheres strictly to Rule Q5 (Benchmarks are TRI).
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, datetime
from typing import Any

import asyncpg
import httpx

from app.config import settings
from workers.ingestion_worker import AsyncRateLimiter, store_raw_payload

logger = logging.getLogger("benchmark_worker")
logging.basicConfig(level=logging.INFO)

NIFTY_INDICES_URL = "https://www.niftyindices.com/Backpage/getTotalReturnIndexString"

# Mapping benchmark code -> (benchmark_id, nse_index_name, label)
BENCHMARKS = {
    "NIFTY_50_TRI": (3, "NIFTY 50", "Nifty 50 TRI"),
    "NIFTY_MIDCAP_150_TRI": (4, "NIFTY MIDCAP 150", "Nifty Midcap 150 TRI"),
    "NIFTY_SMALLCAP_250_TRI": (1, "NIFTY SMALLCAP 250", "Nifty Smallcap 250 TRI"),
    "NIFTY_500_TRI": (2, "NIFTY 500", "Nifty 500 TRI"),
}

_nse_rate_limiter = AsyncRateLimiter(requests_per_second=1.0)


async def fetch_nifty_tri_series(
    client: httpx.AsyncClient,
    index_name: str,
    start_date: str = "01-Jan-2013",
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch historical Total Return Index daily values from Nifty Indices."""
    await _nse_rate_limiter.wait()
    if end_date is None:
        end_date = date.today().strftime("%d-%b-%Y")

    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        "Origin": "https://www.niftyindices.com",
        "Referer": "https://www.niftyindices.com/reports/historical-data",
    }

    parameters = {
        "name": index_name,
        "startDate": start_date,
        "endDate": end_date,
        "indexName": index_name,
    }
    payload = json.dumps({"cinfo": json.dumps(parameters)})

    try:
        resp = await client.post(NIFTY_INDICES_URL, headers=headers, content=payload)
        if resp.status_code == 200:
            raw_bytes = resp.content
            store_raw_payload(
                "benchmarks",
                raw_bytes,
                f"{index_name.replace(' ', '_')}_{date.today().isoformat()}.json",
            )
            data = resp.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "d" in data:
                return json.loads(data["d"])
        else:
            logger.warning("Nifty Indices returned HTTP %d for %s", resp.status_code, index_name)
    except Exception as e:
        logger.warning("Failed to fetch Nifty TRI for %s: %s", index_name, e)

    return []


def parse_nifty_date(d_str: str) -> date | None:
    """Parse Nifty date formats like '18 Sep 2026' or '18-09-2026'."""
    d_str = d_str.strip()
    for fmt in ("%d %b %Y", "%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(d_str, fmt).date()
        except ValueError:
            pass
    return None


async def ingest_benchmark_tri_history() -> dict[str, Any]:
    """Ingest historical Total Return Index series for all primary equity benchmarks."""
    logger.info("Starting Benchmark TRI Ingestion...")
    conn = await asyncpg.connect(settings.pg_dsn)
    try:
        # Ensure benchmarks exist in ref.benchmarks
        for code, (bid, _idx_name, label) in BENCHMARKS.items():
            await conn.execute(
                """
                INSERT INTO ref.benchmarks (benchmark_id, code, label, provider, is_tri)
                VALUES ($1, $2, $3, 'NSE', true)
                ON CONFLICT (benchmark_id) DO UPDATE
                SET code = EXCLUDED.code, label = EXCLUDED.label, is_tri = true;
                """,
                bid,
                code,
                label,
            )

        client_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        }
        total_ingested = 0
        summary = {}

        async with httpx.AsyncClient(
            timeout=45.0, follow_redirects=True, verify=True, headers=client_headers
        ) as client:
            for code, (bid, idx_name, label) in BENCHMARKS.items():
                logger.info(
                    "Fetching authentic TRI series for %s (%s) from 01-Jan-2013...", label, idx_name
                )
                points = await fetch_nifty_tri_series(client, idx_name, start_date="01-Jan-2013")
                logger.info("Retrieved %d daily points for %s.", len(points), label)

                records = []
                for pt in points:
                    d_val = parse_nifty_date(pt.get("Date", ""))
                    tri_val = pt.get("TotalReturnsIndex") or pt.get("TotalReturnIndex")
                    if d_val and tri_val is not None:
                        try:
                            val_float = float(tri_val)
                            if val_float > 0:
                                records.append((bid, d_val, val_float, 1))
                        except (ValueError, TypeError):
                            pass

                if records:
                    # Staging insert into market.benchmark_values
                    await conn.execute(
                        """
                        CREATE TEMP TABLE IF NOT EXISTS staging_bench (
                            benchmark_id SMALLINT,
                            value_date DATE,
                            value NUMERIC(18,4),
                            ingest_id BIGINT
                        ) ON COMMIT PRESERVE ROWS;
                        TRUNCATE TABLE staging_bench;
                        """
                    )
                    await conn.copy_records_to_table(
                        "staging_bench",
                        records=records,
                        columns=["benchmark_id", "value_date", "value", "ingest_id"],
                    )
                    await conn.execute(
                        """
                        INSERT INTO market.benchmark_values (benchmark_id, value_date, value, ingest_id)
                        SELECT benchmark_id, value_date, value, ingest_id FROM staging_bench
                        ON CONFLICT (benchmark_id, value_date) DO UPDATE
                        SET value = EXCLUDED.value;
                        DROP TABLE IF EXISTS staging_bench;
                        """
                    )
                    total_ingested += len(records)
                    summary[code] = len(records)
                    logger.info("Ingested %d daily TRI values for %s.", len(records), code)

        # Map portfolios to their category benchmark in ref.benchmark_history
        logger.info("Mapping portfolios to Tier-1 category benchmarks in ref.benchmark_history...")
        mapped = await conn.execute(
            """
            INSERT INTO ref.benchmark_history (portfolio_id, valid_from, valid_to, benchmark_id, tier)
            SELECT p.portfolio_id, '2013-01-01'::date, '9999-12-31'::date,
                   CASE 
                       WHEN c.code = 'EQ_SMALL_CAP' THEN 1 -- NIFTY_SMALLCAP_250_TRI
                       WHEN c.code = 'EQ_MID_CAP' THEN 4   -- NIFTY_MIDCAP_150_TRI
                       WHEN c.code = 'EQ_LARGE_CAP' THEN 3 -- NIFTY_50_TRI
                       ELSE 2                             -- NIFTY_500_TRI (Flexi, Multi, Large & Mid, ELSS, etc.)
                   END,
                   1
            FROM ref.portfolios p
            JOIN (
                SELECT portfolio_id, category_id,
                       ROW_NUMBER() OVER (PARTITION BY portfolio_id ORDER BY valid_to DESC) as rn
                FROM ref.category_history
            ) ch ON p.portfolio_id = ch.portfolio_id AND ch.rn = 1
            JOIN ref.categories c ON ch.category_id = c.category_id
            WHERE NOT EXISTS (
                SELECT 1 FROM ref.benchmark_history bh WHERE bh.portfolio_id = p.portfolio_id
            );
            """
        )
        logger.info("Benchmark history mapping result: %s", mapped)

        logger.info("Benchmark TRI ingestion complete. Total rows: %d.", total_ingested)
        return {"total_benchmark_values": total_ingested, "benchmarks": summary}
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(ingest_benchmark_tri_history())
