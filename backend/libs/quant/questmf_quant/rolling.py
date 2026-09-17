"""Vectorized rolling window returns and metrics engine.

Rules:
- Q1: No look-ahead. Features as of date t use only data <= t.
- Q4: Boundary rule: start NAV is on or before target date within MAX_STALENESS.
- Q5: Fund and benchmark returns use identical start and end dates.
- Q9: No forward-filling NAV for return calculations. Gaps are flagged.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .calendar.windows import (
    WindowDef,
    find_boundary_nav_date,
    resolve_calendar_start_date,
)
from .drawdown import max_drawdown
from .returns import active_return, log_return, simple_return


@dataclass(frozen=True)
class RollingMetricPoint:
    end_date: date
    start_date: date
    n_obs: int
    ret: float
    log_ret: float
    bench_ret: float | None
    active_ret: float | None
    max_dd: float
    has_gap: bool


def compute_rolling_windows(
    nav_dates: list[date],
    nav_values: list[float],
    window_def: WindowDef,
    bench_map: dict[date, float] | None = None,
    max_staleness_days: int = 5,
    max_gap_days: int = 7,
) -> list[RollingMetricPoint]:
    """Compute rolling window metrics for a mutual fund series."""
    if len(nav_dates) != len(nav_values):
        raise ValueError("Dates and values must have equal length")
    if not nav_dates:
        return []

    date_to_idx = {d: i for i, d in enumerate(nav_dates)}
    results: list[RollingMetricPoint] = []

    for end_idx, end_d in enumerate(nav_dates):
        # Resolve target start date
        if window_def.kind.value == "CAL_MONTH":
            target_start = resolve_calendar_start_date(end_d, window_def.size)
            start_d = find_boundary_nav_date(
                target_start, nav_dates[: end_idx + 1], max_staleness_days
            )
            if start_d is None:
                continue
            start_idx = date_to_idx[start_d]
        elif window_def.kind.value == "OBS":
            start_idx = end_idx - (window_def.size - 1)
            if start_idx < 0:
                continue
            start_d = nav_dates[start_idx]
        else:
            continue

        n_obs = end_idx - start_idx + 1
        if n_obs < 2:
            continue

        slice_navs = nav_values[start_idx : end_idx + 1]
        start_nav = slice_navs[0]
        end_nav = slice_navs[-1]

        r = simple_return(start_nav, end_nav)
        lr = log_return(start_nav, end_nav)
        mdd, _, _ = max_drawdown(slice_navs)

        # Benchmark calculation
        b_ret = None
        act_ret = None
        if bench_map and start_d in bench_map and end_d in bench_map:
            b_start = bench_map[start_d]
            b_end = bench_map[end_d]
            b_ret = simple_return(b_start, b_end)
            act_ret = active_return(r, b_ret)

        # Check gap between consecutive dates
        has_gap = False
        for i in range(start_idx, end_idx):
            if (nav_dates[i + 1] - nav_dates[i]).days > max_gap_days:
                has_gap = True
                break

        results.append(
            RollingMetricPoint(
                end_date=end_d,
                start_date=start_d,
                n_obs=n_obs,
                ret=r,
                log_ret=lr,
                bench_ret=b_ret,
                active_ret=act_ret,
                max_dd=mdd,
                has_gap=has_gap,
            )
        )

    return results
