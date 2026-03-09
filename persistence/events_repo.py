from __future__ import annotations

from typing import Any

from persistence.db import EventRepository


def build_event_record(
    *,
    event_id: str,
    timestamp: str,
    event_type: str,
    risk_score: float,
    risk_level: str,
    state_label: str,
    explanation: str,
    caregiver_message: str | None,
    technical_summary: str | None,
    llm_used: bool,
    llm_fallback_used: bool,
    llm_model: str | None,
    snapshot_path: str | None,
    detectors: dict[str, Any],
    notification_sent: bool,
) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "timestamp": timestamp,
        "event_type": event_type,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "state_label": state_label,
        "explanation": explanation,
        "caregiver_message": caregiver_message,
        "technical_summary": technical_summary,
        "llm_used": llm_used,
        "llm_fallback_used": llm_fallback_used,
        "llm_model": llm_model,
        "snapshot_path": snapshot_path,
        "detectors": detectors,
        "notification_sent": notification_sent,
    }


__all__ = ["EventRepository", "build_event_record"]
