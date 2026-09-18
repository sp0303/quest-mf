"""Technical indicators: RSI, SMA, Momentum Acceleration, RS Slope."""

from __future__ import annotations

import numpy as np


def sma(prices: list[float] | np.ndarray, window: int) -> np.ndarray:
    """Calculate Simple Moving Average."""
    arr = np.asarray(prices, dtype=np.float64)
    if len(arr) < window or window <= 0:
        return np.full_like(arr, np.nan)
    ret = np.cumsum(arr, dtype=np.float64)
    ret[window:] = ret[window:] - ret[:-window]
    result = np.empty_like(arr)
    result[: window - 1] = np.nan
    result[window - 1 :] = ret[window - 1 :] / window
    return result


def rsi(prices: list[float] | np.ndarray, period: int = 14) -> np.ndarray:
    """Calculate Relative Strength Index (Wilder's RSI)."""
    arr = np.asarray(prices, dtype=np.float64)
    n = len(arr)
    out = np.full(n, np.nan, dtype=np.float64)
    if n <= period or period <= 0:
        return out

    deltas = np.diff(arr)
    gains = np.maximum(deltas, 0.0)
    losses = np.abs(np.minimum(deltas, 0.0))

    # Initial average
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    if avg_loss == 0.0:
        out[period] = 100.0 if avg_gain > 0 else 50.0
    else:
        rs = avg_gain / avg_loss
        out[period] = 100.0 - (100.0 / (1.0 + rs))

    # Smoothed Wilder calculation
    for i in range(period, len(deltas)):
        gain = gains[i]
        loss = losses[i]
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

        if avg_loss == 0.0:
            out[i + 1] = 100.0 if avg_gain > 0 else 50.0
        else:
            rs = avg_gain / avg_loss
            out[i + 1] = 100.0 - (100.0 / (1.0 + rs))

    return out


def momentum_acceleration(
    prices: list[float] | np.ndarray,
    short_window: int = 21,
    long_window: int = 63,
) -> float | None:
    """Calculate Momentum Acceleration (rate of change of ROC). Returns None if insufficient history (Q12)."""
    arr = np.asarray(prices, dtype=np.float64)
    if len(arr) < long_window + short_window:
        return None

    # Recent short-term return
    ret_recent = (arr[-1] / arr[-short_window]) - 1.0
    # Prior short-term return from long_window ago
    ret_prior = (arr[-long_window] / arr[-long_window - short_window]) - 1.0

    return float(ret_recent - ret_prior)


def relative_strength_slope(
    fund_prices: list[float] | np.ndarray,
    bench_prices: list[float] | np.ndarray,
    window: int = 63,
) -> float | None:
    """Linear regression slope of the Relative Strength ratio (Fund / Benchmark). Returns None if insufficient history (Q12)."""
    f_arr = np.asarray(fund_prices, dtype=np.float64)
    b_arr = np.asarray(bench_prices, dtype=np.float64)
    if len(f_arr) < window or len(b_arr) < window:
        return None

    ratio = f_arr[-window:] / b_arr[-window:]
    x = np.arange(window, dtype=np.float64)
    # Slope of linear regression
    slope, _ = np.polyfit(x, ratio, 1)
    return float(slope * window)  # Scaled by window for comparability
