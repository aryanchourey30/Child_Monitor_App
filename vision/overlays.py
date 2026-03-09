from __future__ import annotations

from typing import Any

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None


def draw_bbox(frame: Any, bbox: dict[str, int], label: str = "baby") -> Any:
    if cv2 is None or not bbox:
        return frame
    cv2.rectangle(frame, (bbox["x1"], bbox["y1"]), (bbox["x2"], bbox["y2"]), (0, 255, 0), 2)
    cv2.putText(frame, label, (bbox["x1"], max(0, bbox["y1"] - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    return frame
