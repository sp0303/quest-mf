"""Screener search: every word must match fund name or AMC; LIKE wildcards are literal."""

from __future__ import annotations

from app.api.screener import search_patterns


def test_words_become_contains_patterns():
    assert search_patterns("  axis   small ") == ["%axis%", "%small%"]


def test_empty_query_matches_everything():
    assert search_patterns(None) == [] and search_patterns("   ") == []


def test_like_wildcards_are_escaped():
    assert search_patterns("100%_x") == ["%100\\%\\_x%"]


def test_word_count_is_capped():
    assert len(search_patterns("a b c d e f g h i j")) == 8
