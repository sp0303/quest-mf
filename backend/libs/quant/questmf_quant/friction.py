"""Friction model: Exit load, Stamp duty, STT, and Capital Gains Tax.

Rules & Acceptance:
- Test O: A 1% load + 20% STCG example matches a hand-computed golden value.
- Q6: Do not subtract TER from NAV returns (NAV already includes it).
- Spec v2 §18: Indian equity mutual funds taxation rules (Post-Budget 2024: STCG 20%, LTCG 12.5%).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FrictionBreakdown:
    initial_investment: float
    stamp_duty: float
    net_invested: float
    units: float
    gross_proceeds: float
    exit_load: float
    proceeds_after_load: float
    stt: float
    capital_gain: float
    tax: float
    net_proceeds: float
    net_profit: float
    gross_return_pct: float
    net_return_pct: float


def compute_stamp_duty(amount: float, rate: float = 0.00005) -> float:
    """Stamp duty on purchase (0.005% since July 2020)."""
    return amount * rate


def compute_exit_load(proceeds: float, days_held: int, rate: float, exit_load_days: int) -> float:
    """Exit load applied on redemption if days_held < exit_load_days."""
    if days_held < exit_load_days:
        return proceeds * rate
    return 0.0


def compute_stt_equity(gross_proceeds: float, rate: float = 0.001) -> float:
    """Securities Transaction Tax (STT) on redemption of equity funds (0.1% or 0.001)."""
    return gross_proceeds * rate


def compute_capital_gains_tax(
    gain: float,
    days_held: int,
    lt_holding_days: int = 365,
    stcg_rate: float = 0.20,
    ltcg_rate: float = 0.125,
    ltcg_exemption_inr: float = 125000.0,
) -> float:
    """Compute Short-Term or Long-Term Capital Gains Tax.

    If days_held <= lt_holding_days (typically 365 days for equity funds):
        tax = max(0, gain) * stcg_rate (default 20%)
    Else:
        taxable_ltcg = max(0, gain - ltcg_exemption_inr)
        tax = taxable_ltcg * ltcg_rate (default 12.5%)
    """
    if gain <= 0.0:
        return 0.0

    if days_held <= lt_holding_days:
        return gain * stcg_rate
    else:
        taxable_gain = max(0.0, gain - ltcg_exemption_inr)
        return taxable_gain * ltcg_rate


def calculate_net_return(
    initial_amount: float,
    buy_nav: float,
    sell_nav: float,
    days_held: int,
    exit_load_rate: float = 0.01,
    exit_load_days: int = 365,
    stcg_rate: float = 0.20,
    ltcg_rate: float = 0.125,
    stamp_duty_rate: float = 0.00005,
    stt_rate: float = 0.001,
) -> FrictionBreakdown:
    """Calculate comprehensive net return after friction and taxes.

    Execution Flow:
    1. Initial amount pays Stamp Duty -> net invested into units @ buy_nav.
    2. Units redeemed @ sell_nav -> gross proceeds.
    3. Exit load deducted if days_held < exit_load_days.
    4. STT deducted on redemption.
    5. Capital gains = (proceeds after load) - net invested.
    6. Tax deducted.
    7. Net proceeds = proceeds after load - STT - Tax.
    """
    if initial_amount <= 0 or buy_nav <= 0 or sell_nav <= 0:
        raise ValueError("Amounts and NAVs must be positive")

    # 1. Purchase
    stamp_duty = compute_stamp_duty(initial_amount, stamp_duty_rate)
    net_invested = initial_amount - stamp_duty
    units = net_invested / buy_nav

    # 2. Redemption
    gross_proceeds = units * sell_nav
    exit_load = compute_exit_load(gross_proceeds, days_held, exit_load_rate, exit_load_days)
    proceeds_after_load = gross_proceeds - exit_load
    stt = compute_stt_equity(gross_proceeds, stt_rate)

    # 3. Capital Gains and Tax
    capital_gain = proceeds_after_load - net_invested
    tax = compute_capital_gains_tax(
        gain=capital_gain,
        days_held=days_held,
        lt_holding_days=365,
        stcg_rate=stcg_rate,
        ltcg_rate=ltcg_rate,
    )

    # 4. Final net proceeds
    net_proceeds = proceeds_after_load - stt - tax
    net_profit = net_proceeds - initial_amount

    gross_return_pct = (sell_nav / buy_nav) - 1.0
    net_return_pct = net_profit / initial_amount

    return FrictionBreakdown(
        initial_investment=initial_amount,
        stamp_duty=stamp_duty,
        net_invested=net_invested,
        units=units,
        gross_proceeds=gross_proceeds,
        exit_load=exit_load,
        proceeds_after_load=proceeds_after_load,
        stt=stt,
        capital_gain=capital_gain,
        tax=tax,
        net_proceeds=net_proceeds,
        net_profit=net_profit,
        gross_return_pct=gross_return_pct,
        net_return_pct=net_return_pct,
    )
