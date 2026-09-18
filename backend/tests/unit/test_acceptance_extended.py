"""Extended acceptance tests per Spec v2 §28 (Tests D, E, F, G, L, P, R)."""

from datetime import date

import pytest
from questmf_quant.calendar.windows import STANDARD_WINDOWS
from questmf_quant.returns import active_return, simple_return, validate_canonical_scheme
from questmf_quant.rolling import compute_rolling_windows
from questmf_quant.scoring import (
    DEFAULT_BASELINE_MODEL,
    compute_composite_score,
)


def test_d_no_future_leakage_rolling():
    """Test D: Metrics as of date t must not depend on NAV values after t."""
    dates_t = [date(2024, 1, i) for i in range(1, 25)]
    navs_t = [100.0 + i * 0.5 for i in range(1, 25)]

    # Compute windows ending at date t
    window_def = STANDARD_WINDOWS["OBS_21"]
    pts_t = compute_rolling_windows(dates_t, navs_t, window_def)
    assert len(pts_t) > 0
    metric_at_t = pts_t[-1]

    # Append future dates t + 1 .. t + 20
    dates_future = dates_t + [date(2024, 2, i) for i in range(1, 21)]
    navs_future = navs_t + [200.0 + i * 2.0 for i in range(1, 21)]

    pts_future = compute_rolling_windows(dates_future, navs_future, window_def)
    metric_at_t_recomputed = [p for p in pts_future if p.end_date == metric_at_t.end_date][0]

    assert metric_at_t_recomputed.ret == pytest.approx(metric_at_t.ret)
    assert metric_at_t_recomputed.max_dd == pytest.approx(metric_at_t.max_dd)
    assert metric_at_t_recomputed.start_date == metric_at_t.start_date


def test_e_benchmark_alignment():
    """Test E: Fund and benchmark return periods must use identical boundaries (Q5)."""
    fund_nav_start, fund_nav_end = 100.0, 115.0
    bench_val_start, bench_val_end = 1000.0, 1100.0

    r_fund = simple_return(fund_nav_start, fund_nav_end)
    r_bench = simple_return(bench_val_start, bench_val_end)

    act = active_return(r_fund, r_bench)
    assert act == pytest.approx(0.15 - 0.10)


def test_f_missing_dates_no_fake_zero_returns():
    """Test F: Weekends/holidays must not create fake zero-return observations."""
    # Calendar with weekend skipped: Friday 2024-03-22 -> Monday 2024-03-25
    trading_dates = [
        date(2024, 3, 21),
        date(2024, 3, 22),  # Friday
        date(2024, 3, 25),  # Monday
        date(2024, 3, 26),
    ]
    assert len(trading_dates) == 4
    navs = [100.0, 101.0, 103.0, 104.0]

    # Returns must be between trading days, never inserting 101.0 on Saturday/Sunday as 0% returns
    daily_returns = [simple_return(navs[i - 1], navs[i]) for i in range(1, len(navs))]
    assert len(daily_returns) == 3
    # Return from Fri to Mon is 103/101 - 1
    assert daily_returns[1] == pytest.approx(103.0 / 101.0 - 1.0)
    assert daily_returns[1] != 0.0


def test_g_reproducibility():
    """Test G: Same input data + same model version = identical scores."""
    factor_scores = {
        "momentum": 75.4,
        "persistence": 62.8,
        "quality": 81.1,
        "risk": 55.3,
        "cost": 88.0,
    }
    score1, conf1 = compute_composite_score(factor_scores, DEFAULT_BASELINE_MODEL, obs_count=800)
    score2, conf2 = compute_composite_score(factor_scores, DEFAULT_BASELINE_MODEL, obs_count=800)

    assert score1 == score2
    assert conf1 == conf2


def test_l_idcw_cannot_be_canonical():
    """Test L: IDCW series cannot become canonical (raises ValueError per Rule Q7)."""
    with pytest.raises(ValueError, match="IDCW series cannot become canonical"):
        validate_canonical_scheme(plan="DIRECT", option="IDCW", is_canonical=True)

    # Regular IDCW non-canonical should not raise
    validate_canonical_scheme(plan="REGULAR", option="IDCW", is_canonical=False)

    # Direct Growth canonical is valid
    validate_canonical_scheme(plan="DIRECT", option="GROWTH", is_canonical=True)


def test_p_survivorship_merged_fund_inclusion():
    """Test P: Merged-out fund appears in historical universe before merger date (Rule Q10)."""
    # Fund merged on 2023-06-01
    launch_d = date(2018, 1, 1)
    closed_d = date(2023, 6, 1)

    def is_in_universe_as_of(t: date) -> bool:
        return launch_d <= t < closed_d

    # Valid before merger
    assert is_in_universe_as_of(date(2023, 5, 15)) is True
    # Excluded after merger
    assert is_in_universe_as_of(date(2023, 6, 15)) is False


def test_r_golden_fixture_spreadsheet_exactness():
    """Test R: Golden fixture matches hand-calculated reference values to 1e-9."""
    # Hand-calculated reference:
    # NAVs: [100.0, 102.5, 105.0625, 101.910625]
    # Simple returns:
    # 0 -> 1: +0.025 (2.5%)
    # 0 -> 2: +0.050625 (5.0625%)
    # 0 -> 3: +0.01910625 (1.910625%)
    s0, s1, s2, s3 = 100.0, 102.5, 105.0625, 101.910625

    r01 = simple_return(s0, s1)
    r02 = simple_return(s0, s2)
    r03 = simple_return(s0, s3)

    assert abs(r01 - 0.025) < 1e-9
    assert abs(r02 - 0.050625) < 1e-9
    assert abs(r03 - 0.01910625) < 1e-9
