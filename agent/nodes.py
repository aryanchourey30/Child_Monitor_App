from __future__ import annotations

import logging
from typing import Any

from agent.state import MonitorState
from agent.summarizer import EventSummarizer
from rules.fall_risk import compute_fall_risk
from rules.risk_fusion import fuse_risk
from rules.state_classifier import classify_state
from vision.fire_smoke import fire_smoke_score
from vision.ingestion_risk import ingestion_risk_score
from vision.pose import estimate_pose
from vision.wet_floor import wet_floor_score

logger = logging.getLogger(__name__)


def detect_node(state: MonitorState, detector: Any, frame: Any) -> MonitorState:
    det = detector.detect(frame)
    state["baby_detected"] = bool(det["baby_detected"])
    state["baby_bbox"] = det["baby_bbox"]
    state["objects"] = det.get("objects", [])
    return state


def track_node(state: MonitorState, tracker: Any) -> MonitorState:
    tracked = tracker.update(state.get("baby_bbox"))
    state["baby_track_id"] = tracked["track_id"]
    state.setdefault("debug", {})
    state["debug"]["trajectory"] = tracked["trajectory"]
    state["debug"]["velocity"] = tracked["velocity"]
    return state


def pose_node(state: MonitorState, frame: Any) -> MonitorState:
    state["pose"] = estimate_pose(frame, state.get("baby_bbox"))
    return state


def zones_node(state: MonitorState, zone_manager: Any) -> MonitorState:
    state["zone_events"] = zone_manager.evaluate_bbox(state.get("baby_bbox"))
    return state


def safety_scores_node(state: MonitorState, frame: Any) -> MonitorState:
    zone_events = state.get("zone_events", [])
    near_edge = any(z.get("zone_type") == "edge" for z in zone_events)
    lean = float(state.get("pose", {}).get("lean_angle", 0.0))
    velocity = float(state.get("debug", {}).get("velocity", 0.0))
    fall_score, fall_reasons = compute_fall_risk(near_edge=near_edge, lean_angle=lean, velocity=velocity)
    state["fall_risk_score"] = fall_score
    state["wet_floor_score"] = wet_floor_score(frame)
    state["fire_smoke_score"] = fire_smoke_score(frame)
    state["ingestion_risk_score"] = ingestion_risk_score(frame, state.get("pose"))
    state.setdefault("debug", {})
    state["debug"]["fall_reasons"] = fall_reasons
    return state


def fuse_node(state: MonitorState, risk_cfg: dict[str, Any]) -> MonitorState:
    risk_score, level, reasons = fuse_risk(
        fall_risk_score=float(state.get("fall_risk_score", 0.0)),
        wet_floor_score=float(state.get("wet_floor_score", 0.0)),
        fire_smoke_score=float(state.get("fire_smoke_score", 0.0)),
        ingestion_risk_score=float(state.get("ingestion_risk_score", 0.0)),
        zone_events=state.get("zone_events", []),
        weights=risk_cfg,
        thresholds=risk_cfg,
    )
    state["risk_score"] = risk_score
    state["risk_level"] = level
    velocity = float(state.get("debug", {}).get("velocity", 0.0))
    state["state_label"] = classify_state(
        velocity=velocity,
        risk_score=risk_score,
        baby_detected=bool(state.get("baby_detected", False)),
    )
    reasons = reasons or ["no major contributors"]
    state["explanation"] = "; ".join(reasons)
    state["alert_needed"] = level in {"medium", "high", "critical"}
    return state


def compose_alert_node(state: MonitorState) -> MonitorState:
    state["alert_payload"] = {
        "timestamp": state.get("timestamp"),
        "severity": state.get("risk_level"),
        "event_type": "safety_risk",
        "risk_score": state.get("risk_score"),
        "caregiver_message": state.get("caregiver_message"),
        "explanation": state.get("explanation"),
        "technical_summary": state.get("technical_summary"),
        "frame_id": state.get("frame_id"),
    }
    return state


def generate_explanation_node(
    state: MonitorState,
    summarizer: EventSummarizer,
    timeout_seconds: float = 8.0,
) -> MonitorState:
    """Generate human-facing and technical explanations from deterministic state."""
    try:
        event_payload = summarizer.build_event_payload(state)
        if state.get("alert_needed"):
            summary = summarizer.summarize_event(event_payload, timeout_seconds=timeout_seconds)
        else:
            summary = EventSummarizer._fallback_summary(event_payload)
        state["explanation"] = summary["short_summary"]
        state["caregiver_message"] = summary["caregiver_message"]
        state["technical_summary"] = summary["technical_summary"]
        state["llm_used"] = bool(summary["used_llm"])
        state["llm_fallback_used"] = bool(summary["fallback_used"])
        state["llm_model"] = summary.get("model")
    except Exception as exc:  # pragma: no cover
        logger.warning("generate_explanation_node failed, preserving deterministic explanation: %s", exc)
        fallback_payload = EventSummarizer.build_event_payload(state)
        fallback = EventSummarizer._fallback_summary(fallback_payload)
        state["explanation"] = fallback["short_summary"]
        state["caregiver_message"] = fallback["caregiver_message"]
        state["technical_summary"] = fallback["technical_summary"]
        state["llm_used"] = False
        state["llm_fallback_used"] = True
        state["llm_model"] = None
    return state
