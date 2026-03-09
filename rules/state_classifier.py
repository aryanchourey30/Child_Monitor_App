from __future__ import annotations


def classify_state(*, velocity: float, risk_score: float, baby_detected: bool) -> str:
    if not baby_detected:
        return "unknown"
    if risk_score >= 0.75:
        return "unsafe_exploration"
    if velocity < 2:
        return "sleeping"
    if velocity < 8:
        return "calm"
    if velocity < 18:
        return "playful"
    return "restless"
