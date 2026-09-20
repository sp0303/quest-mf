"""Portfolio overlap calculation module.

Adheres to Rule Q3, Rule 3 (Pure Quant Core: no I/O, no DB, no clock).
Computes the true pairwise portfolio overlap between two fund portfolios:

    Overlap(A, B) = sum_{i in A cap B} min(w_{A,i}, w_{B,i})

Where:
    w_{A,i} is the percentage weight of security i in Portfolio A.
    w_{B,i} is the percentage weight of security i in Portfolio B.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class HoldingItem:
    """A single security holding within a portfolio."""

    identifier: str  # Unique security identifier, typically ISIN or normalized symbol
    name: str
    weight: float  # Percentage weight, e.g., 8.5 for 8.5%
    sector: str | None = None
    asset_type: str = "EQUITY"


@dataclass(frozen=True)
class CommonHolding:
    """A security common to two portfolios."""

    identifier: str
    name: str
    weight_a: float
    weight_b: float
    overlap_weight: float  # min(weight_a, weight_b)
    sector: str | None = None


@dataclass(frozen=True)
class OverlapResult:
    """Pairwise portfolio overlap results."""

    overlap_pct: float
    common_holdings_count: int
    fund_a_total_weight: float
    fund_b_total_weight: float
    common_holdings: list[CommonHolding]
    unique_to_a_count: int
    unique_to_b_count: int


def compute_weights_overlap(
    weights_a: Mapping[str, float],
    weights_b: Mapping[str, float],
) -> float:
    """Compute the sum of min(w_A, w_B) across common security identifiers.

    Args:
        weights_a: Mapping of security ID to percentage weight in portfolio A.
        weights_b: Mapping of security ID to percentage weight in portfolio B.

    Returns:
        Overlap percentage rounded to 4 decimal places.
    """
    if not weights_a or not weights_b:
        return 0.0

    common_keys = set(weights_a.keys()) & set(weights_b.keys())
    total_overlap = sum(
        min(max(0.0, float(weights_a[k])), max(0.0, float(weights_b[k]))) for k in common_keys
    )
    return round(total_overlap, 4)


def compute_portfolio_overlap(
    holdings_a: Sequence[HoldingItem],
    holdings_b: Sequence[HoldingItem],
) -> OverlapResult:
    """Compute detailed pairwise portfolio overlap between two sets of holdings.

    Security identifiers are matched case-insensitively.
    Common holdings are returned ordered descending by their shared overlap weight.

    Args:
        holdings_a: List of holdings for portfolio A.
        holdings_b: List of holdings for portfolio B.

    Returns:
        OverlapResult containing total overlap %, counts, and common holdings.
    """
    # Aggregate duplicate entries per identifier if any (e.g., split tranches)
    dict_a: dict[str, HoldingItem] = {}
    weights_a: dict[str, float] = {}
    for h in holdings_a:
        key = h.identifier.strip().upper()
        if not key:
            continue
        dict_a[key] = h
        weights_a[key] = weights_a.get(key, 0.0) + max(0.0, float(h.weight))

    dict_b: dict[str, HoldingItem] = {}
    weights_b: dict[str, float] = {}
    for h in holdings_b:
        key = h.identifier.strip().upper()
        if not key:
            continue
        dict_b[key] = h
        weights_b[key] = weights_b.get(key, 0.0) + max(0.0, float(h.weight))

    total_a = round(sum(weights_a.values()), 4)
    total_b = round(sum(weights_b.values()), 4)

    common_keys = set(weights_a.keys()) & set(weights_b.keys())
    common_holdings: list[CommonHolding] = []

    for k in common_keys:
        w_a = weights_a[k]
        w_b = weights_b[k]
        shared = min(w_a, w_b)
        h_ref = dict_a[k]
        common_holdings.append(
            CommonHolding(
                identifier=k,
                name=h_ref.name,
                weight_a=round(w_a, 4),
                weight_b=round(w_b, 4),
                overlap_weight=round(shared, 4),
                sector=h_ref.sector or dict_b[k].sector,
            )
        )

    # Sort common holdings descending by overlap weight
    common_holdings.sort(key=lambda x: x.overlap_weight, reverse=True)

    overlap_pct = round(sum(h.overlap_weight for h in common_holdings), 4)
    unique_to_a = len(set(weights_a.keys()) - common_keys)
    unique_to_b = len(set(weights_b.keys()) - common_keys)

    return OverlapResult(
        overlap_pct=overlap_pct,
        common_holdings_count=len(common_holdings),
        fund_a_total_weight=total_a,
        fund_b_total_weight=total_b,
        common_holdings=common_holdings,
        unique_to_a_count=unique_to_a,
        unique_to_b_count=unique_to_b,
    )
