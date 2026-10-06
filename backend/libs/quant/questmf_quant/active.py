"""Benchmark-relative rolling statistics for the persistence component (spec §16.2).

- Q1: only windows with end_date <= the last date supplied are used.
- Q4: start NAV is the boundary date on or before the calendar target, within staleness.
- Q5: fund and benchmark use identical start and end dates (dates must be aligned).
- Q12: fewer than `min_windows` windows -> None, never zero.
"""

from __future__ import annotations

import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from questmf_quant.calendar.windows import find_boundary_nav_date, resolve_calendar_start_date


@dataclass(frozen=True)
class ActiveStats:
    beat_pct: float | None  # % of windows where fund return > benchmark return
    median_active: float | None  # median (fund - benchmark) window return
    windows: int


def rolling_active_returns(
    aligned_dates: Sequence[date],
    fund: Mapping[date, float],
    bench: Mapping[date, float],
    months: int,
    step_obs: int = 5,
    max_staleness_days: int = 7,
) -> list[float]:
    """Active returns of every `months`-calendar window ending on aligned dates.

    `aligned_dates` must be sorted ascending and present in both `fund` and `bench`.
    Windows step back from the latest date every `step_obs` observations.
    """
    out: list[float] = []
    for end_idx in range(len(aligned_dates) - 1, -1, -step_obs):
        end_d = aligned_dates[end_idx]
        # The calendar target is strictly before end_d, so searching the full list
        # can never return a date after end_d (no look-ahead) and avoids O(n^2) slicing.
        start_d = find_boundary_nav_date(
            resolve_calendar_start_date(end_d, months),
            aligned_dates,
            max_staleness_days=max_staleness_days,
        )
        if start_d is None or start_d == end_d:
            continue
        f_ret = fund[end_d] / fund[start_d] - 1.0
        b_ret = bench[end_d] / bench[start_d] - 1.0
        out.append(f_ret - b_ret)
    return out


def active_stats(actives: Sequence[float], min_windows: int = 8) -> ActiveStats:
    if len(actives) < min_windows:
        return ActiveStats(beat_pct=None, median_active=None, windows=len(actives))
    beat = 100.0 * sum(1 for a in actives if a > 0.0) / len(actives)
    return ActiveStats(
        beat_pct=beat, median_active=float(statistics.median(actives)), windows=len(actives)
    )
