from __future__ import annotations

from typing import Any, TypedDict


class MonitorState(TypedDict, total=False):
    frame_id: str
    timestamp: str
    source: str
    frame_path: str
    baby_detected: bool
    baby_bbox: dict[str, Any]
    baby_track_id: int
    pose: dict[str, Any]
    objects: list[dict[str, Any]]
    zone_events: list[dict[str, Any]]
    fall_risk_score: float
    wet_floor_score: float
    fire_smoke_score: float
    ingestion_risk_score: float
    state_label: str
    risk_score: float
    risk_level: str
    explanation: str
    caregiver_message: str
    technical_summary: str
    llm_used: bool
    llm_fallback_used: bool
    llm_model: str | None
    alert_needed: bool
    alert_payload: dict[str, Any]
    debug: dict[str, Any]
