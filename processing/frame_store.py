from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class FrameStorageService:
    """Persist incoming frames and enforce rolling retention of latest N files."""

    def __init__(self, storage_dir: str, max_files: int = 240) -> None:
        self.storage_dir = Path(storage_dir)
        self.max_files = max_files
        self._lock = threading.Lock()
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save_frame(self, frame: np.ndarray, frame_id: str, timestamp: str | None = None) -> str:
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        safe_ts = (
            ts.replace("-", "")
            .replace(":", "")
            .replace("+00:00", "Z")
            .replace(".", "_")
        )
        filename = f"{safe_ts}_{frame_id}.jpg"
        path = self.storage_dir / filename
        with self._lock:
            ok = cv2.imwrite(str(path), frame)
            if not ok:
                raise RuntimeError(f"Failed to write frame: {path}")
            logger.info("Frame saved path=%s", path)
            self._apply_retention_unlocked()
        return str(path)

    def list_files(self) -> list[Path]:
        return sorted(self.storage_dir.glob("*.jpg"), key=lambda p: p.name)

    def _apply_retention_unlocked(self) -> None:
        files = self.list_files()
        if len(files) <= self.max_files:
            return
        overflow = len(files) - self.max_files
        to_delete = files[:overflow]
        for file_path in to_delete:
            try:
                if file_path.parent.resolve() != self.storage_dir.resolve():
                    logger.warning("Skipped delete outside storage dir path=%s", file_path)
                    continue
                file_path.unlink(missing_ok=True)
            except Exception as exc:
                logger.warning("Failed deleting old frame file=%s err=%s", file_path, exc)
        logger.info("Retention applied deleted=%d kept=%d", len(to_delete), self.max_files)
