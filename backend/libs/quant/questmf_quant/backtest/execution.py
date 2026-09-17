"""Backtest execution simulator.

Rules:
- Q11: Backtests execute at NAV(t + EXEC_LAG), respect SWITCH_GAP / MIN_HOLD and investability.
- Test M: Backtest cannot buy at NAV(d); first possible fill is NAV(d + EXEC_LAG).
- Test N: Restricted fund at d is never bought at d.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class OrderAction(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True)
class TradeOrder:
    portfolio_id: int
    action: OrderAction
    decision_date: date
    target_weight: float


@dataclass(frozen=True)
class Position:
    portfolio_id: int
    buy_date: date
    buy_nav: float
    units: float
    weight: float


class ExecutionEngine:
    def __init__(
        self,
        exec_lag_days: int = 1,
        min_hold_days: int = 30,
        switch_gap_days: int = 2,
    ) -> None:
        if exec_lag_days < 1:
            raise ValueError(
                "exec_lag_days must be >= 1 (cannot execute same-day without lookahead)"
            )
        self.exec_lag_days = exec_lag_days
        self.min_hold_days = min_hold_days
        self.switch_gap_days = switch_gap_days

    def can_invest(
        self, portfolio_id: int, decision_date: date, restricted_portfolios: set[int]
    ) -> bool:
        """Check if portfolio is eligible for investment (Test N)."""
        return portfolio_id not in restricted_portfolios

    def calculate_fill_date(
        self,
        decision_date: date,
        trading_calendar: list[date],
    ) -> date | None:
        """Find the execution fill date after decision_date with EXEC_LAG (Test M)."""
        import bisect

        idx = bisect.bisect_right(trading_calendar, decision_date)
        fill_idx = idx + (self.exec_lag_days - 1)
        if fill_idx < len(trading_calendar):
            return trading_calendar[fill_idx]
        return None

    def can_exit(self, position: Position, current_date: date) -> bool:
        """Check if position has satisfied min_hold_days."""
        return (current_date - position.buy_date).days >= self.min_hold_days
