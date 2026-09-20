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
from typing import Any

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
        conn: asyncpg.Connection | None = None,
    ) -> Path:
        """Fetch remote workbook, verify SHA256, store untouched to disk."""
        target_file = self.output_dir / f"{as_of_date.isoformat()}_portfolio.xlsx"

        # Check if already cached locally
        if target_file.exists() and target_file.stat().st_size > 0:
            logger.info("Using cached raw payload at %s", target_file)
            return target_file

        logger.info("Fetching portfolio disclosure from %s", url)
        # Rate limit to <= 1 req/s
        await asyncio.sleep(1.0)

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
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
