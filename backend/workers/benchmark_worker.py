"""Benchmark TRI ingestion worker.

Provides dual-mode benchmark ingestion per ADR 0009:
- Option B (Canonical Production Default): AMFI Direct-Growth index-fund NAV proxies.
  100% compliant open data, zero scraping risk, zero license fees.
- Option A (Offline Research Only): Internal NSE website scraper.
  Strictly for private research / model validation; never exposed publicly.

Adheres strictly to Rule Q5 (Benchmarks are TRI).
"""

from __future__ import annotations

import argparse
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

# ==============================================================================
# OPTION B: AMFI Direct-Growth Index-Fund NAV Proxies (Production Canonical)
# Approved under ADR 0009: Clean open data without scraping or licensing risk.
# ==============================================================================
OPTION_B_PROXY_BENCHMARKS = {
    "NIFTY_50_INDEX_PROXY": {
        "benchmark_id": 3,
        "code": "NIFTY_50_INDEX_PROXY",
        "label": "Nifty 50 TRI (UTI Direct-G Index Proxy)",
        "scheme_code": 120716,  # UTI Nifty 50 Index Fund Direct-Growth
        "provider": "AMFI_INDEX_PROXY",
    },
    "NIFTY_MIDCAP_150_INDEX_PROXY": {
        "benchmark_id": 4,
        "code": "NIFTY_MIDCAP_150_INDEX_PROXY",
        "label": "Nifty Midcap 150 TRI (Motilal Direct-G Index Proxy)",
        "scheme_code": 147622,  # Motilal Oswal Nifty Midcap 150 Index Fund Direct-Growth
        "provider": "AMFI_INDEX_PROXY",
    },
    "NIFTY_SMALLCAP_250_INDEX_PROXY": {
        "benchmark_id": 1,
        "code": "NIFTY_SMALLCAP_250_INDEX_PROXY",
        "label": "Nifty Smallcap 250 TRI (Motilal Direct-G Index Proxy)",
        "scheme_code": 147623,  # Motilal Oswal Nifty Smallcap 250 Index Fund Direct-Growth
        "provider": "AMFI_INDEX_PROXY",
    },
    "NIFTY_500_INDEX_PROXY": {
        "benchmark_id": 2,
        "code": "NIFTY_500_INDEX_PROXY",
        "label": "Nifty 500 TRI (Motilal Direct-G Index Proxy)",
        "scheme_code": 147625,  # Motilal Oswal Nifty 500 Index Fund Direct-Growth
        "provider": "AMFI_INDEX_PROXY",
    },
}

# ==============================================================================
# OPTION A: NSE Indices Scraper (RESEARCH ONLY - ADR 0009)
# STRICTLY FOR OFFLINE RESEARCH / BACKTESTING. NEVER EXPOSE ON PUBLIC APIS.
# ==============================================================================
NIFTY_INDICES_URL = "https://www.niftyindices.com/Backpage/getTotalReturnIndexString"

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
    """[RESEARCH ONLY - ADR 0009 OPTION A] Fetch TRI daily values from Nifty Indices."""
    await _nse_rate_limiter.wait()
    if end_date is None:
        end_date = date.today().strftime("%d-%b-%Y")

    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        "Origin": "https://www.niftyindices.com",
        "Referer": "https://www.niftyindices.com/reports/historical-data",
    }
    payload = json.dumps(
        {
            "cinfo": json.dumps(
                {
                    "name": index_name,
                    "startDate": start_date,
                    "endDate": end_date,
                    "indexName": index_name,
                }
            )
        }
    )

    try:
        resp = await client.post(NIFTY_INDICES_URL, headers=headers, content=payload)
        if resp.status_code == 200:
            store_raw_payload(
                "benchmarks",
                resp.content,
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


async def ingest_option_b_proxies(conn: asyncpg.Connection) -> dict[str, int]:
    """[OPTION B - PRODUCTION] Synchronize benchmark series from AMFI Direct-Growth index funds."""
    logger.info("Executing Option B benchmark ingestion (AMFI Direct-Growth Proxies)...")
    summary: dict[str, int] = {}

    for _key, cfg in OPTION_B_PROXY_BENCHMARKS.items():
        bid = cfg["benchmark_id"]
        code = cfg["code"]
        label = cfg["label"]
        provider = cfg["provider"]
        scheme_code = cfg["scheme_code"]

        await conn.execute(
            """
            INSERT INTO ref.benchmarks (benchmark_id, code, label, provider, is_tri)
            VALUES ($1, $2, $3, $4, true)
            ON CONFLICT (benchmark_id) DO UPDATE
            SET code = EXCLUDED.code, label = EXCLUDED.label, provider = EXCLUDED.provider, is_tri = true;
            """,
            bid,
            code,
            label,
            provider,
        )

        res = await conn.execute(
            """
            INSERT INTO market.benchmark_values (benchmark_id, value_date, value, ingest_id)
            SELECT $1, nav_date, nav, 1
            FROM market.nav_history
            WHERE scheme_code = $2
            ON CONFLICT (benchmark_id, value_date) DO UPDATE
            SET value = EXCLUDED.value;
            """,
            bid,
            scheme_code,
        )
        count = int(res.split()[-1]) if res else 0
        summary[code] = count
        logger.info(
            "Synchronized %d proxy NAV points for %s (scheme %d).", count, label, scheme_code
        )

    return summary


async def ingest_option_a_nse_scrape(conn: asyncpg.Connection) -> dict[str, int]:
    """[OPTION A - RESEARCH ONLY] Ingest TRI series via rate-limited niftyindices.com scraping."""
    logger.info("Executing Option A benchmark scraper (Research Only)...")
    for code, (bid, _idx_name, label) in BENCHMARKS.items():
        await conn.execute(
            """
            INSERT INTO ref.benchmarks (benchmark_id, code, label, provider, is_tri)
            VALUES ($1, $2, $3, 'NSE_RESEARCH_SCRAPE', true)
            ON CONFLICT (benchmark_id) DO UPDATE
            SET code = EXCLUDED.code, label = EXCLUDED.label, is_tri = true;
            """,
            bid,
            code,
            label,
        )

    summary: dict[str, int] = {}
    client_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    }
    async with httpx.AsyncClient(
        timeout=45.0, follow_redirects=True, verify=True, headers=client_headers
    ) as client:
        for code, (bid, idx_name, _label) in BENCHMARKS.items():
            points = await fetch_nifty_tri_series(client, idx_name, start_date="01-Jan-2013")
            records = []
            for pt in points:
                d_val = parse_nifty_date(pt.get("Date", ""))
                tri_val = pt.get("TotalReturnsIndex") or pt.get("TotalReturnIndex")
                if d_val and tri_val is not None:
                    try:
                        v = float(tri_val)
                        if v > 0:
                            records.append((bid, d_val, v, 1))
                    except (ValueError, TypeError):
                        pass
            if records:
                await conn.copy_records_to_table(
                    "benchmark_values",
                    records=records,
                    columns=["benchmark_id", "value_date", "value", "ingest_id"],
                    schema="market",
                )
                summary[code] = len(records)
    return summary


async def map_portfolios_to_benchmarks(conn: asyncpg.Connection) -> str:
    """Map equity portfolios to their appropriate category benchmark in ref.benchmark_history."""
    res = await conn.execute(
        """
        INSERT INTO ref.benchmark_history (portfolio_id, valid_from, valid_to, benchmark_id, tier)
        SELECT p.portfolio_id, '2013-01-01'::date, '9999-12-31'::date,
               CASE 
                   WHEN c.code = 'EQ_SMALL_CAP' THEN 1 -- NIFTY_SMALLCAP_250
                   WHEN c.code = 'EQ_MID_CAP' THEN 4   -- NIFTY_MIDCAP_150
                   WHEN c.code = 'EQ_LARGE_CAP' THEN 3 -- NIFTY_50
                   ELSE 2                             -- NIFTY_500
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
    return res


async def ingest_benchmark_tri_history(source: str = "option_b_proxy") -> dict[str, Any]:
    """Ingest benchmark series. Defaults to Option B Direct-Growth proxies (ADR 0009)."""
    logger.info("Starting Benchmark Ingestion using source=%s...", source)
    conn = await asyncpg.connect(settings.pg_dsn)
    try:
        if source == "option_a_nse_scrape_research_only":
            summary = await ingest_option_a_nse_scrape(conn)
        else:
            summary = await ingest_option_b_proxies(conn)

        map_res = await map_portfolios_to_benchmarks(conn)
        logger.info("Benchmark mapping completed: %s", map_res)
        total_rows = sum(summary.values())
        return {"source": source, "total_rows": total_rows, "benchmarks": summary}
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest benchmark series (ADR 0009)")
    parser.add_argument(
        "--source",
        choices=["option_b_proxy", "option_a_nse_scrape_research_only"],
        default="option_b_proxy",
        help="Benchmark source: option_b_proxy (default, production) or option_a_nse_scrape_research_only",
    )
    args = parser.parse_args()
    asyncio.run(ingest_benchmark_tri_history(source=args.source))
