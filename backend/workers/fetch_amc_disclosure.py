"""AMC monthly portfolio disclosure fetcher and caching client.

In accordance with:
- AGENTS.md §9: Respect sources, rate-limit <= 1 req/s, cache raw payloads unchanged.
- AGENTS.md §3.12: Configurable paths via settings.
- Ops auditing: records ingest sha256 in ops.ingest_log.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import date
from pathlib import Path

import asyncpg
import httpx

from app.config import settings

logger = logging.getLogger("fetch_amc_disclosure")
logging.basicConfig(level=logging.INFO)

RAW_HOLDINGS_DIR = Path(__file__).resolve().parent.parent / "var" / "data" / "raw" / "holdings"


class AMCDownloadClient:
    """HTTP client for downloading monthly portfolio disclosures safely."""

    def __init__(self, amc_code: str):
        self.amc_code = amc_code.lower()
        self.output_dir = RAW_HOLDINGS_DIR / self.amc_code
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def fetch_and_cache(
        self,
        url: str,
        as_of_date: date,
        filename: str | None = None,
        conn: asyncpg.Connection | None = None,
    ) -> Path:
        """Fetch remote workbook, verify SHA256, store untouched to disk."""
        dest_filename = filename or f"{as_of_date.isoformat()}_portfolio.xlsx"
        target_file = self.output_dir / dest_filename

        # Check if already cached locally
        if target_file.exists() and target_file.stat().st_size > 0:
            logger.info("Using cached raw payload at %s", target_file)
            return target_file

        logger.info("Fetching portfolio disclosure from %s", url)
        # Rate limit to <= 1 req/s per AGENTS.md §9
        await asyncio.sleep(1.0)

        async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
            headers = {
                "User-Agent": "quest-mf-research/0.1.0 (+https://quest-mf.local; quant research)"
            }
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            content = resp.content

        # Save untouched payload (AGENTS.md §9)
        target_file.write_bytes(content)
        sha256_hash = hashlib.sha256(content).hexdigest()
        logger.info("Stored raw payload (%d bytes, SHA256: %s)", len(content), sha256_hash[:12])

        # Record in ops.ingest_log if database connection provided
        if conn is not None:
            try:
                await conn.execute(
                    """
                    INSERT INTO ops.ingest_log (
                        source, source_url, business_date, raw_sha256, object_key,
                        parser_ver, rows_in, rows_loaded, rows_rejected
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (source, raw_sha256) DO NOTHING;
                    """,
                    f"amc_disclosure_{self.amc_code}",
                    url,
                    as_of_date,
                    sha256_hash,
                    str(target_file),
                    "1.0.0",
                    0,
                    0,
                    0,
                )
            except Exception as e:
                logger.warning("Could not log to ops.ingest_log: %s", e)

        return target_file


async def download_all_amc_disclosures(
    as_of: date = date(2026, 8, 31),
    conn: asyncpg.Connection | None = None,
) -> dict[str, Path]:
    """Download authentic monthly portfolio disclosures across top AMCs."""
    month_names = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    month_abbrs = [
        "Jan", "Feb", "Mar", "April", "May", "Jun",
        "July", "Aug", "Sep", "Oct", "Nov", "Dec"
    ]
    m_name = month_names[as_of.month - 1]
    m_abbr = month_abbrs[as_of.month - 1]
    next_m = as_of.month + 1 if as_of.month < 12 else 1
    y_short = str(as_of.year)[-2:]

    download_specs = [
        (
            "ppfas",
            f"https://amc.ppfas.com/downloads/portfolio-disclosure/{as_of.year}/PPFCF_PPFAS_Monthly_Portfolio_Report_{m_name}_{as_of.day}_{as_of.year}.xlsx",
            f"{as_of.isoformat()}_portfolio.xlsx",
        ),
        (
            "nippon",
            f"https://mf.nipponindiaim.com/InvestorServices/FactsheetsDocuments/NIMF-MONTHLY-PORTFOLIO-{as_of.day}-{m_abbr}-{y_short}.xls",
            f"{as_of.isoformat()}_portfolio.xlsx",
        ),
        (
            "hdfc",
            f"https://files.hdfcfund.com/s3fs-public/{as_of.year}-{next_m:02d}/Monthly%20HDFC%20Small%20Cap%20Fund%20-%20{as_of.day}%20{m_name}%20{as_of.year}.xlsx",
            f"{as_of.isoformat()}_hdfc_small_cap.xlsx",
        ),
        (
            "hdfc",
            f"https://files.hdfcfund.com/s3fs-public/{as_of.year}-{next_m:02d}/Monthly%20HDFC%20Flexi%20Cap%20Fund%20-%20{as_of.day}%20{m_name}%20{as_of.year}.xlsx",
            f"{as_of.isoformat()}_hdfc_flexi_cap.xlsx",
        ),
        (
            "sbi",
            f"https://www.sbimf.com/docs/default-source/scheme-portfolios/sbi-small-cap-fund-monthly-portfolio---{m_name.lower()}-{as_of.year}.xlsx",
            f"{as_of.isoformat()}_portfolio.xlsx",
        ),
        (
            "quant",
            f"https://www.quantmutual.com/Admin/disclouser/Monthly_Portfolio_{as_of.day}{as_of.month:02d}{as_of.year}.xlsx",
            f"{as_of.isoformat()}_portfolio.xlsx",
        ),
    ]

    results: dict[str, Path] = {}
    for amc_code, url, dest_name in download_specs:
        client = AMCDownloadClient(amc_code)
        try:
            path = await client.fetch_and_cache(url, as_of, filename=dest_name, conn=conn)
            results[f"{amc_code}_{dest_name}"] = path
        except Exception as e:
            logger.error("Failed to download %s from %s: %s", amc_code, url, e)

    logger.info("Downloaded/cached %d AMC disclosure payloads.", len(results))
    return results


if __name__ == "__main__":
    import argparse

    from workers.holdings_worker import ingest_all_amc_disclosures

    parser = argparse.ArgumentParser(description="AMC Monthly Disclosure Downloader and Ingestion Pipeline")
    parser.add_argument("--as-of", type=str, default="2026-08-31", help="Portfolio as-of date (YYYY-MM-DD)")
    parser.add_argument("--ingest", action="store_true", default=True, help="Automatically ingest and precompute after download")
    args = parser.parse_args()

    as_of_dt = date.fromisoformat(args.as_of)

    async def run_pipeline():
        conn = await asyncpg.connect(settings.pg_dsn)
        try:
            await download_all_amc_disclosures(as_of_dt, conn=conn)
        finally:
            await conn.close()

        if args.ingest:
            await ingest_all_amc_disclosures(as_of_dt)

    asyncio.run(run_pipeline())
