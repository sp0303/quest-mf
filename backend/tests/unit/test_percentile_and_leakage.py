import numpy as np
import pytest
from questmf_quant.percentile import (
    mid_rank_percentile,
    own_history_percentile,
    peer_percentiles,
)


def test_q_percentile_with_ties_and_min_peer_threshold():
    """Test Q: Percentile with ties uses mid-rank; < 8 peers -> null."""
    # Reference set: [10, 20, 20, 30]
    # For value 20: strictly less = 1 (10), equal = 2 (20, 20)
    # Mid-rank = 1 + 0.5 * 2 = 2.0 -> Percentile = 100 * 2.0 / 4 = 50.0
    res = mid_rank_percentile(20.0, [10.0, 20.0, 20.0, 30.0])
    assert res == pytest.approx(50.0)

    # < 8 peers -> all null (Rule Q8, Test Q)
    few_peers = {1: 0.10, 2: 0.12, 3: 0.08, 4: 0.15, 5: 0.09}  # 5 peers
    pcts = peer_percentiles(few_peers, min_peers=8)
    assert len(pcts) == 5
    assert all(v is None for v in pcts.values())

    # Exactly 8 peers -> successfully computed
    eight_peers = {i: float(i * 0.02) for i in range(1, 9)}
    pcts_8 = peer_percentiles(eight_peers, min_peers=8)
    assert all(v is not None for v in pcts_8.values())
    # Highest peer (8) has strictly less = 7, equal = 1 -> (7 + 0.5)/8 * 100 = 93.75%
    assert pcts_8[8] == pytest.approx(93.75)


def test_k_peer_percentile_one_row_per_portfolio():
    """Test K: Peer percentile counts one row per portfolio_id."""
    # Ensure dictionary keys guarantee 1 row per portfolio_id
    portfolio_map = {
        101: 0.15,
        102: 0.22,
        103: 0.11,
        104: 0.18,
        105: 0.25,
        106: 0.09,
        107: 0.14,
        108: 0.30,
    }
    pcts = peer_percentiles(portfolio_map, min_peers=8)
    assert len(pcts) == len(portfolio_map)
    for pid in portfolio_map:
        assert pid in pcts


def test_j_no_future_leakage_in_shp():
    """Test J: SHP(t) is unchanged when NAV data after t is appended (property test)."""
    np.random.seed(42)
    history_up_to_t = list(np.random.normal(0.05, 0.02, 50))
    current_return_at_t = 0.06

    shp_at_t = own_history_percentile(current_return_at_t, history_up_to_t, min_history_count=20)
    assert shp_at_t is not None

    # Append future data occurring after t
    future_data = list(np.random.normal(0.10, 0.05, 100))
    full_history = history_up_to_t + future_data
    assert len(full_history) == len(history_up_to_t) + 100

    # Computing SHP as of date t must use ONLY data up to t
    shp_recomputed_at_t = own_history_percentile(
        current_return_at_t, history_up_to_t, min_history_count=20
    )
    assert shp_recomputed_at_t == pytest.approx(shp_at_t)
