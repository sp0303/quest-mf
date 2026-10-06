"""Per-fund feature computation for the batch compute worker (spec v2 §9-§16).

Pure orchestration over questmf_quant: no DB or network access here.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from questmf_quant.active import active_stats, rolling_active_returns
from questmf_quant.calendar.windows import find_boundary_nav_date, resolve_calendar_start_date
from questmf_quant.drawdown import max_drawdown
from questmf_quant.percentile import own_history_percentile
from questmf_quant.returns import cagr, simple_return
from questmf_quant.risk import (
    annualized_downside_deviation,
    annualized_volatility,
    beta_and_alpha,
    information_ratio,
    sharpe_ratio,
    sortino_ratio,
    tracking_error,
)

MAX_WINDOW_STALENESS_DAYS = 7
OBS_1Y = 252
OBS_3Y = 756
ANNUAL_RF = 0.065


def _window_start(end_d: date, months: int, dates: list[date]) -> date | None:
    return find_boundary_nav_date(
        resolve_calendar_start_date(end_d, months), dates, MAX_WINDOW_STALENESS_DAYS
    )


def calendar_return(nav: dict[date, float], dates: list[date], months: int) -> float | None:
    """CAL_<n>M simple return (< 12M) or CAGR (>= 12M); None if no boundary NAV (Q4/Q12)."""
    end_d = dates[-1]
    start_d = _window_start(end_d, months, dates)
    if start_d is None:
        return None
    if months >= 12:
        span = float((end_d - start_d).days)
        return cagr(nav[start_d], nav[end_d], days=span) if span >= 365.0 else None
    return simple_return(nav[start_d], nav[end_d])


def _shp_3m(nav: dict[date, float], dates: list[date], r_3m: float | None) -> float | None:
    """SHP(t): percentile of current 3M return among past 3M windows, excluding t (Q1)."""
    if r_3m is None or len(dates) <= 65:
        return None
    history: list[float] = []
    for step in range(10, min(len(dates) - 1, 500), 10):
        end_d = dates[len(dates) - 1 - step]
        start_d = _window_start(end_d, 3, dates)
        if start_d is not None:
            history.append(simple_return(nav[start_d], nav[end_d]))
    return own_history_percentile(r_3m, history) if len(history) >= 8 else None


def _three_year_risk(navs: list[float], dates: list[date], has_3y: bool) -> dict[str, Any]:
    if not has_3y:
        return {"mdd_3y": None, "downside_dev_3y": None}
    start_d = _window_start(dates[-1], 36, dates)
    i0 = dates.index(start_d) if start_d is not None else 0
    window = navs[i0:]
    rets = [window[i] / window[i - 1] - 1.0 for i in range(1, len(window))]
    mdd, _, _ = max_drawdown(window)
    return {"mdd_3y": mdd, "downside_dev_3y": annualized_downside_deviation(rets)}


def _benchmark_features(
    nav: dict[date, float], dates: list[date], bench: dict[date, float]
) -> dict[str, Any]:
    aligned = [d for d in dates if d in bench]
    out: dict[str, Any] = dict.fromkeys(
        (
            "beta_1y",
            "ir_3y",
            "alpha_3m",
            "tracking_error",
            "beat_pct_3m",
            "beat_pct_1y",
            "median_active_3m",
        ),
    )
    if len(aligned) < 30:
        return out
    f = [nav[aligned[i]] / nav[aligned[i - 1]] - 1.0 for i in range(1, len(aligned))]
    b = [bench[aligned[i]] / bench[aligned[i - 1]] - 1.0 for i in range(1, len(aligned))]
    if len(f) >= OBS_1Y:
        out["beta_1y"], _ = beta_and_alpha(f[-OBS_1Y:], b[-OBS_1Y:], annual_rf=ANNUAL_RF)
    if len(f) >= OBS_3Y:  # Q12: no "3Y" IR from a shorter history
        out["ir_3y"] = information_ratio(f[-OBS_3Y:], b[-OBS_3Y:])
        out["tracking_error"] = tracking_error(f[-OBS_3Y:], b[-OBS_3Y:])
    end_d = aligned[-1]
    if end_d == dates[-1]:  # Q5: identical end date for fund and benchmark
        start_d = _window_start(end_d, 3, aligned)
        if start_d is not None:
            out["alpha_3m"] = (nav[end_d] / nav[start_d]) - (bench[end_d] / bench[start_d])
    a3 = active_stats(rolling_active_returns(aligned, nav, bench, 3))
    a12 = active_stats(rolling_active_returns(aligned, nav, bench, 12))
    out.update(beat_pct_3m=a3.beat_pct, median_active_3m=a3.median_active, beat_pct_1y=a12.beat_pct)
    return out


def compute_fund_features(
    nav: dict[date, float], bench: dict[date, float], ter: float | None
) -> dict[str, Any]:
    """All screener columns and §16 features for one canonical series."""
    dates = sorted(nav)
    navs = [nav[d] for d in dates]
    daily = [navs[i] / navs[i - 1] - 1.0 for i in range(1, len(navs))]
    r = {m: calendar_return(nav, dates, m) for m in (1, 3, 6, 12, 36, 60)}
    feats: dict[str, Any] = {
        "ret_1m": r[1],
        "ret_3m": r[3],
        "ret_6m": r[6],
        "ret_1y": r[12],
        "cagr_3y": r[36],
        "cagr_5y": r[60],
        "vol": annualized_volatility(daily),
        "sharpe": sharpe_ratio(daily, annual_rf=ANNUAL_RF),
        "sortino": sortino_ratio(daily, annual_rf=ANNUAL_RF),
        "shp_3m": _shp_3m(nav, dates, r[3]),
        "ter": ter,
        "exit_load_days": None,  # no genuine load_rules source yet (spec §18): stays null
        "obs_count": len(daily),
        "end_date": dates[-1],
    }
    feats.update(_three_year_risk(navs, dates, has_3y=r[36] is not None))
    feats["mdd_mag_3y"] = -feats["mdd_3y"] if feats["mdd_3y"] is not None else None
    feats.update(_benchmark_features(nav, dates, bench))
    return feats
