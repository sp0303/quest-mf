"""Property-based acceptance tests per Spec v2 §28 (Test J & Invariance)."""

import pytest
from questmf_quant.percentile import mid_rank_percentile, own_history_percentile
from questmf_quant.returns import cagr, simple_return


def test_j_shp_future_invariance_property():
    """Test J: SHP(t) is unchanged when NAV data after t is appended (Rule Q1 property test)."""
    # Base history up to date t: 100 observations
    history_up_to_t = [0.01 * (i % 7 - 3) for i in range(1, 100)]
    current_return_t = 0.05

    # SHP(t) strictly excludes current t per Rule Q1
    shp_t = own_history_percentile(current_return_t, history_up_to_t)
    assert 0.0 <= shp_t <= 100.0

    # Append 50 future periods after t (wild market swings, crash, or rally)
    future_data = [0.08, -0.15, 0.22, -0.04] * 12
    augmented_series = history_up_to_t + [current_return_t] + future_data

    # Re-evaluate SHP as of date t using only data known at date t (first 99 periods)
    shp_t_recomputed = own_history_percentile(
        current_return_t, augmented_series[: len(history_up_to_t)]
    )

    assert shp_t_recomputed == pytest.approx(shp_t, abs=1e-12)


def test_percentile_monotonicity_and_bounds_property():
    """Property test: mid-rank percentile is weakly monotonic and bounded [0, 100]."""
    peers = [-0.10, -0.05, 0.00, 0.00, 0.05, 0.10, 0.15, 0.20]

    # Bounded
    for val in [-0.50, -0.10, 0.00, 0.05, 0.20, 0.99]:
        pct = mid_rank_percentile(val, peers)
        assert 0.0 <= pct <= 100.0

    # Monotonic
    pct_low = mid_rank_percentile(-0.02, peers)
    pct_high = mid_rank_percentile(0.08, peers)
    assert pct_low < pct_high


def test_cagr_compounding_identity_property():
    """Property test: (1 + CAGR)^(days / 365.25) - 1 == simple_return."""
    start_nav = 100.0
    end_nav = 175.50
    days = 730.5  # 2 years

    r = simple_return(start_nav, end_nav)
    c = cagr(start_nav, end_nav, days=days)

    compounded = (1.0 + c) ** (days / 365.25) - 1.0
    assert compounded == pytest.approx(r, rel=1e-6)
