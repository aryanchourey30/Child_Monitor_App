from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ModelRunner:
    """Per-frame model interface with placeholder fallback."""

    def __init__(self, graph: Any | None = None, detector: Any | None = None) -> None:
        self.graph = graph
        self.detector = detector

    def run(self, frame: Any, frame_id: str, timestamp: str) -> dict[str, Any]:
        if self.graph is not None and self.detector is not None:
            try:
                state = self.graph.run(
                    detector=self.detector,
                    frame=frame,
                    frame_id=frame_id,
                    timestamp=timestamp,
                )
                return {
                    "subject_detected": bool(state.get("baby_detected", False)),
                    "state_label": str(state.get("state_label", "unknown")),
                    "risk_level": str(state.get("risk_level", "low")),
                    "risk_score": float(state.get("risk_score", 0.0)),
                    "events": state.get("zone_events", []),
                    "raw_state": state,
                }
            except Exception as exc:
                logger.warning("Model runner graph path failed frame_id=%s err=%s", frame_id, exc)
        # Placeholder fallback.
        return {
            "subject_detected": True,
            "state_label": "calm",
            "risk_level": "low",
            "risk_score": 0.18,
            "events": [],
            "raw_state": {},
        }
