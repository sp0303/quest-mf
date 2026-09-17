"""Backtest statistics: Spearman Rank IC and Quintile analysis."""

from __future__ import annotations

import numpy as np
from scipy.stats import spearmanr


def compute_rank_ic(
    scores: list[float] | np.ndarray,
    forward_returns: list[float] | np.ndarray,
) -> float | None:
    """Compute Spearman Rank Information Coefficient (IC) between scores and forward returns."""
    s = np.asarray(scores, dtype=np.float64)
    r = np.asarray(forward_returns, dtype=np.float64)

    mask = ~np.isnan(s) & ~np.isnan(r)
    valid_s = s[mask]
    valid_r = r[mask]

    if len(valid_s) < 5:
        return None

    corr, _ = spearmanr(valid_s, valid_r)
    if np.isnan(corr):
        return 0.0
    return float(corr)


def compute_quintile_returns(
    scores: list[float] | np.ndarray,
    forward_returns: list[float] | np.ndarray,
    n_buckets: int = 5,
) -> dict[int, float]:
    """Calculate mean forward return for each score bucket (quintiles 1..5).

    Quintile 1 is highest score, Quintile 5 is lowest score.
    """
    s = np.asarray(scores, dtype=np.float64)
    r = np.asarray(forward_returns, dtype=np.float64)

    mask = ~np.isnan(s) & ~np.isnan(r)
    valid_s = s[mask]
    valid_r = r[mask]

    if len(valid_s) < n_buckets:
        return {b: 0.0 for b in range(1, n_buckets + 1)}

    # Rank descending: rank 1 is highest score
    ranks = np.argsort(np.argsort(-valid_s))
    bucket_size = len(valid_s) / n_buckets

    bucket_means: dict[int, float] = {}
    for b in range(1, n_buckets + 1):
        start_idx = int((b - 1) * bucket_size)
        end_idx = int(b * bucket_size) if b < n_buckets else len(valid_s)
        b_mask = (ranks >= start_idx) & (ranks < end_idx)
        if np.any(b_mask):
            bucket_means[b] = float(np.mean(valid_r[b_mask]))
        else:
            bucket_means[b] = 0.0

    return bucket_means
