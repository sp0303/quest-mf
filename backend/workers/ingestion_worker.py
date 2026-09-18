"""AMFI and MFAPI data ingestion worker.

Responsibilities:
1. Ingest daily AMFI NAV text feed (portal.amfiindia.com/spages/NAVAll.txt).
2. Parse SEBI category headers and AMC groups.
3. Identify and register canonical schemes (Direct Plan + Growth Option only, Rule Q7, Test L).
4. Pull multi-year daily NAV history from MFAPI (api.mfapi.in).
5. Reconcile AMFI latest NAV vs MFAPI to verify < 0.01% error (Phase 1 exit criteria).
6. Perform high-performance COPY upsert into market.nav_history.
7. Record audit metadata in ops.ingest_log.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import asyncpg
import httpx
from questmf_quant.returns import validate_canonical_scheme

from app.config import settings

logger = logging.getLogger("ingestion_worker")
logging.basicConfig(level=logging.INFO)

AMFI_PORTAL_URL = "https://portal.amfiindia.com/spages/NAVAll.txt"
MFAPI_BASE_URL = "https://api.mfapi.in/mf"

CATEGORY_CODE_MAP = {
    "Small Cap Fund": ("EQ_SMALL_CAP", 1),
    "Mid Cap Fund": ("EQ_MID_CAP", 2),
    "Large Cap Fund": ("EQ_LARGE_CAP", 3),
    "Flexi Cap Fund": ("EQ_FLEXI_CAP", 4),
    "ELSS": ("EQ_ELSS", 5),
    "Multi Cap Fund": ("EQ_MULTI_CAP", 6),
    "Large & Mid Cap Fund": ("EQ_LARGE_MID_CAP", 7),
    "Focused Fund": ("EQ_FOCUSED", 8),
}


@dataclass
class AmfiParsedScheme:
    scheme_code: int
    isin_payout: str | None
    isin_reinvest: str | None
    scheme_name: str
    nav: float
    nav_date: date
    amc_name: str
    category_label: str
    category_code: str
    category_id: int
    plan: str
    option: str
    is_canonical: bool


def parse_amfi_nav_date(d_str: str) -> date | None:
    """Parse AMFI date string (e.g. '17-Sep-2026' or '17-09-2026')."""
    d_str = d_str.strip()
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(d_str, fmt).date()
        except ValueError:
            pass
    return None


def parse_amfi_feed(raw_text: str) -> tuple[list[AmfiParsedScheme], int]:
    """Parse raw AMFI NAVAll.txt into validated scheme records."""
    lines = raw_text.splitlines()
    parsed_schemes: list[AmfiParsedScheme] = []
    rejected_count = 0

    current_amc = "Unknown AMC"
    current_category_label = "Equity Scheme"
    current_category_code = "EQ_FLEXI_CAP"
    current_category_id = 4

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Header check (e.g. Open Ended Schemes (Equity Scheme - Small Cap Fund))
        if line.startswith("Open Ended Schemes") or line.startswith("Close Ended Schemes"):
            # Extract category
            for cat_key, (code, cid) in CATEGORY_CODE_MAP.items():
                if cat_key.lower() in line.lower():
                    current_category_label = cat_key
                    current_category_code = code
                    current_category_id = cid
                    break
            continue

        # AMC name line (does not contain semicolons)
        if ";" not in line:
            if len(line) > 3 and not line.startswith("Scheme Code"):
                current_amc = line
            continue

        parts = [p.strip() for p in line.split(";")]
        if len(parts) < 6 or parts[0].lower() == "scheme code":
            continue

        if len(parts) >= 8:
            code_str, isin1, isin2, name, plan_str, option_str, nav_str, date_str = parts[:8]
        else:
            code_str, isin1, isin2, name, nav_str, date_str = parts[:6]
            plan_str = "Direct Plan" if "direct" in name.lower() else "Regular Plan"
            option_str = (
                "IDCW" if "idcw" in name.lower() or "dividend" in name.lower() else "Growth"
            )

        try:
            scheme_code = int(code_str)
            nav_val = float(nav_str)
            nav_d = parse_amfi_nav_date(date_str)
            if not nav_d or nav_val <= 0:
                rejected_count += 1
                continue
        except (ValueError, TypeError):
            rejected_count += 1
            continue

        name_lower = f"{name} {plan_str} {option_str}".lower()
        plan = "DIRECT" if "direct" in name_lower else "REGULAR"

        if "idcw" in name_lower or "dividend" in name_lower:
            option = "IDCW"
        elif "bonus" in name_lower:
            option = "BONUS"
        else:
            option = "GROWTH"

        # Rule Q7 & Test L: Canonical series = Direct-Growth only.
        is_canonical = False
        if plan == "DIRECT" and option == "GROWTH":
            try:
                validate_canonical_scheme(plan, option, is_canonical=True)
                is_canonical = True
            except ValueError:
                is_canonical = False

        parsed_schemes.append(
            AmfiParsedScheme(
                scheme_code=scheme_code,
                isin_payout=isin1.strip() if isin1.strip() and isin1.strip() != "-" else None,
                isin_reinvest=isin2.strip() if isin2.strip() and isin2.strip() != "-" else None,
                scheme_name=name.strip(),
                nav=nav_val,
                nav_date=nav_d,
                amc_name=current_amc.strip(),
                category_label=current_category_label,
                category_code=current_category_code,
                category_id=current_category_id,
                plan=plan,
                option=option,
                is_canonical=is_canonical,
            )
        )

    return parsed_schemes, rejected_count


def reconcile_amfi_vs_mfapi(amfi_nav: float, mfapi_nav: float) -> float:
    """Calculate relative reconciliation difference between AMFI and MFAPI.

    Phase 1 Exit Criteria: reconciliation error < 0.01% (0.0001).
    """
    if amfi_nav <= 0 or mfapi_nav <= 0:
        return 1.0
    return abs(amfi_nav - mfapi_nav) / amfi_nav


async def fetch_amfi_raw_feed() -> tuple[str, str]:
    """Fetch raw AMFI NAVAll.txt with redirect handling and SHA256 checksum."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) QuestMF/0.2.0"}
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, verify=False) as client:
        resp = await client.get(AMFI_PORTAL_URL, headers=headers)
        resp.raise_for_status()
        raw_text = resp.text

    sha256 = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    return raw_text, sha256


async def fetch_mfapi_history(scheme_code: int) -> dict[str, Any] | None:
    """Fetch full daily historical NAV series from MFAPI."""
    headers = {"User-Agent": "QuestMF/0.2.0"}
    url = f"{MFAPI_BASE_URL}/{scheme_code}"
    async with httpx.AsyncClient(timeout=15.0, verify=False) as client:
        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning("MFAPI fetch failed for scheme %d: %s", scheme_code, e)
    return None


async def ingest_amfi_and_historical(
    max_history_schemes: int = 15,
) -> dict[str, Any]:
    """Execute complete ingestion pipeline with AMFI feed, MFAPI history, and reconciliation."""
    logger.info("Starting AMFI & MFAPI ingestion pipeline...")
    conn = await asyncpg.connect(settings.pg_dsn)
    try:
        # 1. Fetch raw AMFI feed
        raw_text, sha256 = await fetch_amfi_raw_feed()
        schemes, rejected = parse_amfi_feed(raw_text)
        logger.info("Parsed %d schemes from AMFI feed (%d rejected).", len(schemes), rejected)

        # 2. Check ops.ingest_log (idempotence)
        existing_log = await conn.fetchrow(
            "SELECT ingest_id FROM ops.ingest_log WHERE source = 'AMFI' AND raw_sha256 = $1;",
            sha256,
        )
        if existing_log:
            logger.info(
                "AMFI feed with hash %s already ingested in run #%d.",
                sha256[:12],
                existing_log["ingest_id"],
            )
            ingest_id = existing_log["ingest_id"]
            await conn.execute(
                """
                UPDATE ops.ingest_log
                SET rows_loaded = $2, rows_rejected = $3, rows_in = $4
                WHERE ingest_id = $1;
                """,
                ingest_id,
                len(schemes),
                rejected,
                len(schemes) + rejected,
            )
        else:
            log_row = await conn.fetchrow(
                """
                INSERT INTO ops.ingest_log (
                    source, source_url, business_date, raw_sha256, object_key,
                    parser_ver, rows_in, rows_loaded, rows_rejected
                ) VALUES (
                    'AMFI', $1, now()::date, $2, $3,
                    'v2_amfi_parser', $4, $5, $6
                ) RETURNING ingest_id;
                """,
                AMFI_PORTAL_URL,
                sha256,
                f"raw_ingest/amfi/{date.today().isoformat()}_{sha256[:8]}.txt",
                len(schemes) + rejected,
                len(schemes),
                rejected,
            )
            ingest_id = log_row["ingest_id"]

        # 3. Ensure categories exist in ref.categories
        for cat_label, (cat_code, cat_id) in CATEGORY_CODE_MAP.items():
            await conn.execute(
                """
                INSERT INTO ref.categories (category_id, code, label, asset_class)
                VALUES ($1, $2, $3, 'EQUITY')
                ON CONFLICT (category_id) DO NOTHING;
                """,
                cat_id,
                cat_code,
                cat_label,
            )

        # 4. Upsert AMCs
        amc_names = {s.amc_name for s in schemes if s.amc_name}
        for amc in amc_names:
            await conn.execute(
                """
                INSERT INTO ref.amcs (name) VALUES ($1)
                ON CONFLICT (name) DO NOTHING;
                """,
                amc,
            )

        amc_rows = await conn.fetch("SELECT amc_id, name FROM ref.amcs;")
        amc_map = {r["name"]: r["amc_id"] for r in amc_rows}

        # 5. Filter canonical schemes in equity categories
        canonical_equity = [
            s for s in schemes if s.is_canonical and s.category_code.startswith("EQ_")
        ]
        logger.info("Found %d canonical Direct-Growth equity schemes.", len(canonical_equity))

        # 6. Upsert Portfolios & Schemes
        reconciliation_results = []
        nav_records_to_insert = []

        # Target sample of canonical schemes for multi-year daily history ingestion
        selected_for_history = canonical_equity[:max_history_schemes]

        for s in selected_for_history:
            amc_id = amc_map.get(s.amc_name, 1)
            # Use scheme code as base portfolio id
            pid = s.scheme_code // 10

            # Insert portfolio
            await conn.execute(
                """
                INSERT INTO ref.portfolios (portfolio_id, display_name, amc_id, launch_date)
                VALUES ($1, $2, $3, '2013-01-01')
                ON CONFLICT (portfolio_id) DO UPDATE SET display_name = EXCLUDED.display_name;
                """,
                pid,
                s.scheme_name.replace(" - Direct Plan - Growth Option", "")
                .replace(" - Direct Plan - Growth", "")
                .replace(" Direct Growth", ""),
                amc_id,
            )

            # Insert scheme
            await conn.execute(
                """
                INSERT INTO ref.schemes (
                    scheme_code, portfolio_id, isin_payout, isin_reinvest,
                    scheme_name, plan, option, status, is_canonical
                ) VALUES ($1, $2, $3, $4, $5, 'DIRECT', 'GROWTH', 'ACTIVE', true)
                ON CONFLICT (scheme_code) DO UPDATE
                SET status = 'ACTIVE', is_canonical = true;
                """,
                s.scheme_code,
                pid,
                s.isin_payout,
                s.isin_reinvest,
                s.scheme_name,
            )

            # Insert category history mapping
            await conn.execute(
                """
                INSERT INTO ref.category_history (portfolio_id, valid_from, valid_to, category_id, mapping_confidence)
                VALUES ($1, '2018-01-01', '9999-12-31', $2, 1.0)
                ON CONFLICT DO NOTHING;
                """,
                pid,
                s.category_id,
            )

            # Insert today's AMFI NAV
            nav_records_to_insert.append((s.scheme_code, s.nav_date, s.nav, ingest_id, 0))

            # 7. Pull MFAPI historical records & reconcile
            mfapi_data = await fetch_mfapi_history(s.scheme_code)
            if mfapi_data and "data" in mfapi_data:
                history_points = mfapi_data["data"]
                logger.info(
                    "Scheme %d: retrieved %d historical NAV points from MFAPI.",
                    s.scheme_code,
                    len(history_points),
                )

                # Check reconciliation on latest matching date
                if history_points:
                    latest_mfapi = history_points[0]
                    mfapi_d = parse_amfi_nav_date(latest_mfapi["date"])
                    mfapi_val = float(latest_mfapi["nav"])

                    if mfapi_d == s.nav_date:
                        diff = reconcile_amfi_vs_mfapi(s.nav, mfapi_val)
                        reconciliation_results.append(
                            {
                                "scheme_code": s.scheme_code,
                                "scheme_name": s.scheme_name,
                                "amfi_nav": s.nav,
                                "mfapi_nav": mfapi_val,
                                "diff_pct": diff * 100,
                                "passed": diff < 0.0001,  # < 0.01%
                            }
                        )

                # Prepare multi-year history for insertion
                # Keep last 1,000 trading days (approx 4 years)
                for pt in history_points[:1000]:
                    pt_d = parse_amfi_nav_date(pt["date"])
                    pt_nav = float(pt["nav"])
                    if pt_d and pt_nav > 0:
                        nav_records_to_insert.append((s.scheme_code, pt_d, pt_nav, ingest_id, 0))

        # 8. High-performance COPY to market.nav_history using staging or bulk insert
        if nav_records_to_insert:
            # Deduplicate by (scheme_code, nav_date)
            unique_records = {}
            for code, d, nav, i_id, rev in nav_records_to_insert:
                unique_records[(code, d)] = (code, d, nav, i_id, rev)

            deduped_records = list(unique_records.values())
            logger.info("Inserting %d unique daily NAV records...", len(deduped_records))

            # Rule 7: Bulk writes use COPY -> staging -> MERGE/upsert.
            await conn.execute(
                """
                CREATE TEMP TABLE IF NOT EXISTS staging_nav (
                    scheme_code INT,
                    nav_date DATE,
                    nav NUMERIC(18,6),
                    ingest_id BIGINT,
                    revision SMALLINT
                ) ON COMMIT PRESERVE ROWS;
                TRUNCATE TABLE staging_nav;
                """
            )

            # Batch insert into staging in chunks of 5,000
            chunk_size = 5000
            for i in range(0, len(deduped_records), chunk_size):
                chunk = deduped_records[i : i + chunk_size]
                await conn.copy_records_to_table(
                    "staging_nav",
                    records=chunk,
                    columns=["scheme_code", "nav_date", "nav", "ingest_id", "revision"],
                )

            # Merge from staging into market.nav_history
            await conn.execute(
                """
                INSERT INTO market.nav_history (scheme_code, nav_date, nav, ingest_id, revision)
                SELECT scheme_code, nav_date, nav, ingest_id, revision FROM staging_nav
                ON CONFLICT (scheme_code, nav_date) DO UPDATE
                SET nav = EXCLUDED.nav,
                    ingest_id = EXCLUDED.ingest_id,
                    revision = market.nav_history.revision + 1;
                DROP TABLE IF EXISTS staging_nav;
                """
            )

        logger.info("AMFI & MFAPI ingestion completed successfully.")
        return {
            "ingest_id": ingest_id,
            "canonical_equity_schemes": len(canonical_equity),
            "reconciled_schemes": len(reconciliation_results),
            "reconciliation_summary": reconciliation_results,
            "total_nav_records_ingested": len(nav_records_to_insert),
        }
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(ingest_amfi_and_historical(max_history_schemes=15))
