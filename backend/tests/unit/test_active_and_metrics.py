"""Benchmark-relative persistence features and per-fund metric windows (Q1, Q4, Q5, Q12)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from questmf_quant.active import active_stats, rolling_active_returns
from questmf_quant.friction import calculate_net_return, compute_stt_equity

from workers.compute_metrics import OBS_3Y, compute_fund_features


def _business_days(start: date, n: int) -> list[date]:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def test_fund_always_beating_benchmark_has_100pct_beat():
    days = _business_days(date(2022, 1, 3), 400)
    fund = {d: 100.0 * (1.0008**i) for i, d in enumerate(days)}
    bench = {d: 100.0 * (1.0003**i) for i, d in enumerate(days)}
    actives = rolling_active_returns(days, fund, bench, months=3)
    stats = active_stats(actives)
    assert stats.beat_pct == pytest.approx(100.0)
    assert stats.median_active > 0


def test_active_window_uses_identical_dates_for_fund_and_benchmark():
    days = _business_days(date(2024, 1, 1), 80)
    fund = {d: 100.0 for d in days}
    bench = {d: 100.0 for d in days}
    # Identical series -> every active return is exactly zero (Q5).
    assert all(a == 0.0 for a in rolling_active_returns(days, fund, bench, months=3))


def test_too_few_windows_is_none_not_zero():
    stats = active_stats([0.01, 0.02])
    assert stats.beat_pct is None and stats.median_active is None


def test_short_history_has_no_three_year_features():
    days = _business_days(date(2025, 1, 1), 300)  # ~14 months
    nav = {d: 10.0 * (1.0005**i) for i, d in enumerate(days)}
    f = compute_fund_features(nav, nav, ter=0.007)
    assert f["obs_count"] < OBS_3Y
    assert f["ir_3y"] is None and f["mdd_3y"] is None and f["cagr_3y"] is None
    assert f["beta_1y"] == pytest.approx(1.0)
    assert f["exit_load_days"] is None  # no genuine source yet


def test_alpha_needs_benchmark_on_fund_end_date():
    days = _business_days(date(2025, 1, 1), 120)
    nav = {d: 10.0 * (1.001**i) for i, d in enumerate(days)}
    stale_bench = {d: 100.0 for d in days[:-5]}  # benchmark stops 5 days early
    assert compute_fund_features(nav, stale_bench, ter=None)["alpha_3m"] is None
    fresh_bench = {d: 100.0 for d in days}
    assert compute_fund_features(nav, fresh_bench, ter=None)["alpha_3m"] is not None


def test_stt_on_equity_fund_redemption_is_0_001_pct():
    assert compute_stt_equity(100_000.0) == pytest.approx(1.0)
    res = calculate_net_return(100_000.0, buy_nav=10.0, sell_nav=11.0, days_held=400)
    assert res.stt == pytest.approx(res.gross_proceeds * 0.00001)
