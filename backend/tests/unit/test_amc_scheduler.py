"""Unit tests for AMC Holdings Scheduler."""

from datetime import date
from workers.amc_holdings_scheduler import REGISTERED_AMCS, compute_default_dates


def test_registered_amcs_coverage():
    assert "nippon" in REGISTERED_AMCS
    assert "hdfc" in REGISTERED_AMCS
    assert "icici" in REGISTERED_AMCS
    assert "sbi" in REGISTERED_AMCS
    assert "kotak" in REGISTERED_AMCS

    nippon = REGISTERED_AMCS["nippon"]
    assert 101 in nippon.portfolio_schemes

    hdfc = REGISTERED_AMCS["hdfc"]
    assert 103 in hdfc.portfolio_schemes


def test_compute_default_dates():
    as_of, disclosed = compute_default_dates()
    assert isinstance(as_of, date)
    assert isinstance(disclosed, date)
    assert disclosed > as_of
    # Disclosed is always on the 10th of the current month
    assert disclosed.day == 10
