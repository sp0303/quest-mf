"""Drawdown and underwater series analytics."""

from __future__ import annotations

import numpy as np


def underwater_series(nav_series: list[float] | np.ndarray) -> np.ndarray:
    """Calculate the underwater series (drawdown percentage at each step).

    underwater[t] = (nav[t] / peak[t]) - 1.0 (always <= 0.0)
    """
    arr = np.asarray(nav_series, dtype=np.float64)
    if len(arr) == 0:
        return np.array([], dtype=np.float64)
    if np.any(arr <= 0):
        raise ValueError("NAV values must be strictly positive")

    cummax = np.maximum.accumulate(arr)
    return (arr / cummax) - 1.0


def max_drawdown(nav_series: list[float] | np.ndarray) -> tuple[float, int, int]:
    """Compute maximum drawdown and indices of peak and trough.

    Returns: (max_dd, peak_idx, trough_idx) where max_dd is a negative float or 0.0.
    """
    arr = np.asarray(nav_series, dtype=np.float64)
    if len(arr) < 2:
        return 0.0, 0, 0
    if np.any(arr <= 0):
        raise ValueError("NAV values must be strictly positive")

    cummax = np.maximum.accumulate(arr)
    drawdowns = (arr / cummax) - 1.0

    trough_idx = int(np.argmin(drawdowns))
    min_dd = float(drawdowns[trough_idx])

    if min_dd >= 0.0:
        return 0.0, 0, 0

    # Peak index is the index of max NAV occurring up to trough_idx
    peak_idx = int(np.argmax(arr[: trough_idx + 1]))
    return min_dd, peak_idx, trough_idx


def max_drawdown_recovery_days(
    nav_series: list[float] | np.ndarray,
    dates: list,
) -> int | None:
    """Compute number of days taken to recover from the maximum drawdown.

    Returns None if the drawdown has not recovered by the end of the series.
    """
    min_dd, peak_idx, trough_idx = max_drawdown(nav_series)
    if min_dd >= 0.0:
        return 0

    peak_nav = nav_series[peak_idx]
    # Check for recovery after trough_idx
    for idx in range(trough_idx + 1, len(nav_series)):
        if nav_series[idx] >= peak_nav:
            return (dates[idx] - dates[trough_idx]).days

    return None
