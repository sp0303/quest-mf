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
) -> float:
    """Calculate sample annualized standard deviation of returns."""
    arr = np.asarray(returns, dtype=np.float64)
    if len(arr) < 2:
        return 0.0
    return float(np.std(arr, ddof=1) * math.sqrt(periods_per_year))


def annualized_downside_deviation(
    returns: list[float] | np.ndarray,
    mar: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """Calculate annualized downside deviation below Minimum Acceptable Return (MAR)."""
    arr = np.asarray(returns, dtype=np.float64)
    if len(arr) < 2:
        return 0.0
    under = np.minimum(arr - mar, 0.0)
    semivar = np.mean(under**2)
    return float(math.sqrt(semivar) * math.sqrt(periods_per_year))


def sharpe_ratio(
    returns: list[float] | np.ndarray,
    annual_rf: float = 0.06,
    periods_per_year: int = 252,
) -> float:
    """Annualized Sharpe ratio."""
    arr = np.asarray(returns, dtype=np.float64)
    if len(arr) < 2:
        return 0.0
    vol = annualized_volatility(arr, periods_per_year)
    if vol == 0.0:
        return 0.0
    ann_ret = float(np.mean(arr) * periods_per_year)
    return (ann_ret - annual_rf) / vol


def sortino_ratio(
    returns: list[float] | np.ndarray,
    annual_rf: float = 0.06,
    periods_per_year: int = 252,
) -> float:
    """Annualized Sortino ratio using downside deviation."""
    arr = np.asarray(returns, dtype=np.float64)
    if len(arr) < 2:
        return 0.0
    rf_daily = annual_rf / periods_per_year
    dd = annualized_downside_deviation(arr, mar=rf_daily, periods_per_year=periods_per_year)
    if dd == 0.0:
        return 0.0
    ann_ret = float(np.mean(arr) * periods_per_year)
    return (ann_ret - annual_rf) / dd


def tracking_error(
    fund_returns: list[float] | np.ndarray,
    bench_returns: list[float] | np.ndarray,
    periods_per_year: int = 252,
) -> float:
    """Annualized tracking error std(r_fund - r_bench) * sqrt(252)."""
    f_arr = np.asarray(fund_returns, dtype=np.float64)
    b_arr = np.asarray(bench_returns, dtype=np.float64)
    if len(f_arr) != len(b_arr):
        raise ValueError("Fund and benchmark series must be of identical length")
    if len(f_arr) < 2:
        return 0.0

    active_diff = f_arr - b_arr
    return float(np.std(active_diff, ddof=1) * math.sqrt(periods_per_year))


def information_ratio(
    fund_returns: list[float] | np.ndarray,
    bench_returns: list[float] | np.ndarray,
    periods_per_year: int = 252,
) -> float:
    """Annualized Information Ratio (mean active return / tracking error)."""
    f_arr = np.asarray(fund_returns, dtype=np.float64)
    b_arr = np.asarray(bench_returns, dtype=np.float64)
    if len(f_arr) != len(b_arr):
        raise ValueError("Fund and benchmark series must be of identical length")
    te = tracking_error(f_arr, b_arr, periods_per_year)
    if te == 0.0:
        return 0.0
    mean_active = float(np.mean(f_arr - b_arr) * periods_per_year)
    return mean_active / te


def beta_and_alpha(
    fund_returns: list[float] | np.ndarray,
    bench_returns: list[float] | np.ndarray,
    periods_per_year: int = 252,
    annual_rf: float = 0.06,
) -> tuple[float, float]:
    """Calculate CAPM Beta and Annualized Alpha."""
    f_arr = np.asarray(fund_returns, dtype=np.float64)
    b_arr = np.asarray(bench_returns, dtype=np.float64)
    if len(f_arr) != len(b_arr):
        raise ValueError("Series lengths must match")
    if len(f_arr) < 2:
        return 1.0, 0.0

    cov_matrix = np.cov(f_arr, b_arr)
    var_bench = float(cov_matrix[1, 1])
    if var_bench == 0.0:
        return 1.0, 0.0

    beta = float(cov_matrix[0, 1] / var_bench)
    ann_f = float(np.mean(f_arr) * periods_per_year)
    ann_b = float(np.mean(b_arr) * periods_per_year)
    alpha = (ann_f - annual_rf) - beta * (ann_b - annual_rf)

    return beta, alpha


def up_down_capture(
    fund_returns: list[float] | np.ndarray,
    bench_returns: list[float] | np.ndarray,
) -> tuple[float, float]:
    """Calculate Up-Market Capture and Down-Market Capture ratios."""
    f_arr = np.asarray(fund_returns, dtype=np.float64)
    b_arr = np.asarray(bench_returns, dtype=np.float64)
    if len(f_arr) != len(b_arr):
        raise ValueError("Series lengths must match")

    up_mask = b_arr > 0
    down_mask = b_arr < 0

    up_cap = (
        float(np.mean(f_arr[up_mask]) / np.mean(b_arr[up_mask]))
        if np.any(up_mask) and np.mean(b_arr[up_mask]) != 0
        else 1.0
    )
    down_cap = (
        float(np.mean(f_arr[down_mask]) / np.mean(b_arr[down_mask]))
        if np.any(down_mask) and np.mean(b_arr[down_mask]) != 0
        else 1.0
    )

    return up_cap, down_cap
