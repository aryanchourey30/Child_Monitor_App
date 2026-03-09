from __future__ import annotations

from typing import Any

import numpy as np

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None


def wet_floor_score(frame: Any, roi: tuple[int, int, int, int] | None = None) -> float:
    if cv2 is None or frame is None:
        return 0.0
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = roi or (0, int(h * 0.5), w, h)
    patch = frame[y1:y2, x1:x2]
    if patch.size == 0:
        return 0.0
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    bright_pixels = np.mean(gray > 220)
    return float(min(1.0, bright_pixels * 2.5))
