from questmf_quant.scoring import (
    DEFAULT_BASELINE_MODEL,
    Confidence,
    assign_quadrant,
    compute_composite_score,
)


def test_q12_insufficient_history():
    """Rule Q12: Insufficient history -> INSUFFICIENT_HISTORY, never zero."""
    factor_scores = {
        "momentum": 85.0,
        "persistence": 70.0,
        "quality": 80.0,
        "risk": 60.0,
        "cost": 90.0,
    }

    # Only 100 days of history (< 252 days required)
    score, conf = compute_composite_score(factor_scores, DEFAULT_BASELINE_MODEL, obs_count=100)
    assert conf == Confidence.INSUFFICIENT
    assert score is None  # Never returns 0.0 for insufficient history!


def test_scoring_and_quadrants():
    factor_scores = {
        "momentum": 80.0,
        "persistence": 70.0,
        "quality": 80.0,
        "risk": 60.0,
        "cost": 90.0,
    }
    # 800 days of history (>= 756 days -> OK)
    score, conf = compute_composite_score(factor_scores, DEFAULT_BASELINE_MODEL, obs_count=800)
    assert conf == Confidence.OK
    assert score is not None
    assert 70.0 <= score <= 85.0

    # Test 2x2 quadrants
    assert assign_quadrant(peer_pct=75.0, shp=60.0) == 1  # High peer, High SHP
    assert assign_quadrant(peer_pct=30.0, shp=60.0) == 2  # Low peer, High SHP
    assert assign_quadrant(peer_pct=30.0, shp=40.0) == 3  # Low peer, Low SHP
    assert assign_quadrant(peer_pct=75.0, shp=40.0) == 4  # High peer, Low SHP
