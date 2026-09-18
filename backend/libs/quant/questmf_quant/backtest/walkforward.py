"""Walk-forward backtest simulator.

Rules:
- Q11: Backtests execute at NAV(t + EXEC_LAG), respect SWITCH_GAP / MIN_HOLD and investability,
  and report gross and net results.
- Test M: Cannot buy at NAV(d); fill is NAV(d + EXEC_LAG).
- Test N: Restricted funds are never bought.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from questmf_quant.backtest.execution import ExecutionEngine
from questmf_quant.backtest.stats import compute_rank_ic
from questmf_quant.drawdown import max_drawdown
from questmf_quant.friction import calculate_net_return
from questmf_quant.returns import cagr
from questmf_quant.risk import sharpe_ratio


@dataclass(frozen=True)
class BacktestConfig:
    top_k: int = 3
    rebalance_months: int = 3
    exec_lag_days: int = 1
    min_hold_days: int = 30
    initial_capital: float = 100000.0
    exit_load_rate: float = 0.01
    exit_load_days: int = 365
    stcg_rate: float = 0.20
    ltcg_rate: float = 0.125
    annual_rf: float = 0.065


@dataclass
class Holding:
    portfolio_id: int
    buy_date: date
    buy_nav: float
    units: float
    gross_cost: float
    net_invested: float
    last_nav: float = 0.0


@dataclass
class BacktestResult:
    equity_curve_gross: list[tuple[date, float]]
    equity_curve_net: list[tuple[date, float]]
    summary: dict[str, Any]
    rank_ics: list[float] = field(default_factory=list)


def run_walkforward_backtest(
    nav_by_portfolio: dict[int, dict[date, float]],
    scores_by_date: dict[date, dict[int, float]],
    trading_calendar: list[date],
    restricted_portfolios_by_date: dict[date, set[int]] | None = None,
    config: BacktestConfig | None = None,
) -> BacktestResult:
    """Execute walk-forward backtest simulation with lag, restrictions, and friction."""
    cfg = config or BacktestConfig()
    engine = ExecutionEngine(
        exec_lag_days=cfg.exec_lag_days,
        min_hold_days=cfg.min_hold_days,
    )
    restricted_map = restricted_portfolios_by_date or {}

    if not trading_calendar:
        return BacktestResult(
            equity_curve_gross=[],
            equity_curve_net=[],
            summary={
                "cagr_gross": 0.0,
                "cagr_net": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "rank_ic_mean": 0.0,
            },
        )

    # Determine rebalance decision dates (e.g. every rebalance_months on trading calendar)
    decision_dates: list[date] = []
    curr_m = -1
    for d in trading_calendar:
        if d in scores_by_date:
            m_val = d.year * 12 + d.month
            if curr_m == -1 or (m_val - curr_m) >= cfg.rebalance_months:
                decision_dates.append(d)
                curr_m = m_val

    if not decision_dates and scores_by_date:
        decision_dates = sorted(scores_by_date.keys())

    # State tracking
    gross_cash = cfg.initial_capital
    net_cash = cfg.initial_capital
    gross_holdings: dict[int, list[float]] = {}  # pid -> [units, last_nav]
    net_holdings: dict[int, Holding] = {}  # pid -> Holding

    equity_gross: list[tuple[date, float]] = []
    equity_net: list[tuple[date, float]] = []
    rank_ics: list[float] = []

    # Map rebalance fill dates
    pending_orders: dict[date, list[int]] = {}  # fill_date -> target pids
    for d in decision_dates:
        fill_d = engine.calculate_fill_date(d, trading_calendar)
        if fill_d is not None:
            # Score ranking at decision date
            scores = scores_by_date.get(d, {})
            restricted = restricted_map.get(d, set())
            eligible = [
                pid for pid, score in scores.items() if engine.can_invest(pid, d, restricted)
            ]
            ranked = sorted(eligible, key=lambda p: scores[p], reverse=True)
            target_pids = ranked[: cfg.top_k]
            pending_orders[fill_d] = target_pids

            # Calculate forward rank IC if forward prices exist
            # Compare scores with forward 60-day returns
            if len(scores) >= 5:
                fwd_returns: list[float] = []
                score_vals: list[float] = []
                import bisect

                cur_idx = bisect.bisect_left(trading_calendar, d)
                fwd_idx = min(len(trading_calendar) - 1, cur_idx + 60)
                fwd_d = trading_calendar[fwd_idx]
                for pid, sc in scores.items():
                    p_navs = nav_by_portfolio.get(pid, {})
                    if d in p_navs and fwd_d in p_navs and p_navs[d] > 0:
                        ret = (p_navs[fwd_d] / p_navs[d]) - 1.0
                        score_vals.append(sc)
                        fwd_returns.append(ret)
                ic = compute_rank_ic(score_vals, fwd_returns)
                if ic is not None:
                    rank_ics.append(ic)

    # Walk through every day on the trading calendar
    for d in trading_calendar:
        # Check if today is a rebalance fill date
        if d in pending_orders:
            targets = pending_orders[d]
            # 1. Exit positions not in targets (respecting min_hold_days)
            to_exit_net = [
                pid
                for pid, h in net_holdings.items()
                if pid not in targets and (d - h.buy_date).days >= cfg.min_hold_days
            ]
            for pid in to_exit_net:
                h = net_holdings.pop(pid)
                nav = nav_by_portfolio.get(pid, {}).get(d, h.last_nav or h.buy_nav)
                days_held = (d - h.buy_date).days
                f_res = calculate_net_return(
                    initial_amount=h.net_invested,
                    buy_nav=h.buy_nav,
                    sell_nav=nav,
                    days_held=days_held,
                    exit_load_rate=cfg.exit_load_rate,
                    exit_load_days=cfg.exit_load_days,
                    stcg_rate=cfg.stcg_rate,
                    ltcg_rate=cfg.ltcg_rate,
                )
                net_cash += f_res.net_proceeds

            to_exit_gross = [pid for pid in gross_holdings if pid not in targets]
            for pid in to_exit_gross:
                units, last_nav = gross_holdings.pop(pid)
                nav = nav_by_portfolio.get(pid, {}).get(d, last_nav)
                gross_cash += units * nav

            # 2. Buy new targets
            new_gross_targets = [pid for pid in targets if pid not in gross_holdings]
            if new_gross_targets and gross_cash > 0:
                alloc_per = gross_cash / len(new_gross_targets)
                for pid in new_gross_targets:
                    nav = nav_by_portfolio.get(pid, {}).get(d, 1.0)
                    units = alloc_per / nav
                    gross_holdings[pid] = [units, nav]
                gross_cash = 0.0

            new_net_targets = [pid for pid in targets if pid not in net_holdings]
            if new_net_targets and net_cash > 0:
                alloc_per = net_cash / len(new_net_targets)
                for pid in new_net_targets:
                    nav = nav_by_portfolio.get(pid, {}).get(d, 1.0)
                    stamp = alloc_per * 0.00005
                    net_inv = alloc_per - stamp
                    units = net_inv / nav
                    net_holdings[pid] = Holding(
                        portfolio_id=pid,
                        buy_date=d,
                        buy_nav=nav,
                        units=units,
                        gross_cost=alloc_per,
                        net_invested=net_inv,
                        last_nav=nav,
                    )
                net_cash = 0.0

        # Mark-to-market daily valuations
        g_val = gross_cash
        for pid, gh in gross_holdings.items():
            nav = nav_by_portfolio.get(pid, {}).get(d)
            if nav is not None:
                gh[1] = nav
            g_val += gh[0] * gh[1]

        n_val = net_cash
        for pid, h in net_holdings.items():
            nav = nav_by_portfolio.get(pid, {}).get(d)
            if nav is not None:
                h.last_nav = nav
            days_held = (d - h.buy_date).days
            f_res = calculate_net_return(
                initial_amount=h.net_invested,
                buy_nav=h.buy_nav,
                sell_nav=h.last_nav,
                days_held=days_held,
                exit_load_rate=cfg.exit_load_rate,
                exit_load_days=cfg.exit_load_days,
                stcg_rate=cfg.stcg_rate,
                ltcg_rate=cfg.ltcg_rate,
            )
            n_val += f_res.net_proceeds

        equity_gross.append((d, round(g_val, 2)))
        equity_net.append((d, round(n_val, 2)))

    # Compute Summary
    g_vals = [v for _, v in equity_gross]
    n_vals = [v for _, v in equity_net]

    days = float((trading_calendar[-1] - trading_calendar[0]).days)
    if days <= 0:
        days = 365.25
    c_gross = cagr(g_vals[0], g_vals[-1], days=days) if days > 0 and g_vals else 0.0
    c_net = cagr(n_vals[0], n_vals[-1], days=days) if days > 0 and n_vals else 0.0

    mdd_val, _, _ = max_drawdown(n_vals) if n_vals else (0.0, 0, 0)

    # Net daily returns for Sharpe
    net_daily_rets = [
        (n_vals[i] / n_vals[i - 1]) - 1.0 for i in range(1, len(n_vals)) if n_vals[i - 1] > 0
    ]
    shp = sharpe_ratio(net_daily_rets, annual_rf=cfg.annual_rf) if net_daily_rets else 0.0
    mean_ic = sum(rank_ics) / len(rank_ics) if rank_ics else 0.0

    summary = {
        "cagr_gross": round(c_gross, 4),
        "cagr_net": round(c_net, 4),
        "sharpe_ratio": round(shp, 2),
        "max_drawdown": round(mdd_val, 4),
        "rank_ic_mean": round(mean_ic, 4),
        "top_k": cfg.top_k,
        "rebalance_months": cfg.rebalance_months,
    }

    return BacktestResult(
        equity_curve_gross=equity_gross,
        equity_curve_net=equity_net,
        summary=summary,
        rank_ics=rank_ics,
    )
