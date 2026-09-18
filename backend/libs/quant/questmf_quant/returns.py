"""Return calculation functions.

Formulas:
- Simple return: R = NAV_t / NAV_s - 1
- Log return: r = ln(NAV_t / NAV_s)
- CAGR: (1 + R) ^ (365.25 / days) - 1
- Active return: R_fund - R_bench (strictly same start and end dates, Q5)
- Excess return: R_fund - R_rf
- XIRR: internal rate of return for periodic/SIP cashflows
"""

from __future__ import annotations

import math
from datetime import date


def validate_canonical_scheme(plan: str, option: str, is_canonical: bool = True) -> None:
    """Validate that canonical series adheres to Rule Q7 and Test L.

    - Q7: Canonical series = Direct-Growth. Never compute returns from IDCW NAV.
    - Test L: IDCW series cannot become canonical (raises ValueError).
    """
    if is_canonical:
        if option.strip().upper() == "IDCW":
            raise ValueError("IDCW series cannot become canonical (Rule Q7, Test L)")
        if option.strip().upper() != "GROWTH":
            raise ValueError(f"Canonical series must have GROWTH option, got {option}")


def simple_return(nav_start: float, nav_end: float) -> float:
    """Calculate simple percentage return."""
    if nav_start <= 0:
        raise ValueError(f"nav_start must be positive, got {nav_start}")
    if nav_end < 0:
        raise ValueError(f"nav_end cannot be negative, got {nav_end}")
    return (nav_end / nav_start) - 1.0


def log_return(nav_start: float, nav_end: float) -> float:
    """Calculate continuously compounded log return."""
    if nav_start <= 0 or nav_end <= 0:
        raise ValueError("NAV values must be strictly positive for log return")
    return math.log(nav_end / nav_start)


def cagr(nav_start: float, nav_end: float, days: float) -> float:
    """Calculate Compound Annual Growth Rate annualized over 365.25 days."""
    if days <= 0:
        raise ValueError(f"days must be positive, got {days}")
    if nav_start <= 0 or nav_end <= 0:
        raise ValueError("NAV values must be strictly positive for CAGR")

    r = nav_end / nav_start
    if r < 0:
        raise ValueError("Total return cannot be negative for CAGR base")
    return (r ** (365.25 / days)) - 1.0


def active_return(fund_return: float, bench_return: float) -> float:
    """Calculate active return relative to benchmark (R_fund - R_bench).

    Per Rule Q5: fund and benchmark returns must use identical start and end dates.
    """
    return fund_return - bench_return


def excess_return(fund_return: float, risk_free_return: float) -> float:
    """Calculate excess return over the risk-free rate."""
    return fund_return - risk_free_return


def xirr(cashflows: list[tuple[date, float]], tol: float = 1e-7, max_iter: int = 100) -> float:
    """Compute XIRR (Internal Rate of Return) for irregular or periodic cash flows.

    Cash flows are given as (date, amount).
    Negative amounts are investments/outflows; positive amounts are redemptions/inflows.
    """
    if len(cashflows) < 2:
        raise ValueError("XIRR requires at least 2 cash flow entries")

    dates = [cf[0] for cf in cashflows]
    amounts = [cf[1] for cf in cashflows]

    # Check that there is at least one positive and one negative cash flow
    has_positive = any(a > 0 for a in amounts)
    has_negative = any(a < 0 for a in amounts)
    if not (has_positive and has_negative):
        raise ValueError("XIRR requires at least one positive and one negative cash flow")

    d0 = dates[0]
    year_fractions = [(d - d0).days / 365.25 for d in dates]

    # Newton-Raphson search
    rate = 0.1  # Initial guess 10%
    for _ in range(max_iter):
        f_val = 0.0
        df_val = 0.0
        for frac, amount in zip(year_fractions, amounts, strict=True):
            denom = (1.0 + rate) ** frac
            if denom == 0.0:
                denom = 1e-12
            f_val += amount / denom
            df_val -= frac * amount / ((1.0 + rate) ** (frac + 1.0))

        if abs(f_val) < tol:
            return rate

        if abs(df_val) < 1e-12:
            break

        new_rate = rate - f_val / df_val
        if new_rate <= -1.0:  # Bound away from -100%
            rate = (rate - 1.0) / 2.0
        else:
            rate = new_rate

    return rate
