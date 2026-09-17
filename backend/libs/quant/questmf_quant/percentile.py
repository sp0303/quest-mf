"""Percentile engines: Peer Percentile (mid-rank) and Self-History Percentile (SHP).

Rules:
- Q1: No look-ahead. SHP(t) excludes future data (uses only past observations).
- Q8: One row per portfolio_id in peer percentile. Minimum 8 peers, otherwise None.
- Test J: SHP(t) is unchanged when NAV data after t is appended (property test).
- Test Q: Percentile with ties uses mid-rank; < 8 peers -> None.
"""

from __future__ import annotations

import numpy as np


def mid_rank_percentile(value: float, reference_set: list[float] | np.ndarray) -> float:
    """Compute percentile of value within reference_set using mid-rank for ties.

    Formula: Percentile = 100 * (count(v < value) + 0.5 * count(v == value)) / N
    Returns a score between 0.0 and 100.0.
    """
    arr = np.asarray(reference_set, dtype=np.float64)
    n = len(arr)
    if n == 0:
        raise ValueError("Reference set cannot be empty")

    strictly_less = np.sum(arr < value)
    equal = np.sum(arr == value)

    rank = strictly_less + 0.5 * equal
    return float(100.0 * rank / n)


def peer_percentiles(
    portfolio_metric_map: dict[int, float],
    min_peers: int = 8,
) -> dict[int, float | None]:
    """Compute peer percentiles across unique portfolio IDs in a category.

    Strictly adheres to:
    - Rule Q8: Exactly one value per portfolio_id.
    - Test Q: If peer count < min_peers (default 8), all values are None.
    - Ties use mid-rank.
    """
    valid_items = {
        pid: v for pid, v in portfolio_metric_map.items() if v is not None and not np.isnan(v)
    }
    total_peers = len(valid_items)

    if total_peers < min_peers:
        # Fewer than min_peers peers -> null (Rule Q8)
        return {pid: None for pid in portfolio_metric_map}

    ref_values = np.fromiter(valid_items.values(), dtype=np.float64)

    results: dict[int, float | None] = {}
    for pid in portfolio_metric_map:
        if pid not in valid_items:
            results[pid] = None
        else:
            val = valid_items[pid]
            results[pid] = mid_rank_percentile(val, ref_values)

    return results


def own_history_percentile(
    current_value: float,
    past_values_up_to_t: list[float] | np.ndarray,
    min_history_count: int = 20,
) -> float | None:
    """Calculate Self-History Percentile (SHP) as of date t.

    Per Rule Q1 and Test J:
    - Must use strictly past rolling observations up to date t.
    - Appending observations from dates > t has zero impact on SHP(t).
    - If historical sample < min_history_count, returns None.
    """
    arr = np.asarray(past_values_up_to_t, dtype=np.float64)
    valid_arr = arr[~np.isnan(arr)]

    if len(valid_arr) < min_history_count:
        return None

    return mid_rank_percentile(current_value, valid_arr)
