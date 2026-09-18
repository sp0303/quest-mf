"""Risk and benchmark-relative performance metrics.

Formulas:
- Annualized Volatility: std(returns) * sqrt(252)
- Downside Deviation: sqrt(mean(min(r - mar, 0)^2)) * sqrt(252)
- Tracking Error: std(r_fund - r_bench) * sqrt(252)
- Information Ratio: mean(r_fund - r_bench) / TE * sqrt(252)
- Beta: Cov(r_fund, r_bench) / Var(r_bench)
- Up/Down capture ratios
"""

from __future__ import annotations

import math

import numpy as np


def annualized_volatility(
    returns: list[float] | np.ndarray,
    periods_per_year: int = 252,
    min_obs: int = 2,
) -> float | None:
    """Calculate sample annualized standard deviation of returns. Returns None if len < min_obs (Q12)."""
    arr = np.asarray(returns, dtype=np.float64)
    if len(arr) < min_obs:
        return None
    return float(np.std(arr, ddof=1) * math.sqrt(periods_per_year))


def annualized_downside_deviation(
    returns: list[float] | np.ndarray,
    mar: float = 0.0,
    periods_per_year: int = 252,
    min_obs: int = 2,
) -> float | None:
    """Calculate annualized downside deviation below Minimum Acceptable Return (MAR). Returns None if len < min_obs (Q12)."""
    arr = np.asarray(returns, dtype=np.float64)
    if len(arr) < min_obs:
        return None
    under = np.minimum(arr - mar, 0.0)
    semivar = np.mean(under**2)
    return float(math.sqrt(semivar) * math.sqrt(periods_per_year))


def sharpe_ratio(
    returns: list[float] | np.ndarray,
    annual_rf: float = 0.06,
    periods_per_year: int = 252,
    min_obs: int = 2,
) -> float | None:
    """Annualized Sharpe ratio. Returns None if len < min_obs (Q12)."""
    arr = np.asarray(returns, dtype=np.float64)
    if len(arr) < min_obs:
        return None
    vol = annualized_volatility(arr, periods_per_year, min_obs=min_obs)
    if vol is None or vol == 0.0:
        return None
    ann_ret = float(np.mean(arr) * periods_per_year)
    return (ann_ret - annual_rf) / vol


def sortino_ratio(
    returns: list[float] | np.ndarray,
    annual_rf: float = 0.06,
    periods_per_year: int = 252,
    min_obs: int = 2,
) -> float | None:
    """Annualized Sortino ratio using downside deviation. Returns None if len < min_obs (Q12)."""
    arr = np.asarray(returns, dtype=np.float64)
    if len(arr) < min_obs:
        return None
    rf_daily = annual_rf / periods_per_year
    dd = annualized_downside_deviation(
        arr, mar=rf_daily, periods_per_year=periods_per_year, min_obs=min_obs
    )
    if dd is None or dd == 0.0:
        return None
    ann_ret = float(np.mean(arr) * periods_per_year)
    return (ann_ret - annual_rf) / dd


def tracking_error(
    fund_returns: list[float] | np.ndarray,
    bench_returns: list[float] | np.ndarray,
    periods_per_year: int = 252,
    min_obs: int = 2,
) -> float | None:
    """Annualized tracking error std(r_fund - r_bench) * sqrt(252). Returns None if len < min_obs (Q12)."""
    f_arr = np.asarray(fund_returns, dtype=np.float64)
    b_arr = np.asarray(bench_returns, dtype=np.float64)
    if len(f_arr) != len(b_arr):
        raise ValueError("Fund and benchmark series must be of identical length")
    if len(f_arr) < min_obs:
        return None

    active_diff = f_arr - b_arr
    return float(np.std(active_diff, ddof=1) * math.sqrt(periods_per_year))


def information_ratio(
    fund_returns: list[float] | np.ndarray,
    bench_returns: list[float] | np.ndarray,
    periods_per_year: int = 252,
    min_obs: int = 2,
) -> float | None:
    """Annualized Information Ratio (mean active return / tracking error). Returns None if len < min_obs (Q12)."""
    f_arr = np.asarray(fund_returns, dtype=np.float64)
    b_arr = np.asarray(bench_returns, dtype=np.float64)
    if len(f_arr) != len(b_arr):
        raise ValueError("Fund and benchmark series must be of identical length")
    if len(f_arr) < min_obs:
        return None
    te = tracking_error(f_arr, b_arr, periods_per_year, min_obs=min_obs)
    if te is None or te == 0.0:
        return None
    mean_active = float(np.mean(f_arr - b_arr) * periods_per_year)
    return mean_active / te


def beta_and_alpha(
    fund_returns: list[float] | np.ndarray,
    bench_returns: list[float] | np.ndarray,
    periods_per_year: int = 252,
    annual_rf: float = 0.06,
    min_obs: int = 2,
) -> tuple[float | None, float | None]:
    """Calculate CAPM Beta and Annualized Alpha. Returns (None, None) if len < min_obs (Q12)."""
    f_arr = np.asarray(fund_returns, dtype=np.float64)
    b_arr = np.asarray(bench_returns, dtype=np.float64)
    if len(f_arr) != len(b_arr):
        raise ValueError("Series lengths must match")
    if len(f_arr) < min_obs:
        return None, None

    cov_matrix = np.cov(f_arr, b_arr)
    var_bench = float(cov_matrix[1, 1])
    if var_bench == 0.0:
        return None, None

    beta = float(cov_matrix[0, 1] / var_bench)
    ann_f = float(np.mean(f_arr) * periods_per_year)
    ann_b = float(np.mean(b_arr) * periods_per_year)
    alpha = (ann_f - annual_rf) - beta * (ann_b - annual_rf)

    return beta, alpha


def up_down_capture(
    fund_returns: list[float] | np.ndarray,
    bench_returns: list[float] | np.ndarray,
    min_obs: int = 2,
) -> tuple[float | None, float | None]:
    """Calculate Up-Market Capture and Down-Market Capture ratios."""
    f_arr = np.asarray(fund_returns, dtype=np.float64)
    b_arr = np.asarray(bench_returns, dtype=np.float64)
    if len(f_arr) != len(b_arr):
        raise ValueError("Series lengths must match")
    if len(f_arr) < min_obs:
        return None, None

    up_mask = b_arr > 0
    down_mask = b_arr < 0

    up_cap = (
        float(np.mean(f_arr[up_mask]) / np.mean(b_arr[up_mask]))
        if np.any(up_mask) and np.mean(b_arr[up_mask]) != 0
        else None
    )
    down_cap = (
        float(np.mean(f_arr[down_mask]) / np.mean(b_arr[down_mask]))
        if np.any(down_mask) and np.mean(b_arr[down_mask]) != 0
        else None
    )

    return up_cap, down_cap
