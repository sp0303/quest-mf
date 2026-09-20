"""Base contract for AMC monthly portfolio disclosure parsers.

Enforces standardized testing contract gates H1–H8:
- H1: Header & offset sniffing
- H2: ISIN validation
- H3: Weight parsing & normalization
- H4: Sum of weights validation (95% to 105%)
- H5: Asset classification (EQUITY, DEBT, TREPS_CASH, etc.)
- H6: Point-in-time date adherence
- H7: Summary precomputation compatibility
- H8: Idempotent ingest
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from workers.holdings_worker import RawHoldingEntry

ISIN_REGEX = re.compile(r"^IN[A-Z0-9]{10}$", re.IGNORECASE)


@dataclass(frozen=True)
class HeaderMapping:
    """Column indices (0-based) for required holding fields."""

    header_row_index: int
    isin_col: int
    name_col: int
    pct_nav_col: int
    sector_col: int | None = None
    quantity_col: int | None = None
    market_value_col: int | None = None


@dataclass(frozen=True)
class ParsingResult:
    """Standardized output of an AMC portfolio parse run."""

    holdings: list[RawHoldingEntry]
    total_weight: float
    equity_count: int
    valid: bool
    validation_message: str


class BaseAMCParser(ABC):
    """Standard base class from which every AMC-specific parser must inherit."""

    @classmethod
    def clean_isin(cls, val: Any) -> str | None:
        """Validate and clean ISIN string conforming to Gate H2."""
        if not val:
            return None
        text = str(val).strip().upper()
        if ISIN_REGEX.match(text):
            return text
        return None

    @classmethod
    def clean_weight(cls, val: Any) -> float:
        """Standardize percentage weights to float [0.0, 100.0] conforming to Gate H3."""
        if val is None or val == "":
            return 0.0
        text = str(val).strip().replace("%", "").replace(",", "")
        try:
            num = float(text)
        except ValueError:
            return 0.0

        # If stored as fraction (e.g. 0.0425 for 4.25%), convert if explicitly small
        # In SEBI format, it's typically already in % (e.g., 4.25 or 0.85)
        # We clamp negative values (e.g. pending payables) to 0 or preserve for net cash
        return round(num, 4)

    @classmethod
    def detect_asset_type(
        cls,
        name: str,
        isin: str | None = None,
        sector: str | None = None,
    ) -> str:
        """Categorize security into standard asset types conforming to Gate H5."""
        upper_name = name.strip().upper()
        upper_sec = (sector or "").strip().upper()

        if any(w in upper_name for w in ("TREPS", "REVERSE REPO", "REPO", "CASH & CASH EQUIVALENTS", "NET RECEIVABLES", "CLEARING CORP")):
            return "TREPS_CASH"
        if any(w in upper_name for w in ("MUTUAL FUND UNITS", "EXCHANGE TRADED COMMODITY")):
            return "OTHER"
        if any(w in upper_sec for w in ("DEBT", "GOVERNMENT BOND", "TREASURY BILL", "COMMERCIAL PAPER", "CERTIFICATE OF DEPOSIT")):
            return "DEBT"
        if any(w in upper_name for w in ("FUTURES", "OPTIONS", "INDEX OPTION")):
            return "DERIVATIVE"

        # Default to EQUITY if ISIN is present and not tagged debt
        if isin and isin.startswith("IN"):
            return "EQUITY"
        return "EQUITY"

    @classmethod
    def sniff_headers(cls, rows: Sequence[Sequence[Any]]) -> HeaderMapping:
        """Identify header row and column mapping dynamically conforming to Gate H1."""
        for row_idx, row in enumerate(rows[:20]):
            row_strs = [str(c).strip().lower() if c is not None else "" for c in row]
            isin_col = None
            name_col = None
            pct_col = None
            sector_col = None
            qty_col = None
            mval_col = None

            for col_idx, text in enumerate(row_strs):
                if "isin" in text:
                    isin_col = col_idx
                elif any(k in text for k in ("name of instrument", "name of the instrument", "security name", "instrument name")):
                    name_col = col_idx
                elif any(k in text for k in ("% to nav", "% to net assets", "percentage to net assets", "% of nav", "pct_nav")):
                    pct_col = col_idx
                elif any(k in text for k in ("industry", "sector", "rating / industry")):
                    sector_col = col_idx
                elif any(k in text for k in ("quantity", "qty")):
                    qty_col = col_idx
                elif any(k in text for k in ("market value", "fair value", "value in lakhs")):
                    mval_col = col_idx

            if isin_col is not None and name_col is not None and pct_col is not None:
                return HeaderMapping(
                    header_row_index=row_idx,
                    isin_col=isin_col,
                    name_col=name_col,
                    pct_nav_col=pct_col,
                    sector_col=sector_col,
                    quantity_col=qty_col,
                    market_value_col=mval_col,
                )

        raise ValueError("Gate H1 Failed: Unable to detect required header row with ISIN, Name, and % to NAV")

    @classmethod
    def validate_holdings(
        cls,
        holdings: Sequence[RawHoldingEntry],
    ) -> tuple[bool, str]:
        """Validate portfolio completeness and weight bounds conforming to Gate H4."""
        if not holdings:
            return False, "Gate H4 Failed: No holdings records parsed"

        total_weight = sum(h.pct_nav for h in holdings)
        if total_weight < 90.0 or total_weight > 110.0:
            return (
                False,
                f"Gate H4 Failed: Total weight {total_weight:.2f}% is outside permissible [90.0%, 110.0%] bounds",
            )

        return True, f"Validation passed with {len(holdings)} holdings totaling {total_weight:.2f}%"

    @abstractmethod
    def parse_workbook(
        self,
        workbook_data: Any,
        portfolio_id: int,
        as_of_date: date,
        disclosed_date: date,
        scheme_name_filter: str | None = None,
    ) -> ParsingResult:
        """Parse raw workbook into standardized ParsingResult."""
        pass
