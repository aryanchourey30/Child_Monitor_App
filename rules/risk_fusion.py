from __future__ import annotations

from typing import Any


def fuse_risk(
    *,
    fall_risk_score: float,
    wet_floor_score: float,
    fire_smoke_score: float,
    ingestion_risk_score: float,
    zone_events: list[dict[str, Any]],
    weights: dict[str, float],
    thresholds: dict[str, float],
) -> tuple[float, str, list[str]]:
    zone_score = max((float(z.get("severity_weight", 0.0)) for z in zone_events), default=0.0)
    score = (
        fall_risk_score * float(weights.get("fall_weight", 0.35))
        + wet_floor_score * float(weights.get("wet_floor_weight", 0.2))
        + fire_smoke_score * float(weights.get("fire_smoke_weight", 0.35))
        + ingestion_risk_score * float(weights.get("ingestion_weight", 0.1))
        + zone_score * float(weights.get("zone_weight", 0.25))
    )
    score = max(0.0, min(1.0, score))
    if fire_smoke_score >= 0.8:
        score = max(score, 0.95)
    medium = float(thresholds.get("medium_threshold", 0.4))
    high = float(thresholds.get("high_threshold", 0.7))
    critical = float(thresholds.get("critical_threshold", 0.9))
    if score >= critical:
        level = "critical"
    elif score >= high:
        level = "high"
    elif score >= medium:
        level = "medium"
    else:
        level = "low"
    reasons: list[str] = []
    if fall_risk_score > 0.4:
        reasons.append("fall risk elevated")
    if wet_floor_score > 0.4:
        reasons.append("possible slippery floor")
    if fire_smoke_score > 0.4:
        reasons.append("fire/smoke visual signal")
    if ingestion_risk_score > 0.4:
        reasons.append("possible ingestion behavior")
    if zone_events:
        reasons.append(f"in restricted zone: {zone_events[0].get('zone_name')}")
    return score, level, reasons
