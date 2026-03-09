from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None


def save_snapshot(frame: Any, snapshots_dir: str | Path, event_id: str) -> str | None:
    if cv2 is None or frame is None:
        return None
    out_dir = Path(snapshots_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{event_id}.jpg"
    cv2.imwrite(str(out_path), frame)
    return str(out_path)
