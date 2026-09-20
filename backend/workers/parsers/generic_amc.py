"""Generic AMC monthly portfolio disclosure parser.

Conforms to BaseAMCParser contract Gates H1–H8.
Parses standard SEBI-mandated monthly portfolio workbooks (.xlsx).
"""

from __future__ import annotations

import io
from datetime import date
from typing import Any

import openpyxl

from workers.parsers.base import BaseAMCParser, ParsingResult


class GenericAMCParser(BaseAMCParser):
    """Generic parser for SEBI-compliant AMC monthly portfolio workbooks."""

    def __init__(self, amc_code: str = "GENERIC", default_scheme_filter: str | None = None):
        self.amc_code = amc_code.upper()
        self.default_scheme_filter = default_scheme_filter

    def parse_workbook(
        self,
        workbook_data: str | bytes | io.BytesIO,
        portfolio_id: int,
        as_of_date: date,
        disclosed_date: date,
        scheme_name_filter: str | None = None,
    ) -> ParsingResult:
        """Parse SEBI-mandated monthly Excel workbook into validated holdings list."""
        if isinstance(workbook_data, (bytes, bytearray)):
            wb = openpyxl.load_workbook(io.BytesIO(workbook_data), data_only=True)
        elif isinstance(workbook_data, io.BytesIO):
            wb = openpyxl.load_workbook(workbook_data, data_only=True)
        else:
            wb = openpyxl.load_workbook(workbook_data, data_only=True)

        target_filter = (scheme_name_filter or self.default_scheme_filter or "").strip().lower()
        target_sheet = None

        # 1. Match sheet by name if multiple sheets exist
        if target_filter:
            compact_filter = target_filter.replace(" ", "")
            for name in wb.sheetnames:
                compact_name = name.lower().replace(" ", "")
                if target_filter in name.lower() or compact_filter in compact_name:
                    target_sheet = wb[name]
                    break

        # 2. Check if an Index sheet exists mapping code -> full name (e.g. Nippon India, Tata)
        index_sheets = [s for s in wb.sheetnames if s.lower() == "index"]
        if target_sheet is None and index_sheets and target_filter:
            idx_ws = wb[index_sheets[0]]
            for row in idx_ws.iter_rows(values_only=True):
                non_empty = [str(c).strip() for c in row if c is not None]
                if any(target_filter in c.lower() for c in non_empty):
                    for c in non_empty:
                        if c in wb.sheetnames:
                            target_sheet = wb[c]
                            break
                    if target_sheet is not None:
                        break

        # 3. Check sheet title banner / header within top 5 rows (e.g. Quant MF sheets like qSCF)
        if target_sheet is None and target_filter:
            for name in wb.sheetnames:
                ws = wb[name]
                for r in ws.iter_rows(values_only=True, max_row=5):
                    row_txt = " ".join(str(c) for c in r if c is not None).lower()
                    if target_filter in row_txt:
                        target_sheet = ws
                        break
                if target_sheet is not None:
                    break

        if target_sheet is None:
            target_sheet = wb.active or wb.worksheets[0]

        rows_data: list[list[Any]] = []
        for row in target_sheet.iter_rows(values_only=True):
            rows_data.append(list(row))

        return self.parse_sheet_rows(
            rows_data=rows_data,
            portfolio_id=portfolio_id,
            as_of_date=as_of_date,
            disclosed_date=disclosed_date,
        )


class HDFCParser(GenericAMCParser):
    """Parser for HDFC Asset Management monthly portfolio disclosures."""

    def __init__(self, default_scheme_filter: str | None = "HDFC Small Cap"):
        super().__init__(amc_code="HDFC", default_scheme_filter=default_scheme_filter)


class ICICIPrudentialParser(GenericAMCParser):
    """Parser for ICICI Prudential AMC monthly portfolio disclosures."""

    def __init__(self, default_scheme_filter: str | None = "Bluechip"):
        super().__init__(amc_code="ICICI_PRU", default_scheme_filter=default_scheme_filter)


class SBIParser(GenericAMCParser):
    """Parser for SBI Funds Management monthly portfolio disclosures."""

    def __init__(self, default_scheme_filter: str | None = "Small Cap"):
        super().__init__(amc_code="SBI", default_scheme_filter=default_scheme_filter)


class KotakParser(GenericAMCParser):
    """Parser for Kotak Mahindra AMC monthly portfolio disclosures."""

    def __init__(self, default_scheme_filter: str | None = "Small Cap"):
        super().__init__(amc_code="KOTAK", default_scheme_filter=default_scheme_filter)


class QuantParser(GenericAMCParser):
    """Parser for Quant Mutual Fund monthly portfolio disclosures."""

    def __init__(self, default_scheme_filter: str | None = "Small Cap"):
        super().__init__(amc_code="QUANT", default_scheme_filter=default_scheme_filter)


class AxisParser(GenericAMCParser):
    """Parser for Axis Mutual Fund monthly portfolio disclosures."""

    def __init__(self, default_scheme_filter: str | None = "Small Cap"):
        super().__init__(amc_code="AXIS", default_scheme_filter=default_scheme_filter)


class PPFASParser(GenericAMCParser):
    """Parser for PPFAS Mutual Fund monthly portfolio disclosures."""

    def __init__(self, default_scheme_filter: str | None = "Flexi Cap"):
        super().__init__(amc_code="PPFAS", default_scheme_filter=default_scheme_filter)


class TataParser(GenericAMCParser):
    """Parser for Tata Mutual Fund monthly portfolio disclosures."""

    def __init__(self, default_scheme_filter: str | None = "Small Cap"):
        super().__init__(amc_code="TATA", default_scheme_filter=default_scheme_filter)


class BandhanParser(GenericAMCParser):
    """Parser for Bandhan Mutual Fund monthly portfolio disclosures."""

    def __init__(self, default_scheme_filter: str | None = "Small Cap"):
        super().__init__(amc_code="BANDHAN", default_scheme_filter=default_scheme_filter)


class InvescoParser(GenericAMCParser):
    """Parser for Invesco Mutual Fund monthly portfolio disclosures."""

    def __init__(self, default_scheme_filter: str | None = "Small Cap"):
        super().__init__(amc_code="INVESCO", default_scheme_filter=default_scheme_filter)


class DSPParser(GenericAMCParser):
    """Parser for DSP Mutual Fund monthly portfolio disclosures."""

    def __init__(self, default_scheme_filter: str | None = "Small Cap"):
        super().__init__(amc_code="DSP", default_scheme_filter=default_scheme_filter)
