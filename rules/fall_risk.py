from __future__ import annotations


def compute_fall_risk(
    *,
    near_edge: bool,
    lean_angle: float,
    velocity: float,
    climb_like: bool = False,
) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 0.0
    if near_edge:
        score += 0.45
        reasons.append("near edge zone")
    if lean_angle > 12:
        score += 0.25
        reasons.append("forward lean elevated")
    if velocity > 25:
        score += 0.2
        reasons.append("rapid body shift")
    if climb_like:
        score += 0.2
        reasons.append("climb-like behavior")
    return min(1.0, score), reasons
