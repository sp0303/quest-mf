"""AMFI and MFAPI data ingestion worker.

Responsibilities:
1. Ingest daily AMFI NAV text feed (portal.amfiindia.com/spages/NAVAll.txt).
2. Parse SEBI category headers across all official equity categories.
3. Identify and register canonical schemes (Direct Plan + Growth Option only, Rule Q7, Test L).
4. Pull multi-year daily NAV history from MFAPI (api.mfapi.in) with TLS verification & rate limiting (AGENTS.md §9).
5. Store raw untouched payloads to filesystem before parsing (AGENTS.md §9).
6. Reconcile AMFI latest NAV vs MFAPI to verify < 0.01% error (Phase 1 exit criteria).
7. Collision-free portfolio mapping and high-performance COPY upsert into market.nav_history.
8. Record audit metadata in ops.ingest_log.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import asyncpg
import httpx
from questmf_quant.returns import validate_canonical_scheme

from app.config import settings

logger = logging.getLogger("ingestion_worker")
logging.basicConfig(level=logging.INFO)

AMFI_PORTAL_URL = "https://portal.amfiindia.com/spages/NAVAll.txt"
MFAPI_BASE_URL = "https://api.mfapi.in/mf"

RAW_STORAGE_DIR = Path(__file__).resolve().parent.parent / "var" / "data" / "raw"

# Exhaustive SEBI Equity Category Mapping
CATEGORY_CODE_MAP: dict[str, tuple[str, int, str]] = {
    "Small Cap": ("EQ_SMALL_CAP", 1, "Small Cap Fund"),
    "Mid Cap": ("EQ_MID_CAP", 2, "Mid Cap Fund"),
    "Large Cap": ("EQ_LARGE_CAP", 3, "Large Cap Fund"),
    "Flexi Cap": ("EQ_FLEXI_CAP", 4, "Flexi Cap Fund"),
    "ELSS": ("EQ_ELSS", 5, "ELSS (Tax Saving)"),
    "Multi Cap": ("EQ_MULTI_CAP", 6, "Multi Cap Fund"),
    "Large & Mid Cap": ("EQ_LARGE_MID_CAP", 7, "Large & Mid Cap Fund"),
    "Focused": ("EQ_FOCUSED", 8, "Focused Fund"),
    "Dividend Yield": ("EQ_DIVIDEND_YIELD", 9, "Dividend Yield Fund"),
    "Value": ("EQ_VALUE", 10, "Value Fund"),
    "Contra": ("EQ_CONTRA", 11, "Contra Fund"),
    "Sectoral": ("EQ_SECTORAL_THEMATIC", 12, "Sectoral / Thematic Fund"),
    "Thematic": ("EQ_SECTORAL_THEMATIC", 12, "Sectoral / Thematic Fund"),
    "Index Fund": ("EQ_INDEX", 13, "Index Fund"),
    "ETF": ("EQ_ETF", 14, "Equity ETF"),
}


class AsyncRateLimiter:
    """Async rate limiter ensuring <= max_rate_per_second per AGENTS.md §9."""

    def __init__(self, requests_per_second: float = 1.0):
        self.interval = 1.0 / requests_per_second
        self._lock = asyncio.Lock()
        self._last_call = 0.0

    async def wait(self) -> None:
        async with self._lock:
            loop = asyncio.get_running_loop()
            now = loop.time()
            elapsed = now - self._last_call
            if elapsed < self.interval:
                await asyncio.sleep(self.interval - elapsed)
            self._last_call = loop.time()


_amfi_rate_limiter = AsyncRateLimiter(requests_per_second=1.0)
_mfapi_rate_limiter = AsyncRateLimiter(requests_per_second=1.0)


def store_raw_payload(source: str, payload_bytes: bytes, filename: str) -> tuple[str, str]:
    """Store raw unparsed payload to filesystem and return (sha256, rel_storage_path).

    Adheres strictly to AGENTS.md §9: store raw payloads unchanged before parsing.
    """
    sha256 = hashlib.sha256(payload_bytes).hexdigest()
    today_str = date.today().isoformat()
    dest_dir = RAW_STORAGE_DIR / source.lower() / today_str
    dest_dir.mkdir(parents=True, exist_ok=True)
    file_path = dest_dir / filename
    file_path.write_bytes(payload_bytes)
    rel_path = f"var/data/raw/{source.lower()}/{today_str}/{filename}"
    return sha256, rel_path


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
    """Parse raw AMFI NAVAll.txt into validated scheme records across all SEBI categories."""
    lines = raw_text.splitlines()
    parsed_schemes: list[AmfiParsedScheme] = []
    rejected_count = 0

    current_amc = "Unknown AMC"
    current_category_label = "Flexi Cap Fund"
    current_category_code = "EQ_FLEXI_CAP"
    current_category_id = 4

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Header check (e.g. Open Ended Schemes (Equity Scheme - Small Cap Fund))
        if line.startswith("Open Ended Schemes") or line.startswith("Close Ended Schemes"):
            matched = False
            for cat_key, (code, cid, label) in CATEGORY_CODE_MAP.items():
                if cat_key.lower() in line.lower():
                    current_category_label = label
                    current_category_code = code
                    current_category_id = cid
                    matched = True
                    break
            if not matched and "equity" in line.lower():
                current_category_label = "Flexi Cap Fund"
                current_category_code = "EQ_FLEXI_CAP"
                current_category_id = 4
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


async def fetch_amfi_raw_feed() -> tuple[str, str, str]:
    """Fetch raw AMFI NAVAll.txt with TLS verification, rate-limit, and payload persistence."""
    await _amfi_rate_limiter.wait()
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) QuestMF/0.3.0"}
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, verify=True) as client:
        resp = await client.get(AMFI_PORTAL_URL, headers=headers)
        resp.raise_for_status()
        raw_bytes = resp.content
        raw_text = resp.text

    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    filename = f"{sha256[:16]}.txt"
    _, storage_rel_path = store_raw_payload("amfi", raw_bytes, filename)
    return raw_text, sha256, storage_rel_path


async def fetch_mfapi_history_with_client(
    client: httpx.AsyncClient,
    scheme_code: int,
    max_retries: int = 3,
) -> dict[str, Any] | None:
    """Fetch full daily historical NAV series with connection pooling, proactive rate limiting, and 429 backoff."""
    url = f"{MFAPI_BASE_URL}/{scheme_code}"
    headers = {"User-Agent": "QuestMF/0.3.1"}
    for attempt in range(max_retries):
        try:
            await _mfapi_rate_limiter.wait()
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                raw_bytes = resp.content
                store_raw_payload("mfapi", raw_bytes, f"scheme_{scheme_code}.json")
                return resp.json()
            elif resp.status_code == 429:
                wait_time = 2.0 * (attempt + 1)
                logger.warning(
                    "MFAPI 429 Too Many Requests for %d. Backing off %0.1fs...",
                    scheme_code,
                    wait_time,
                )
                await asyncio.sleep(wait_time)
            else:
                return None
        except Exception as e:
            if attempt == max_retries - 1:
                logger.warning("MFAPI fetch error for scheme %d: %s", scheme_code, e)
                return None
            await asyncio.sleep(1.0 * (attempt + 1))
    return None


async def fetch_mfapi_history(scheme_code: int) -> dict[str, Any] | None:
    """Convenience wrapper for single scheme fetch."""
    async with httpx.AsyncClient(timeout=15.0, verify=True) as client:
        return await fetch_mfapi_history_with_client(client, scheme_code)


async def flush_nav_records_to_db(
    conn: asyncpg.Connection,
    records: list[tuple[int, date, float, int, int]],
) -> int:
    """Flush a list of NAV records into market.nav_history via staging and COPY (Rule 7)."""
    if not records:
        return 0

    unique_records = {}
    for code, d, nav, i_id, rev in records:
        unique_records[(code, d)] = (code, d, nav, i_id, rev)
    deduped = list(unique_records.values())

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

    chunk_size = 5000
    for i in range(0, len(deduped), chunk_size):
        chunk = deduped[i : i + chunk_size]
        await conn.copy_records_to_table(
            "staging_nav",
            records=chunk,
            columns=["scheme_code", "nav_date", "nav", "ingest_id", "revision"],
        )

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
    return len(deduped)


async def ingest_amfi_and_historical(
    max_history_schemes: int | None = None,
    concurrency: int = 5,
) -> dict[str, Any]:
    """Execute complete ingestion pipeline with AMFI feed, parallel MFAPI history, and reconciliation."""
    logger.info(
        "Starting AMFI & MFAPI ingestion pipeline (parallel concurrency=%d)...", concurrency
    )
    conn = await asyncpg.connect(settings.pg_dsn)
    try:
        # 1. Fetch raw AMFI feed & persist unparsed bytes
        raw_text, sha256, storage_key = await fetch_amfi_raw_feed()
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
                storage_key,
                len(schemes) + rejected,
                len(schemes),
                rejected,
            )
            ingest_id = log_row["ingest_id"]

        # 3. Ensure categories exist in ref.categories across all SEBI categories
        for _cat_key, (cat_code, cat_id, cat_label) in CATEGORY_CODE_MAP.items():
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

        # 6. Upsert Portfolios & Schemes.
        # `selected_for_history` gates registration + today's AMFI NAV point and always
        # covers every canonical scheme, regardless of max_history_schemes. The separate
        # `schemes_for_deep_history` below scopes the expensive MFAPI multi-year backfill:
        # 0 means "delta only" (no MFAPI calls), None means "unlimited" (full backfill).
        selected_for_history = canonical_equity

        if max_history_schemes is None:
            schemes_for_deep_history = canonical_equity
            logger.info(
                "Deep MFAPI history: ALL %d canonical schemes (max_history_schemes=None).",
                len(schemes_for_deep_history),
            )
        elif max_history_schemes > 0:
            schemes_for_deep_history = canonical_equity[:max_history_schemes]
            logger.info(
                "Deep MFAPI history: %d of %d canonical schemes (max_history_schemes=%d).",
                len(schemes_for_deep_history),
                len(canonical_equity),
                max_history_schemes,
            )
        else:
            schemes_for_deep_history = []
            logger.info("Deep MFAPI history: SKIPPED (max_history_schemes=0, delta-only run).")

        # Synchronize portfolio_id sequence to prevent collisions with historical IDs
        await conn.execute(
            """
            SELECT setval(
                pg_get_serial_sequence('ref.portfolios', 'portfolio_id'),
                COALESCE((SELECT max(portfolio_id) FROM ref.portfolios), 1) + 1,
                false
            );
            """
        )

        amfi_today_records = []
        for s in selected_for_history:
            amc_id = amc_map.get(s.amc_name, 1)

            clean_name = (
                s.scheme_name.replace(" - Direct Plan - Growth Option", "")
                .replace(" - Direct Plan - Growth", "")
                .replace(" Direct Growth", "")
                .replace(" - Direct - Growth", "")
                .strip()
            )

            p_row = await conn.fetchrow(
                """
                SELECT portfolio_id FROM ref.schemes WHERE scheme_code = $1
                UNION
                SELECT portfolio_id FROM ref.portfolios WHERE display_name = $2 AND amc_id = $3
                LIMIT 1;
                """,
                s.scheme_code,
                clean_name,
                amc_id,
            )
            if p_row:
                pid = p_row["portfolio_id"]
            else:
                new_p = await conn.fetchrow(
                    """
                    INSERT INTO ref.portfolios (display_name, amc_id, launch_date)
                    VALUES ($1, $2, '2013-01-01')
                    RETURNING portfolio_id;
                    """,
                    clean_name,
                    amc_id,
                )
                pid = new_p["portfolio_id"]

            await conn.execute(
                """
                INSERT INTO ref.schemes (
                    scheme_code, portfolio_id, isin_payout, isin_reinvest,
                    scheme_name, plan, option, status, is_canonical
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, 'ACTIVE', $8)
                ON CONFLICT (scheme_code) DO UPDATE
                SET portfolio_id = EXCLUDED.portfolio_id,
                    status = 'ACTIVE',
                    plan = EXCLUDED.plan,
                    option = EXCLUDED.option,
                    is_canonical = EXCLUDED.is_canonical;
                """,
                s.scheme_code,
                pid,
                s.isin_payout,
                s.isin_reinvest,
                s.scheme_name,
                s.plan,
                s.option,
                s.is_canonical,
            )

            await conn.execute(
                """
                INSERT INTO ref.category_history (portfolio_id, valid_from, valid_to, category_id, mapping_confidence)
                VALUES ($1, '2018-01-01', '9999-12-31', $2, 1.0)
                ON CONFLICT DO NOTHING;
                """,
                pid,
                s.category_id,
            )

            amfi_today_records.append((s.scheme_code, s.nav_date, s.nav, ingest_id, 0))

        # Flush today's AMFI NAV points
        await flush_nav_records_to_db(conn, amfi_today_records)

        # Rule Q7: Deduplicate canonical schemes so exactly one scheme per portfolio is canonical
        await conn.execute("""
            WITH ranked_canonical AS (
                SELECT scheme_code, portfolio_id,
                       ROW_NUMBER() OVER (
                           PARTITION BY portfolio_id
                           ORDER BY 
                               CASE WHEN scheme_name ILIKE '%segregated%' THEN 1 ELSE 0 END,
                               scheme_code DESC
                       ) as rn
                FROM ref.schemes
                WHERE is_canonical = true
            )
            UPDATE ref.schemes s
            SET is_canonical = false
            FROM ranked_canonical r
            WHERE s.scheme_code = r.scheme_code AND r.rn > 1;
        """)

        # 7. Parallel Multi-Year Historical Fetch via MFAPI
        sem = asyncio.Semaphore(concurrency)
        client_limits = httpx.Limits(
            max_connections=concurrency * 2, max_keepalive_connections=concurrency
        )
        reconciliation_results = []
        total_historical_rows = 0

        async with httpx.AsyncClient(
            timeout=20.0, verify=True, limits=client_limits
        ) as http_client:

            async def process_scheme_history(
                scheme: AmfiParsedScheme,
            ) -> tuple[list[tuple[int, date, float, int, int]], dict[str, Any] | None]:
                async with sem:
                    records: list[tuple[int, date, float, int, int]] = []
                    recon_info: dict[str, Any] | None = None
                    mfapi_data = await fetch_mfapi_history_with_client(
                        http_client, scheme.scheme_code
                    )

                    if mfapi_data and "data" in mfapi_data:
                        history_points = mfapi_data["data"]
                        if history_points:
                            latest_mfapi = history_points[0]
                            mfapi_d = parse_amfi_nav_date(latest_mfapi["date"])
                            mfapi_val = float(latest_mfapi["nav"])

                            if mfapi_d == scheme.nav_date:
                                diff = reconcile_amfi_vs_mfapi(scheme.nav, mfapi_val)
                                recon_info = {
                                    "scheme_code": scheme.scheme_code,
                                    "scheme_name": scheme.scheme_name,
                                    "amfi_nav": scheme.nav,
                                    "mfapi_nav": mfapi_val,
                                    "diff_pct": diff * 100,
                                    "passed": diff < 0.0001,
                                }

                            for pt in history_points[:1000]:
                                pt_d = parse_amfi_nav_date(pt["date"])
                                pt_nav = float(pt["nav"])
                                if pt_d and pt_nav > 0:
                                    records.append((scheme.scheme_code, pt_d, pt_nav, ingest_id, 0))

                    return records, recon_info

            # Process in batches of 50 schemes to stream DB writes incrementally
            batch_size = 50
            total_schemes = len(schemes_for_deep_history)

            for b_start in range(0, total_schemes, batch_size):
                b_end = min(b_start + batch_size, total_schemes)
                batch_schemes = schemes_for_deep_history[b_start:b_end]

                tasks = [process_scheme_history(s) for s in batch_schemes]
                results = await asyncio.gather(*tasks)

                batch_nav_records: list[tuple[int, date, float, int, int]] = []
                for recs, recon in results:
                    batch_nav_records.extend(recs)
                    if recon:
                        reconciliation_results.append(recon)

                # Flush batch records to PostgreSQL
                flushed = await flush_nav_records_to_db(conn, batch_nav_records)
                total_historical_rows += flushed

                pct = (b_end / total_schemes) * 100
                logger.info(
                    "[%d/%d schemes | %0.1f%%] Flushed %d historical NAV rows (total historical: %d).",
                    b_end,
                    total_schemes,
                    pct,
                    flushed,
                    total_historical_rows,
                )

        logger.info(
            "AMFI & MFAPI parallel ingestion complete. Ingested %d total historical rows across %d schemes.",
            total_historical_rows,
            total_schemes,
        )

        return {
            "ingest_id": ingest_id,
            "canonical_equity_schemes": len(canonical_equity),
            "reconciled_schemes": len(reconciliation_results),
            "reconciliation_summary": reconciliation_results[:10],
            "total_nav_records_ingested": total_historical_rows + len(amfi_today_records),
        }
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(ingest_amfi_and_historical(concurrency=5))
