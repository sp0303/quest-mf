"""Seed rich sample mutual fund data for development and demonstration."""

import asyncio
import random
from datetime import date, timedelta

import asyncpg
from questmf_quant.drawdown import max_drawdown
from questmf_quant.percentile import mid_rank_percentile, own_history_percentile
from questmf_quant.returns import cagr, simple_return
from questmf_quant.risk import (
    information_ratio,
)
from questmf_quant.scoring import (
    DEFAULT_BASELINE_MODEL,
    assign_quadrant,
    compute_composite_score,
)

from app.config import settings

SAMPLE_FUNDS = [
    {
        "portfolio_id": 101,
        "name": "Nippon India Small Cap Fund",
        "amc": "Nippon India Mutual Fund",
        "category_code": "EQ_SMALL_CAP",
        "benchmark": "NIFTY_SMALLCAP_250_TRI",
        "ter": 0.0071,
        "aum_cr": 58400.0,
        "base_nav": 18.5,
        "drift": 0.0009,
        "vol": 0.012,
        "exit_load": 0.01,
        "exit_days": 365,
    },
    {
        "portfolio_id": 102,
        "name": "Quant Small Cap Fund",
        "amc": "Quant Mutual Fund",
        "category_code": "EQ_SMALL_CAP",
        "benchmark": "NIFTY_SMALLCAP_250_TRI",
        "ter": 0.0077,
        "aum_cr": 26800.0,
        "base_nav": 35.2,
        "drift": 0.0011,
        "vol": 0.016,
        "exit_load": 0.01,
        "exit_days": 365,
    },
    {
        "portfolio_id": 103,
        "name": "HDFC Small Cap Fund",
        "amc": "HDFC Mutual Fund",
        "category_code": "EQ_SMALL_CAP",
        "benchmark": "NIFTY_SMALLCAP_250_TRI",
        "ter": 0.0069,
        "aum_cr": 34100.0,
        "base_nav": 22.1,
        "drift": 0.0008,
        "vol": 0.011,
        "exit_load": 0.01,
        "exit_days": 365,
    },
    {
        "portfolio_id": 104,
        "name": "SBI Small Cap Fund",
        "amc": "SBI Mutual Fund",
        "category_code": "EQ_SMALL_CAP",
        "benchmark": "NIFTY_SMALLCAP_250_TRI",
        "ter": 0.0068,
        "aum_cr": 31200.0,
        "base_nav": 40.0,
        "drift": 0.00075,
        "vol": 0.010,
        "exit_load": 0.01,
        "exit_days": 365,
    },
    {
        "portfolio_id": 105,
        "name": "Kotak Small Cap Fund",
        "amc": "Kotak Mahindra Mutual Fund",
        "category_code": "EQ_SMALL_CAP",
        "benchmark": "NIFTY_SMALLCAP_250_TRI",
        "ter": 0.0065,
        "aum_cr": 17800.0,
        "base_nav": 65.4,
        "drift": 0.00078,
        "vol": 0.0115,
        "exit_load": 0.01,
        "exit_days": 365,
    },
    {
        "portfolio_id": 106,
        "name": "Axis Small Cap Fund",
        "amc": "Axis Mutual Fund",
        "category_code": "EQ_SMALL_CAP",
        "benchmark": "NIFTY_SMALLCAP_250_TRI",
        "ter": 0.0055,
        "aum_cr": 23400.0,
        "base_nav": 28.3,
        "drift": 0.00065,
        "vol": 0.0095,
        "exit_load": 0.01,
        "exit_days": 365,
    },
    {
        "portfolio_id": 107,
        "name": "Tata Small Cap Fund",
        "amc": "Tata Mutual Fund",
        "category_code": "EQ_SMALL_CAP",
        "benchmark": "NIFTY_SMALLCAP_250_TRI",
        "ter": 0.0058,
        "aum_cr": 9500.0,
        "base_nav": 15.0,
        "drift": 0.00085,
        "vol": 0.0125,
        "exit_load": 0.01,
        "exit_days": 365,
    },
    {
        "portfolio_id": 108,
        "name": "Bandhan Small Cap Fund",
        "amc": "Bandhan Mutual Fund",
        "category_code": "EQ_SMALL_CAP",
        "benchmark": "NIFTY_SMALLCAP_250_TRI",
        "ter": 0.0062,
        "aum_cr": 6800.0,
        "base_nav": 12.5,
        "drift": 0.00088,
        "vol": 0.013,
        "exit_load": 0.01,
        "exit_days": 365,
    },
    {
        "portfolio_id": 109,
        "name": "Invesco India Smallcap Fund",
        "amc": "Invesco Mutual Fund",
        "category_code": "EQ_SMALL_CAP",
        "benchmark": "NIFTY_SMALLCAP_250_TRI",
        "ter": 0.0061,
        "aum_cr": 5400.0,
        "base_nav": 14.2,
        "drift": 0.00082,
        "vol": 0.012,
        "exit_load": 0.01,
        "exit_days": 365,
    },
    {
        "portfolio_id": 110,
        "name": "DSP Small Cap Fund",
        "amc": "DSP Mutual Fund",
        "category_code": "EQ_SMALL_CAP",
        "benchmark": "NIFTY_SMALLCAP_250_TRI",
        "ter": 0.0072,
        "aum_cr": 16200.0,
        "base_nav": 45.0,
        "drift": 0.00072,
        "vol": 0.0118,
        "exit_load": 0.01,
        "exit_days": 365,
    },
    {
        "portfolio_id": 201,
        "name": "Parag Parikh Flexi Cap Fund",
        "amc": "PPFAS Mutual Fund",
        "category_code": "EQ_FLEXI_CAP",
        "benchmark": "NIFTY_500_TRI",
        "ter": 0.0062,
        "aum_cr": 72500.0,
        "base_nav": 25.0,
        "drift": 0.00075,
        "vol": 0.0085,
        "exit_load": 0.02,
        "exit_days": 730,
    },
    {
        "portfolio_id": 202,
        "name": "HDFC Flexi Cap Fund",
        "amc": "HDFC Mutual Fund",
        "category_code": "EQ_FLEXI_CAP",
        "benchmark": "NIFTY_500_TRI",
        "ter": 0.0082,
        "aum_cr": 61200.0,
        "base_nav": 350.0,
        "drift": 0.00072,
        "vol": 0.0090,
        "exit_load": 0.01,
        "exit_days": 365,
    },
]


async def seed_data():
    conn = await asyncpg.connect(settings.pg_dsn)
    try:
        print("Connected to PostgreSQL for seeding...")
        # Get category map
        cat_rows = await conn.fetch("SELECT category_id, code FROM ref.categories;")
        cat_map = {r["code"]: r["category_id"] for r in cat_rows}

        # Seed Benchmarks
        benchmarks = [
            ("NIFTY_SMALLCAP_250_TRI", "Nifty Smallcap 250 TRI", "NSE", True),
            ("NIFTY_500_TRI", "Nifty 500 TRI", "NSE", True),
            ("NIFTY_50_TRI", "Nifty 50 TRI", "NSE", True),
        ]
        for b_code, b_label, b_prov, is_tri in benchmarks:
            await conn.execute(
                """
                INSERT INTO ref.benchmarks (code, label, provider, is_tri)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (code) DO NOTHING;
            """,
                b_code,
                b_label,
                b_prov,
                is_tri,
            )

        # Generate business calendar for last 3 years (approx 750 trading days)
        today = date.today()
        trading_dates: list[date] = []
        cur = today - timedelta(days=1100)
        while cur <= today:
            if cur.weekday() < 5:  # Mon-Fri
                trading_dates.append(cur)
            cur += timedelta(days=1)

        # Generate benchmark values
        random.seed(42)
        bench_navs = {}
        for b_code, _, _, _ in benchmarks:
            b_val = 1000.0
            series = []
            for d in trading_dates:
                shock = random.gauss(0.0005, 0.009)
                b_val *= 1.0 + shock
                series.append((d, round(b_val, 4)))
            bench_navs[b_code] = dict(series)

        # Insert AMCs and Portfolios
        amc_map = {}
        for fund in SAMPLE_FUNDS:
            amc_name = fund["amc"]
            if amc_name not in amc_map:
                row = await conn.fetchrow(
                    """
                    INSERT INTO ref.amcs (name) VALUES ($1)
                    ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                    RETURNING amc_id;
                """,
                    amc_name,
                )
                amc_map[amc_name] = row["amc_id"]

            amc_id = amc_map[amc_name]
            p_id = fund["portfolio_id"]
            cat_id = cat_map.get(fund["category_code"], 1)

            await conn.execute(
                """
                INSERT INTO ref.portfolios (portfolio_id, display_name, amc_id, launch_date)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (portfolio_id) DO UPDATE SET display_name = EXCLUDED.display_name;
            """,
                p_id,
                fund["name"],
                amc_id,
                date(2015, 1, 1),
            )

            scheme_code = p_id * 1000 + 1
            await conn.execute(
                """
                INSERT INTO ref.schemes (scheme_code, portfolio_id, scheme_name, plan, option, status, is_canonical)
                VALUES ($1, $2, $3, 'DIRECT', 'GROWTH', 'ACTIVE', true)
                ON CONFLICT (scheme_code) DO NOTHING;
            """,
                scheme_code,
                p_id,
                fund["name"] + " - Direct Plan - Growth",
            )

            # Load rule
            await conn.execute(
                """
                INSERT INTO ref.load_rules (scheme_code, valid_from, exit_load_rate, exit_load_days, rule_text)
                VALUES ($1, '2020-01-01', $2, $3, '1% for redemption within 365 days')
                ON CONFLICT DO NOTHING;
            """,
                scheme_code,
                fund["exit_load"],
                fund["exit_days"],
            )

            # Generate fund NAV history
            nav = fund["base_nav"]
            nav_records = []
            f_navs: list[float] = []
            for d in trading_dates:
                shock = random.gauss(fund["drift"], fund["vol"])
                nav *= 1.0 + shock
                f_navs.append(nav)
                nav_records.append((scheme_code, d, round(nav, 6), 1, 0))

            await conn.copy_records_to_table(
                "nav_history",
                records=nav_records,
                schema_name="market",
                columns=["scheme_code", "nav_date", "nav", "ingest_id", "revision"],
            )

            # Calculate rolling returns & metrics for screener snapshot
            r_1m = simple_return(f_navs[-22], f_navs[-1])
            r_3m = simple_return(f_navs[-64], f_navs[-1])
            r_6m = simple_return(f_navs[-127], f_navs[-1])
            r_1y = simple_return(f_navs[-253], f_navs[-1])
            c_3y = cagr(f_navs[-755], f_navs[-1], days=1095.0)

            # Benchmark comparison
            b_map = bench_navs[fund["benchmark"]]
            b_start = b_map[trading_dates[-64]]
            b_end = b_map[trading_dates[-1]]
            b_r3m = simple_return(b_start, b_end)
            alpha_3m = r_3m - b_r3m

            # Drawdown & risk
            mdd, _, _ = max_drawdown(f_navs[-755:])
            returns_daily = [f_navs[i] / f_navs[i - 1] - 1.0 for i in range(1, len(f_navs))]
            bench_daily = [
                b_map[trading_dates[i]] / b_map[trading_dates[i - 1]] - 1.0
                for i in range(1, len(trading_dates))
            ]

            ir_3y = information_ratio(returns_daily[-755:], bench_daily[-755:])

            # Past 3M returns for SHP
            past_3m_returns = [
                simple_return(f_navs[i - 63], f_navs[i]) for i in range(63, len(f_navs) - 1)
            ]
            shp = own_history_percentile(r_3m, past_3m_returns, min_history_count=20) or 50.0

            # Store fund temporary metrics
            fund["r_1m"] = r_1m
            fund["r_3m"] = r_3m
            fund["r_6m"] = r_6m
            fund["r_1y"] = r_1y
            fund["cagr_3y"] = c_3y
            fund["alpha_3m"] = alpha_3m
            fund["mdd_3y"] = mdd
            fund["ir_3y"] = ir_3y
            fund["shp_3m"] = shp

        # Compute Peer Percentiles per category
        small_cap_funds = [f for f in SAMPLE_FUNDS if f["category_code"] == "EQ_SMALL_CAP"]
        sc_returns = {f["portfolio_id"]: f["r_3m"] for f in small_cap_funds}
        ref_values = list(sc_returns.values())

        for f in SAMPLE_FUNDS:
            pid = f["portfolio_id"]
            if f["category_code"] == "EQ_SMALL_CAP":
                peer_pct = mid_rank_percentile(f["r_3m"], ref_values)
            else:
                peer_pct = 75.0

            shp = f["shp_3m"]
            quadrant = assign_quadrant(peer_pct, shp)

            factor_scores = {
                "momentum": min(100.0, max(0.0, 50.0 + f["r_3m"] * 250.0)),
                "persistence": shp,
                "quality": min(100.0, max(0.0, 50.0 + f["ir_3y"] * 25.0)),
                "risk": min(100.0, max(0.0, 100.0 + f["mdd_3y"] * 200.0)),
                "cost": min(100.0, max(0.0, 100.0 - f["ter"] * 5000.0)),
            }
            composite, conf = compute_composite_score(
                factor_scores, DEFAULT_BASELINE_MODEL, obs_count=800
            )

            cat_id = cat_map.get(f["category_code"], 1)

            # Insert screener snapshot
            await conn.execute(
                """
                INSERT INTO scoring.screener_snapshot (
                    as_of_date, model_version, category_id, portfolio_id, fund_name, amc,
                    ret_1m, ret_3m, ret_6m, ret_1y, cagr_3y, shp_3m, peer_pct_3m, alpha_3m,
                    ir_3y, mdd_3y, ter, exit_load_rate, exit_load_days, composite, confidence, quadrant, flags, investable
                ) VALUES (
                    $1, 'v1_baseline', $2, $3, $4, $5,
                    $6, $7, $8, $9, $10, $11, $12, $13,
                    $14, $15, $16, $17, $18, $19, $20, $21, 0, true
                )
                ON CONFLICT (as_of_date, model_version, category_id, portfolio_id) DO UPDATE
                SET composite = EXCLUDED.composite, peer_pct_3m = EXCLUDED.peer_pct_3m;
            """,
                today,
                cat_id,
                pid,
                f["name"],
                f["amc"],
                f["r_1m"],
                f["r_3m"],
                f["r_6m"],
                f["r_1y"],
                f["cagr_3y"],
                f["shp_3m"],
                peer_pct,
                f["alpha_3m"],
                f["ir_3y"],
                f["mdd_3y"],
                f["ter"],
                f["exit_load"],
                f["exit_days"],
                composite,
                conf,
                quadrant,
            )

        # Update scoring.latest
        await conn.execute(
            """
            INSERT INTO scoring.latest (model_version, as_of_date, published_at)
            VALUES ('v1_baseline', $1, now())
            ON CONFLICT (model_version) DO UPDATE
            SET as_of_date = EXCLUDED.as_of_date, published_at = now();
        """,
            today,
        )

        # Seed AMFI market caps and portfolio holdings
        try:
            from workers.amfi_marketcap_worker import BASELINE_SECURITIES, StockMarketCapEntry, upsert_market_caps
            from workers.holdings_worker import (
                RawHoldingEntry,
                SAMPLE_FUND_PROFILES,
                SAMPLE_PORTFOLIO_HOLDINGS,
                ingest_monthly_holdings,
                precompute_portfolio_summary,
                upsert_fund_profile,
            )

            mcap_entries = [
                StockMarketCapEntry(
                    isin=isin,
                    name=name,
                    nse_symbol=sym,
                    sector=sec,
                    industry=ind,
                    market_cap_rank=rank,
                    avg_market_cap_cr=mcap,
                    valid_from=date(today.year, 1, 1),
                )
                for isin, name, sym, sec, ind, rank, mcap in BASELINE_SECURITIES
            ]
            await upsert_market_caps(conn, mcap_entries)

            holdings_as_of = date(today.year, today.month - 1 if today.month > 1 else 12, 28)
            disclosed = date(today.year, today.month, 10)
            for pid, holdings in SAMPLE_PORTFOLIO_HOLDINGS.items():
                entries = [
                    RawHoldingEntry(
                        portfolio_id=pid,
                        as_of_date=holdings_as_of,
                        isin=isin,
                        security_name=name,
                        asset_type=atype,
                        sector=sec,
                        quantity=100000.0,
                        market_value_lakhs=round(pct * 500.0, 2),
                        pct_nav=pct,
                        disclosed_date=disclosed,
                    )
                    for isin, name, atype, sec, pct in holdings
                ]
                await ingest_monthly_holdings(conn, entries)
                await precompute_portfolio_summary(conn, pid, holdings_as_of)

            for prof in SAMPLE_FUND_PROFILES:
                await upsert_fund_profile(conn, prof)
            print("Market caps, holdings, and fund profiles seeded successfully!")
        except Exception as e:
            print(f"Notice: holdings seeding skipped: {e}")

        print("Sample mutual funds and historical data seeded successfully!")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed_data())
