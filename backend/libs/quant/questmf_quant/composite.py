"""Spec v2 §16 composite: within-category percentiles -> components -> composite.

Rules:
- §16.1: every feature is a within-category, point-in-time peer percentile (0-100).
  "Lower is better" features are inverted (100 - pct). A component is the mean of
  its non-null feature percentiles, and is null when more than 50% of its features
  are null. The composite is the weighted mean of non-null components (weights
  renormalised); if more than `max_null_components` components are null the
  composite is null and the fund is INCOMPLETE.
- Q8: peer percentiles need >= min_peers funds, otherwise null.
- Q13: components, features, weights and thresholds come from versioned config.
- Q12: missing inputs stay null, never zero.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from questmf_quant.percentile import peer_percentiles

# Bit flags stored in scoring.screener_snapshot.flags (spec §16.4).
FLAG_SMALL_PEER_GROUP = 1
FLAG_INCOMPLETE = 2
FLAG_SHORT_HISTORY = 4  # < 3Y of history: 3Y features (IR, MDD, CAGR) are null
FLAG_INVESTABILITY_UNVERIFIED = 8  # no subscription-status source yet (spec §7.4)
FLAG_NO_BENCHMARK = 16  # benchmark-relative features unavailable


@dataclass(frozen=True)
class ComponentSpec:
    name: str
    weight: float
    # A leading "-" marks a lower-is-better feature (inverted percentile).
    features: tuple[str, ...]


@dataclass(frozen=True)
class CompositeModel:
    version: str
    components: tuple[ComponentSpec, ...]
    min_peers: int = 8
    max_null_components: int = 1
    min_obs_required: int = 252


@dataclass(frozen=True)
class CompositeResult:
    composite: float | None
    components: dict[str, float | None] = field(default_factory=dict)
    incomplete: bool = False
    small_peer_group: bool = False


SPEC16_CONFIG: dict = {
    "components": {
        "momentum": {"weight": 0.25, "features": ["ret_1m", "ret_3m", "ret_6m"]},
        "persistence": {
            "weight": 0.35,
            "features": ["beat_pct_3m", "beat_pct_1y", "median_active_3m", "ir_3y"],
        },
        "quality": {"weight": 0.15, "features": ["cagr_3y", "cagr_5y"]},
        "risk": {"weight": 0.15, "features": ["-mdd_mag_3y", "-downside_dev_3y", "-beta_1y"]},
        "cost": {"weight": 0.10, "features": ["-ter", "-exit_load_days"]},
    },
    "min_peers": 8,
    "max_null_components": 1,
    "min_obs_required": 252,
}
SPEC16_VERSION = "v2_spec16"


def model_from_config(version: str, cfg: Mapping) -> CompositeModel:
    """Build a CompositeModel from a scoring.model_versions config document."""
    comps = cfg.get("components")
    if not comps:
        raise ValueError(f"model {version} has no 'components' section")
    return CompositeModel(
        version=version,
        components=tuple(
            ComponentSpec(name=n, weight=float(c["weight"]), features=tuple(c["features"]))
            for n, c in comps.items()
        ),
        min_peers=int(cfg.get("min_peers", 8)),
        max_null_components=int(cfg.get("max_null_components", 1)),
        min_obs_required=int(cfg.get("min_obs_required", 252)),
    )


SPEC16_MODEL = model_from_config(SPEC16_VERSION, SPEC16_CONFIG)


def _feature_percentiles(
    features_by_pid: Mapping[int, Mapping[str, float | None]],
    model: CompositeModel,
) -> dict[str, dict[int, float | None]]:
    out: dict[str, dict[int, float | None]] = {}
    for comp in model.components:
        for feat in comp.features:
            invert = feat.startswith("-")
            key = feat.lstrip("-")
            raw = {pid: f.get(key) for pid, f in features_by_pid.items()}
            pct = peer_percentiles(raw, min_peers=model.min_peers)  # type: ignore[arg-type]
            out[feat] = {
                pid: (None if v is None else (100.0 - v if invert else v)) for pid, v in pct.items()
            }
    return out


def _component_score(pcts: list[float | None]) -> float | None:
    vals = [p for p in pcts if p is not None]
    if not pcts or len(vals) * 2 < len(pcts):  # more than 50% null
        return None
    return sum(vals) / len(vals)


def score_category(
    features_by_pid: Mapping[int, Mapping[str, float | None]],
    model: CompositeModel = SPEC16_MODEL,
) -> dict[int, CompositeResult]:
    """Score one category's funds (one row per portfolio_id, Rule Q8)."""
    small = len(features_by_pid) < model.min_peers
    pcts = _feature_percentiles(features_by_pid, model)
    results: dict[int, CompositeResult] = {}
    for pid in features_by_pid:
        comps = {
            c.name: _component_score([pcts[f][pid] for f in c.features]) for c in model.components
        }
        nulls = sum(1 for v in comps.values() if v is None)
        active = [(c.weight, comps[c.name]) for c in model.components if comps[c.name] is not None]
        total_w = sum(w for w, _ in active)
        incomplete = nulls > model.max_null_components or total_w == 0.0
        composite = None if incomplete else round(sum(w * v for w, v in active) / total_w, 2)
        results[pid] = CompositeResult(
            composite=composite, components=comps, incomplete=incomplete, small_peer_group=small
        )
    return results
