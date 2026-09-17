"""Composite scoring engine and 2x2 quadrant assignment.

Rules:
- Q13: Model weights and thresholds live in versioned config, never hardcoded.
- Q12: Insufficient history -> INSUFFICIENT_HISTORY, never zero.
- Spec v2 §16: 2x2 matrix quadrants (Peer vs Own-history SHP).
"""

from __future__ import annotations

from dataclasses import dataclass


class Confidence(int):
    INSUFFICIENT = 0
    LOW = 1
    OK = 2


@dataclass(frozen=True)
class ModelConfig:
    version: str
    weights: dict[
        str, float
    ]  # e.g. {"momentum": 0.35, "persistence": 0.25, "quality": 0.20, "risk": 0.10, "cost": 0.10}
    min_obs_required: int = 252  # 1 year minimum for low confidence, 756 (3Y) for full confidence


DEFAULT_BASELINE_MODEL = ModelConfig(
    version="v1_baseline",
    weights={
        "momentum": 0.35,
        "persistence": 0.25,
        "quality": 0.20,
        "risk": 0.10,
        "cost": 0.10,
    },
    min_obs_required=252,
)


def assign_quadrant(peer_pct: float | None, shp: float | None) -> int | None:
    """Assign quadrant in the 2x2 matrix:

    X = Peer Percentile (0..100, threshold 50)
    Y = Self-History Percentile SHP (0..100, threshold 50)

    Quadrants:
    - Quadrant 1: High Peer (>=50), High SHP (>=50) [Strong now, strong historically]
    - Quadrant 2: Low Peer (<50),  High SHP (>=50) [Lagging peers, but high vs own history]
    - Quadrant 3: Low Peer (<50),  Low SHP (<50)  [Lagging peers and lagging own history]
    - Quadrant 4: High Peer (>=50), Low SHP (<50)  [Beating peers, but low vs own history]
    """
    if peer_pct is None or shp is None:
        return None

    high_peer = peer_pct >= 50.0
    high_shp = shp >= 50.0

    if high_peer and high_shp:
        return 1
    elif not high_peer and high_shp:
        return 2
    elif not high_peer and not high_shp:
        return 3
    else:
        return 4


def compute_composite_score(
    factor_scores: dict[str, float | None],
    config: ModelConfig,
    obs_count: int,
) -> tuple[float | None, int]:
    """Compute weighted composite score and confidence level.

    Returns: (composite_score, confidence)
    If obs_count < 252, returns (None, Confidence.INSUFFICIENT) per Rule Q12.
    """
    if obs_count < config.min_obs_required:
        return None, Confidence.INSUFFICIENT

    confidence = Confidence.OK if obs_count >= (config.min_obs_required * 3) else Confidence.LOW

    total_weight = 0.0
    weighted_sum = 0.0

    for factor, weight in config.weights.items():
        val = factor_scores.get(factor)
        if val is not None:
            weighted_sum += val * weight
            total_weight += weight

    if total_weight == 0.0:
        return None, Confidence.INSUFFICIENT

    # Normalize by active weights if some factors are missing
    composite = weighted_sum / total_weight
    return round(composite, 2), confidence
