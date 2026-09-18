from datetime import date, timedelta

from questmf_quant.backtest.walkforward import (
    BacktestConfig,
    run_walkforward_backtest,
)


def test_walkforward_simulation():
    # Setup 100 trading days
    base_date = date(2023, 1, 1)
    calendar = [base_date + timedelta(days=i) for i in range(120)]

    # 3 portfolios
    nav_by_portfolio = {
        101: {d: 100.0 * (1.0 + 0.001 * i) for i, d in enumerate(calendar)},
        102: {d: 50.0 * (1.0 + 0.0005 * i) for i, d in enumerate(calendar)},
        103: {d: 20.0 * (1.0 - 0.0002 * i) for i, d in enumerate(calendar)},
    }

    # Scores at day 0 and day 60
    scores_by_date = {
        calendar[0]: {101: 90.0, 102: 80.0, 103: 40.0},
        calendar[60]: {101: 85.0, 102: 95.0, 103: 30.0},
    }

    config = BacktestConfig(
        top_k=2,
        rebalance_months=2,
        exec_lag_days=1,
        min_hold_days=10,
        initial_capital=100000.0,
    )

    result = run_walkforward_backtest(
        nav_by_portfolio=nav_by_portfolio,
        scores_by_date=scores_by_date,
        trading_calendar=calendar,
        config=config,
    )

    assert len(result.equity_curve_gross) == 120
    assert len(result.equity_curve_net) == 120
    assert result.summary["top_k"] == 2
    assert result.summary["cagr_gross"] > 0
    # Net return should be less than or equal to gross return due to friction
    assert result.summary["cagr_net"] <= result.summary["cagr_gross"]
    assert result.summary["max_drawdown"] <= 0.0
