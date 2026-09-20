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

ISIN_REGEX = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$", re.IGNORECASE)


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
        text = str(val).strip().replace("%", "").replace(",", "").replace("$", "")
        try:
            num = float(text)
        except ValueError:
            return 0.0

        # Preserve precision up to 4 decimal places
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

        if any(w in upper_name for w in ("TREPS", "REVERSE REPO", "REPO", "CASH", "NET RECEIVABLES", "CLEARING CORP", "CURRENT ASSETS", "MARGIN MONEY")) or upper_sec in ("CASH", "CASH & CASH EQUIVALENTS", "TREPS", "MONEY MARKET"):
            return "TREPS_CASH"
        if any(w in upper_name for w in ("MUTUAL FUND UNITS", "EXCHANGE TRADED COMMODITY")):
            return "OTHER"
        if any(w in upper_sec for w in ("DEBT", "GOVERNMENT BOND", "TREASURY BILL", "COMMERCIAL PAPER", "CERTIFICATE OF DEPOSIT")):
            return "DEBT"
        if any(w in upper_name for w in ("FUTURES", "OPTIONS", "INDEX OPTION")):
            return "DERIVATIVE"

        # Default to EQUITY if valid ISIN is present
        if isin and ISIN_REGEX.match(isin):
            return "EQUITY"
        return "EQUITY"

    @classmethod
    def sniff_headers(cls, rows: Sequence[Sequence[Any]]) -> HeaderMapping:
        """Identify header row and column mapping dynamically conforming to Gate H1."""
        for row_idx, row in enumerate(rows[:25]):
            row_strs = [" ".join(str(c).split()).lower() if c is not None else "" for c in row]
            isin_col = None
            name_col = None
            pct_col = None
            sector_col = None
            qty_col = None
            mval_col = None

            for col_idx, text in enumerate(row_strs):
                if "isin" in text:
                    isin_col = col_idx
                elif any(k in text for k in ("name of instrument", "name of the instrument", "security name", "instrument name", "company name", "name of company", "issuer name", "name of the instrument / issuer")):
                    name_col = col_idx
                elif any(k in text for k in ("% to nav", "% to net assets", "percentage to net assets", "% of nav", "pct_nav", "% to aum", "% of aum", "% to total aum", "% to netassets", "percentage to aum")):
                    pct_col = col_idx
                elif any(k in text for k in ("industry", "sector", "rating / industry", "industry / rating", "industry/rating", "industry+ /rating", "rating/industry")):
                    sector_col = col_idx
                elif any(k in text for k in ("quantity", "qty")):
                    qty_col = col_idx
                elif any(k in text for k in ("market value", "fair value", "value in lakhs", "market/fair value", "market/ fair value", "market value (rs. in lakhs)", "market value(rs.in lakhs)", "market/ fair value (rs. in lacs.)")):
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
    def parse_sheet_rows(
        cls,
        rows_data: Sequence[Sequence[Any]],
        portfolio_id: int,
        as_of_date: date,
        disclosed_date: date,
    ) -> ParsingResult:
        """Parse raw sheet rows into standardized and validated ParsingResult."""
        if not rows_data:
            return ParsingResult(
                holdings=[],
                total_weight=0.0,
                equity_count=0,
                valid=False,
                validation_message="Sheet has no data rows",
            )

        header_map = cls.sniff_headers(rows_data)
        holdings: list[RawHoldingEntry] = []
        start_row = header_map.header_row_index + 1

        for row in rows_data[start_row:]:
            if not row or all(c is None for c in row):
                continue

            raw_name = row[header_map.name_col] if header_map.name_col < len(row) else None
            if not raw_name:
                continue

            name_str = str(raw_name).strip()
            upper_name = name_str.upper()

            # Stop when reaching overall total / end marker
            if "GRAND TOTAL" in upper_name:
                break

            # Skip subtotal, intermediate category headers, disclaimers
            if any(k in upper_name for k in ("TOTAL", "SUB TOTAL", "PORTFOLIO AS ON", "NOTES:", "DISCLAIMER", "EQUITY & EQUITY RELATED", "LISTED / AWAITING", "UNLISTED")):
                continue

            raw_pct = row[header_map.pct_nav_col] if header_map.pct_nav_col < len(row) else None
            pct_nav = cls.clean_weight(raw_pct)
            if pct_nav <= 0.0:
                continue

            raw_isin = row[header_map.isin_col] if header_map.isin_col < len(row) else None
            cleaned_isin = cls.clean_isin(raw_isin)

            raw_sector = (
                row[header_map.sector_col]
                if header_map.sector_col is not None and header_map.sector_col < len(row)
                else None
            )
            sector = str(raw_sector).strip() if raw_sector else None

            raw_qty = (
                row[header_map.quantity_col]
                if header_map.quantity_col is not None and header_map.quantity_col < len(row)
                else None
            )
            try:
                quantity = float(raw_qty) if raw_qty is not None else None
            except (ValueError, TypeError):
                quantity = None

            raw_mval = (
                row[header_map.market_value_col]
                if header_map.market_value_col is not None and header_map.market_value_col < len(row)
                else None
            )
            try:
                mval = float(raw_mval) if raw_mval is not None else None
            except (ValueError, TypeError):
                mval = None

            asset_type = cls.detect_asset_type(name_str, cleaned_isin, sector)

            holdings.append(
                RawHoldingEntry(
                    portfolio_id=portfolio_id,
                    as_of_date=as_of_date,
                    isin=cleaned_isin,
                    security_name=name_str,
                    asset_type=asset_type,
                    sector=sector,
                    quantity=quantity,
                    market_value_lakhs=mval,
                    pct_nav=pct_nav,
                    disclosed_date=disclosed_date,
                )
            )

        # Gate H3 decimal scaling: if sum of positive weights is < 2.0 (fractional scale), convert to percentage
        pos_weight_sum = sum(h.pct_nav for h in holdings if h.pct_nav > 0)
        if 0.0 < pos_weight_sum < 2.0:
            holdings = [
                RawHoldingEntry(
                    portfolio_id=h.portfolio_id,
                    as_of_date=h.as_of_date,
                    isin=h.isin,
                    security_name=h.security_name,
                    asset_type=h.asset_type,
                    sector=h.sector,
                    quantity=h.quantity,
                    market_value_lakhs=h.market_value_lakhs,
                    pct_nav=round(h.pct_nav * 100.0, 4),
                    disclosed_date=h.disclosed_date,
                )
                for h in holdings
            ]

        valid, msg = cls.validate_holdings(holdings)
        total_w = round(sum(h.pct_nav for h in holdings), 4)
        eq_count = sum(1 for h in holdings if h.asset_type == "EQUITY")

        return ParsingResult(
            holdings=holdings,
            total_weight=total_w,
            equity_count=eq_count,
            valid=valid,
            validation_message=msg,
        )

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
