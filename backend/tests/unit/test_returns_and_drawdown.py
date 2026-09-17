import math

import numpy as np
import pytest
from questmf_quant.downsample import lttb
from questmf_quant.drawdown import max_drawdown, underwater_series
from questmf_quant.returns import (
    active_return,
    cagr,
    log_return,
    simple_return,
)


def test_simple_and_log_returns():
    # 100 -> 120 is +20%
    assert simple_return(100.0, 120.0) == pytest.approx(0.20)
    assert log_return(100.0, 120.0) == pytest.approx(math.log(1.20))

    # Active return (Q5)
    fund_r = 0.20
    bench_r = 0.15
    assert active_return(fund_r, bench_r) == pytest.approx(0.05)


def test_cagr():
    # 100 -> 200 in 730.5 days (~2 years) is approx (2)^(0.5) - 1 ~ 41.42%
    res = cagr(100.0, 200.0, 730.5)
    assert res == pytest.approx((2.0**0.5) - 1.0, rel=1e-5)


def test_max_drawdown_and_underwater():
    navs = [100.0, 120.0, 110.0, 90.0, 105.0, 130.0]
    # Peak is 120, trough is 90 -> drawdown is (90 - 120) / 120 = -30 / 120 = -0.25 (-25%)
    mdd, peak_idx, trough_idx = max_drawdown(navs)
    assert mdd == pytest.approx(-0.25)
    assert peak_idx == 1  # 120.0
    assert trough_idx == 3  # 90.0

    uw = underwater_series(navs)
    assert uw[1] == 0.0  # at peak
    assert uw[3] == pytest.approx(-0.25)  # at trough


def test_downsample_lttb():
    # 10,000 points downsampled to 500
    x = list(range(10000))
    y = [float(np.sin(i / 100.0) + (i / 1000.0)) for i in range(10000)]

    sampled_x, sampled_y = lttb(x, y, target_points=500)
    assert len(sampled_x) == 500
    assert len(sampled_y) == 500
    # First and last points are strictly preserved
    assert sampled_x[0] == x[0]
    assert sampled_x[-1] == x[-1]
    assert sampled_y[0] == y[0]
    assert sampled_y[-1] == y[-1]
