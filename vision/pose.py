from __future__ import annotations

from typing import Any


def estimate_pose(frame: Any, bbox: dict | None) -> dict:
    # Placeholder posture cues for MVP plumbing.
    if not bbox:
        return {}
    height = max(1, bbox["y2"] - bbox["y1"])
    width = max(1, bbox["x2"] - bbox["x1"])
    aspect = height / width
    posture = "standing" if aspect > 1.3 else "sitting"
    return {
        "posture": posture,
        "lean_angle": 8.0 if posture == "standing" else 2.0,
        "center": {"x": (bbox["x1"] + bbox["x2"]) / 2, "y": (bbox["y1"] + bbox["y2"]) / 2},
    }
