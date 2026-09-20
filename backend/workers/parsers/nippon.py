"""Nippon India Mutual Fund monthly portfolio disclosure parser.

Conforms to BaseAMCParser contract H1–H8.
Parses official Nippon India portfolio disclosure workbooks (.xlsx).
"""

from __future__ import annotations

from workers.parsers.generic_amc import GenericAMCParser


class NipponIndiaParser(GenericAMCParser):
    """Parser for Nippon India Mutual Fund monthly portfolio disclosures."""

    def __init__(self, default_scheme_filter: str | None = "Small Cap"):
        super().__init__(amc_code="NIPPON", default_scheme_filter=default_scheme_filter)
