from rules.risk_fusion import fuse_risk


def test_risk_fusion_levels() -> None:
    weights = {
        "fall_weight": 0.35,
        "wet_floor_weight": 0.2,
        "fire_smoke_weight": 0.35,
        "ingestion_weight": 0.1,
        "zone_weight": 0.25,
        "medium_threshold": 0.4,
        "high_threshold": 0.7,
        "critical_threshold": 0.9,
    }
    score, level, _ = fuse_risk(
        fall_risk_score=0.8,
        wet_floor_score=0.0,
        fire_smoke_score=0.0,
        ingestion_risk_score=0.0,
        zone_events=[{"severity_weight": 0.9, "zone_name": "bed_edge"}],
        weights=weights,
        thresholds=weights,
    )
    assert score > 0.4
    assert level in {"medium", "high", "critical"}
