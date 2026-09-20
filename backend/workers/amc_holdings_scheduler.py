"""Automated AMC monthly portfolio holdings scheduler and CLI.

Orchestrates monthly ingestion across registered AMCs:
- Ingests SEBI monthly portfolio disclosures
- Executes BaseAMCParser contract gates H1–H8
- Precomputes holdings.portfolio_summary for sub-millisecond API queries (Rule 1)

Usage:
    python -m workers.amc_holdings_scheduler --amc all
    python -m workers.amc_holdings_scheduler --amc nippon --as-of-date 2026-08-31
    python -m workers.amc_holdings_scheduler --amc hdfc --file path/to/hdfc.xlsx
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import asyncpg

from app.config import settings
from workers.holdings_worker import (
    ingest_monthly_holdings,
    precompute_portfolio_summary,
)
from workers.parsers import (
    AxisParser,
    BandhanParser,
    DSPParser,
    HDFCParser,
    ICICIPrudentialParser,
    InvescoParser,
    KotakParser,
    NipponIndiaParser,
    PPFASParser,
    QuantParser,
    SBIParser,
    TataParser,
)

logger = logging.getLogger("amc_holdings_scheduler")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


@dataclass(frozen=True)
class AMCRegistration:
    amc_code: str
    amc_name: str
    parser_factory: Any
    portfolio_schemes: dict[int, str]  # portfolio_id -> scheme_name_filter


REGISTERED_AMCS: dict[str, AMCRegistration] = {
    "nippon": AMCRegistration(
        amc_code="nippon",
        amc_name="Nippon India Mutual Fund",
        parser_factory=NipponIndiaParser,
        portfolio_schemes={101: "Small Cap"},
    ),
    "quant": AMCRegistration(
        amc_code="quant",
        amc_name="Quant Mutual Fund",
        parser_factory=QuantParser,
        portfolio_schemes={102: "Small Cap"},
    ),
    "hdfc": AMCRegistration(
        amc_code="hdfc",
        amc_name="HDFC Asset Management",
        parser_factory=HDFCParser,
        portfolio_schemes={103: "Small Cap", 202: "Flexi Cap"},
    ),
    "icici": AMCRegistration(
        amc_code="icici",
        amc_name="ICICI Prudential AMC",
        parser_factory=ICICIPrudentialParser,
        portfolio_schemes={113: "Bluechip"},
    ),
    "sbi": AMCRegistration(
        amc_code="sbi",
        amc_name="SBI Funds Management",
        parser_factory=SBIParser,
        portfolio_schemes={104: "Small Cap"},
    ),
    "kotak": AMCRegistration(
        amc_code="kotak",
        amc_name="Kotak Mahindra AMC",
        parser_factory=KotakParser,
        portfolio_schemes={105: "Small Cap"},
    ),
    "axis": AMCRegistration(
        amc_code="axis",
        amc_name="Axis Asset Management",
        parser_factory=AxisParser,
        portfolio_schemes={106: "Small Cap"},
    ),
    "tata": AMCRegistration(
        amc_code="tata",
        amc_name="Tata Mutual Fund",
        parser_factory=TataParser,
        portfolio_schemes={107: "Small Cap"},
    ),
    "bandhan": AMCRegistration(
        amc_code="bandhan",
        amc_name="Bandhan Mutual Fund",
        parser_factory=BandhanParser,
        portfolio_schemes={108: "Small Cap"},
    ),
    "invesco": AMCRegistration(
        amc_code="invesco",
        amc_name="Invesco Mutual Fund",
        parser_factory=InvescoParser,
        portfolio_schemes={109: "Small Cap"},
    ),
    "dsp": AMCRegistration(
        amc_code="dsp",
        amc_name="DSP Mutual Fund",
        parser_factory=DSPParser,
        portfolio_schemes={110: "Small Cap"},
    ),
    "ppfas": AMCRegistration(
        amc_code="ppfas",
        amc_name="PPFAS Mutual Fund",
        parser_factory=PPFASParser,
        portfolio_schemes={201: "Flexi Cap"},
    ),
}


def compute_default_dates() -> tuple[date, date]:
    """Compute default (as_of_date, disclosed_date) for the latest completed month."""
    today = date.today()
    # First day of current month minus 1 day = last day of preceding month
    first_of_current = date(today.year, today.month, 1)
    as_of = first_of_current - timedelta(days=1)
    # SEBI disclosure deadline is 10th of current month
    disclosed = date(today.year, today.month, 10)
    return as_of, disclosed


async def run_amc_ingestion(
    conn: asyncpg.Connection,
    registration: AMCRegistration,
    workbook_data: Any,
    as_of: date,
    disclosed: date,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Execute ingestion for a single AMC across its registered portfolios."""
    parser = registration.parser_factory()
    results: dict[int, Any] = {}

    for pid, scheme_filter in registration.portfolio_schemes.items():
        logger.info(
            "Processing %s -> Portfolio ID %d ('%s')", registration.amc_name, pid, scheme_filter
        )
        amc_dir = (
            Path(__file__).resolve().parent.parent
            / "var"
            / "data"
            / "raw"
            / "holdings"
            / registration.amc_code
        )
        scheme_slug = scheme_filter.lower().replace(" ", "_")
        scheme_path = amc_dir / f"{as_of.isoformat()}_{registration.amc_code}_{scheme_slug}.xlsx"

        curr_data = workbook_data
        if scheme_path.exists():
            curr_data = scheme_path.read_bytes()

        if curr_data is not None:
            parse_res = parser.parse_workbook(
                curr_data,
                portfolio_id=pid,
                as_of_date=as_of,
                disclosed_date=disclosed,
                scheme_name_filter=scheme_filter,
            )
        else:
            logger.warning(
                "No authentic disclosure workbook found for %s (PID %d). Skipping per Rule Q16.",
                registration.amc_name,
                pid,
            )
            results[pid] = {"status": "SKIPPED", "reason": "No authentic disclosure workbook found"}
            continue

        if not parse_res.valid:
            logger.warning(
                "Validation failed for portfolio %d: %s", pid, parse_res.validation_message
            )
            results[pid] = {"status": "FAILED", "reason": parse_res.validation_message}
            continue

        if not dry_run:
            await ingest_monthly_holdings(conn, parse_res.holdings)
            await precompute_portfolio_summary(conn, pid, as_of)
            results[pid] = {
                "status": "SUCCESS",
                "holdings_count": len(parse_res.holdings),
                "equity_count": parse_res.equity_count,
                "total_weight": parse_res.total_weight,
            }
        else:
            results[pid] = {
                "status": "DRY_RUN",
                "holdings_count": len(parse_res.holdings),
                "total_weight": parse_res.total_weight,
            }

    return results


async def main() -> None:
    """CLI entry point for monthly AMC holdings scheduler."""
    parser = argparse.ArgumentParser(description="AMC Monthly Portfolio Disclosure Scheduler")
    parser.add_argument(
        "--amc", default="all", choices=list(REGISTERED_AMCS.keys()) + ["all"], help="Target AMC"
    )
    parser.add_argument("--as-of-date", help="Portfolio as-of date (YYYY-MM-DD)")
    parser.add_argument("--file", help="Path to local Excel disclosure file")
    parser.add_argument(
        "--dry-run", action="store_true", help="Parse and validate without DB writes"
    )
    args = parser.parse_args()

    default_as_of, default_disclosed = compute_default_dates()
    as_of = date.fromisoformat(args.as_of_date) if args.as_of_date else default_as_of
    disclosed = default_disclosed

    logger.info(
        "Starting AMC Holdings Scheduler (As of: %s, Disclosed: %s, Dry Run: %s)",
        as_of,
        disclosed,
        args.dry_run,
    )

    amcs_to_run = (
        list(REGISTERED_AMCS.values()) if args.amc == "all" else [REGISTERED_AMCS[args.amc]]
    )
    file_bytes = Path(args.file).read_bytes() if args.file and Path(args.file).exists() else None

    conn = await asyncpg.connect(settings.pg_dsn)
    try:
        total_success = 0
        total_portfolios = 0
        for reg in amcs_to_run:
            wb_bytes = file_bytes
            if wb_bytes is None:
                cached_path = (
                    Path(__file__).resolve().parent.parent
                    / "var"
                    / "data"
                    / "raw"
                    / "holdings"
                    / reg.amc_code
                    / f"{as_of.isoformat()}_portfolio.xlsx"
                )
                if cached_path.exists():
                    wb_bytes = cached_path.read_bytes()
                    logger.info(
                        "Found cached disclosure file for %s at %s", reg.amc_name, cached_path
                    )

            res = await run_amc_ingestion(
                conn, reg, wb_bytes, as_of, disclosed, dry_run=args.dry_run
            )
            for pid, status_info in res.items():
                total_portfolios += 1
                if status_info.get("status") in ("SUCCESS", "DRY_RUN"):
                    total_success += 1
                    logger.info(
                        "✅ Portfolio %d: %s (Holdings: %d, Total Weight: %.2f%%)",
                        pid,
                        status_info["status"],
                        status_info["holdings_count"],
                        status_info["total_weight"],
                    )
                else:
                    logger.error("❌ Portfolio %d: FAILED (%s)", pid, status_info.get("reason"))

        logger.info(
            "Completed: %d/%d portfolios successfully processed.", total_success, total_portfolios
        )
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
