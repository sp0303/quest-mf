"""Spec v2 §16 composite: within-category percentiles, null rules, versioned weights."""

from __future__ import annotations

import pytest
from questmf_quant.composite import (
    SPEC16_CONFIG,
    SPEC16_MODEL,
    model_from_config,
    score_category,
)


def _fund(i: int, **over: float | None) -> dict[str, float | None]:
    """A complete feature row whose values rise with i (higher i = better)."""
    base: dict[str, float | None] = {
        "ret_1m": 0.01 * i,
        "ret_3m": 0.02 * i,
        "ret_6m": 0.03 * i,
        "beat_pct_3m": 10.0 * i,
        "beat_pct_1y": 10.0 * i,
        "median_active_3m": 0.001 * i,
        "ir_3y": 0.1 * i,
        "cagr_3y": 0.01 * i,
        "cagr_5y": 0.01 * i,
        "mdd_mag_3y": 0.5 - 0.01 * i,
        "downside_dev_3y": 0.3 - 0.01 * i,
        "beta_1y": 1.5 - 0.05 * i,
        "ter": 0.02 - 0.001 * i,
        "exit_load_days": None,
    }
    base.update(over)
    return base


def test_spec16_weights_match_spec_table():
    weights = {c.name: c.weight for c in SPEC16_MODEL.components}
    assert weights == {
        "momentum": 0.25,
        "persistence": 0.35,
        "quality": 0.15,
        "risk": 0.15,
        "cost": 0.10,
    }
    assert sum(weights.values()) == pytest.approx(1.0)
    # §16.2: SHP is a diagnostic axis, not a composite feature in V1.
    feats = {f.lstrip("-") for c in SPEC16_MODEL.components for f in c.features}
    assert "shp_3m" not in feats


def test_lower_is_better_features_are_inverted():
    funds = {i: _fund(i) for i in range(10)}
    res = score_category(funds)
    # Fund 9 has the lowest TER, lowest drawdown and best returns -> top on every component.
    assert res[9].components["cost"] > res[0].components["cost"]
    assert res[9].components["risk"] > res[0].components["risk"]
    assert res[9].composite > res[0].composite


def test_component_null_when_more_than_half_features_null():
    funds = {i: _fund(i, cagr_3y=None, cagr_5y=None) for i in range(10)}
    res = score_category(funds)
    assert all(r.components["quality"] is None for r in res.values())
    # Only one component null -> composite still computed with renormalised weights.
    assert all(r.composite is not None and not r.incomplete for r in res.values())


def test_cost_uses_ter_when_exit_load_unknown():
    funds = {i: _fund(i) for i in range(10)}  # exit_load_days is None (1 of 2 = 50%, not >50%)
    res = score_category(funds)
    assert res[9].components["cost"] is not None


def test_more_than_one_null_component_is_incomplete():
    funds = {i: _fund(i, cagr_3y=None, cagr_5y=None, ter=None) for i in range(10)}
    res = score_category(funds)
    assert all(r.composite is None and r.incomplete for r in res.values())


def test_small_peer_group_yields_null_percentiles():
    funds = {i: _fund(i) for i in range(5)}  # < 8 peers (Rule Q8)
    res = score_category(funds)
    assert all(r.small_peer_group and r.composite is None for r in res.values())


def test_composite_within_bounds_and_deterministic():
    funds = {i: _fund(i) for i in range(12)}
    a, b = score_category(funds), score_category(funds)
    assert {k: v.composite for k, v in a.items()} == {k: v.composite for k, v in b.items()}
    assert all(0.0 <= v.composite <= 100.0 for v in a.values())


def test_model_from_config_requires_components():
    assert model_from_config("x", SPEC16_CONFIG).min_peers == 8
    with pytest.raises(ValueError):
        model_from_config("legacy", {"weights": {"momentum": 1.0}})
