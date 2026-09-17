"""Calendar and observation window calculations.

Rules:
- Q3: Window names are distinct (CAL_3M != CAL_90D != OBS_90).
- Q4: Boundary rule: start NAV is on or before target date, within MAX_STALENESS.
- Test H: CAL_1M ending 31 Mar resolves to 28/29 Feb (EOM clipping).
- Test I: Boundary rule picks on-or-before, never after; staleness > limit -> None.
- Test A, B, C: Exact N observations, start = end - (N - 1), M - N + 1 total.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class WindowKind(StrEnum):
    CAL_MONTH = "CAL_MONTH"
    CAL_DAY = "CAL_DAY"
    OBS = "OBS"


@dataclass(frozen=True)
class WindowDef:
    code: str
    kind: WindowKind
    size: int  # months, days, or observations


STANDARD_WINDOWS: dict[str, WindowDef] = {
    "CAL_1M": WindowDef("CAL_1M", WindowKind.CAL_MONTH, 1),
    "CAL_3M": WindowDef("CAL_3M", WindowKind.CAL_MONTH, 3),
    "CAL_6M": WindowDef("CAL_6M", WindowKind.CAL_MONTH, 6),
    "CAL_1Y": WindowDef("CAL_1Y", WindowKind.CAL_MONTH, 12),
    "CAL_3Y": WindowDef("CAL_3Y", WindowKind.CAL_MONTH, 36),
    "CAL_5Y": WindowDef("CAL_5Y", WindowKind.CAL_MONTH, 60),
    "OBS_21": WindowDef("OBS_21", WindowKind.OBS, 21),
    "OBS_63": WindowDef("OBS_63", WindowKind.OBS, 63),
    "OBS_90": WindowDef("OBS_90", WindowKind.OBS, 90),
    "OBS_126": WindowDef("OBS_126", WindowKind.OBS, 126),
    "OBS_252": WindowDef("OBS_252", WindowKind.OBS, 252),
}


def resolve_calendar_start_date(end_date: date, months: int) -> date:
    """Resolve start date for a calendar month window with End-Of-Month (EOM) clipping.

    Example: 2024-03-31 minus 1 month -> 2024-02-29 (leap year)
             2023-03-31 minus 1 month -> 2023-02-28
             2024-05-31 minus 3 months -> 2024-02-29
    """
    if months <= 0:
        raise ValueError(f"months must be positive, got {months}")

    total_months = end_date.year * 12 + (end_date.month - 1) - months
    target_year = total_months // 12
    target_month = (total_months % 12) + 1

    # End of month clipping
    max_days_in_target_month = calendar.monthrange(target_year, target_month)[1]
    target_day = min(end_date.day, max_days_in_target_month)

    return date(target_year, target_month, target_day)


def find_boundary_nav_date(
    target_date: date,
    available_dates: list[date] | tuple[date, ...],
    max_staleness_days: int = 5,
) -> date | None:
    """Find the latest available date on or before target_date within max_staleness_days.

    Never picks a date after target_date (prevents lookahead).
    Returns None if no date is found or staleness exceeds max_staleness_days.
    Assumes available_dates is sorted ascending.
    """
    if not available_dates:
        return None

    import bisect

    idx = bisect.bisect_right(available_dates, target_date) - 1
    if idx < 0:
        return None

    matched_date = available_dates[idx]
    if (target_date - matched_date).days > max_staleness_days:
        return None

    return matched_date


def resolve_obs_indices(end_idx: int, n_obs: int, total_obs: int) -> tuple[int, int] | None:
    """Resolve 0-indexed [start_idx, end_idx] for an N-observation window.

    Satisfies Test B: start_idx == end_idx - (n_obs - 1).
    Satisfies Test A: exactly n_obs observations (inclusive).
    Returns None if there are fewer than n_obs observations available up to end_idx.
    """
    if n_obs <= 0:
        raise ValueError(f"n_obs must be positive, got {n_obs}")
    if end_idx >= total_obs:
        raise ValueError(f"end_idx {end_idx} >= total_obs {total_obs}")

    start_idx = end_idx - (n_obs - 1)
    if start_idx < 0:
        return None

    return (start_idx, end_idx)


def compute_eligible_obs_window_count(m_obs: int, n_obs: int) -> int:
    """Calculate eligible window count M - N + 1 (Test C)."""
    if m_obs < n_obs:
        return 0
    return m_obs - n_obs + 1
