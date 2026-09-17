from datetime import date

from questmf_quant.calendar.windows import (
    compute_eligible_obs_window_count,
    find_boundary_nav_date,
    resolve_calendar_start_date,
    resolve_obs_indices,
)


def test_h_calendar_month_eom_clipping():
    """Test H: CAL_1M ending 31 Mar resolves its target to 28/29 Feb (EOM clipping)."""
    # Leap year
    res_leap = resolve_calendar_start_date(date(2024, 3, 31), months=1)
    assert res_leap == date(2024, 2, 29)

    # Non-leap year
    res_non_leap = resolve_calendar_start_date(date(2023, 3, 31), months=1)
    assert res_non_leap == date(2023, 2, 28)

    # 3-month window from 31 May -> 28/29 Feb
    res_3m = resolve_calendar_start_date(date(2024, 5, 31), months=3)
    assert res_3m == date(2024, 2, 29)


def test_i_boundary_rule_on_or_before_and_staleness():
    """Test I: Boundary rule picks on-or-before, never after; staleness > limit -> None."""
    available_dates = [
        date(2024, 3, 20),
        date(2024, 3, 22),
        date(2024, 3, 25),  # Monday
        date(2024, 3, 26),
    ]

    # Target is Sunday 2024-03-24 -> should pick Friday 2024-03-22
    matched = find_boundary_nav_date(date(2024, 3, 24), available_dates, max_staleness_days=5)
    assert matched == date(2024, 3, 22)
    assert matched <= date(2024, 3, 24)

    # Never pick after target date (2024-03-25 must not be picked)
    assert matched != date(2024, 3, 25)

    # Staleness > limit -> returns None
    target_stale = date(2024, 3, 31)
    matched_stale = find_boundary_nav_date(target_stale, available_dates, max_staleness_days=3)
    # Latest available is 2024-03-26, difference is 5 days > 3 days limit
    assert matched_stale is None


def test_a_b_c_obs_window_rules():
    """Tests A, B, C: Observation window counting and indices."""
    # Test A & B: for N = 90, end_idx = 100
    indices = resolve_obs_indices(end_idx=100, n_obs=90, total_obs=150)
    assert indices is not None
    start_idx, end_idx = indices
    assert end_idx == 100
    # Test B: start_idx == end_idx - (n_obs - 1) == 100 - 89 == 11
    assert start_idx == 100 - 89
    # Test A: count of observations is exactly 90
    assert (end_idx - start_idx + 1) == 90

    # Test C: for M observations, eligible windows is M - N + 1
    m_obs = 150
    n_obs = 90
    count = compute_eligible_obs_window_count(m_obs, n_obs)
    assert count == 150 - 90 + 1 == 61
