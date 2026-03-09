from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Deque


@dataclass(slots=True)
class TrackState:
    track_id: int = 1
    history: Deque[tuple[float, float]] = field(default_factory=lambda: deque(maxlen=30))

    def update(self, bbox: dict[str, int] | None) -> dict:
        if not bbox:
            return {"track_id": self.track_id, "position": None, "velocity": 0.0, "trajectory": list(self.history)}
        cx = (bbox["x1"] + bbox["x2"]) / 2.0
        cy = (bbox["y1"] + bbox["y2"]) / 2.0
        velocity = 0.0
        if self.history:
            px, py = self.history[-1]
            velocity = math.dist((px, py), (cx, cy))
        self.history.append((cx, cy))
        return {
            "track_id": self.track_id,
            "position": {"x": cx, "y": cy},
            "velocity": velocity,
            "trajectory": list(self.history),
        }
