from __future__ import annotations

import logging
import threading
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class FrameStore:
    """Store incoming frames into a single rolling batch directory."""

    def __init__(self, storage_dir: str, max_frames: int = 240) -> None:
        self.storage_dir = Path(storage_dir)
        self.max_frames = max_frames
        self._lock = threading.Lock()
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._counter = self.get_current_frame_count()

    def save_frame(self, frame: np.ndarray, timestamp: str | None = None) -> str:
        """Save frame to disk and return saved path.

        Batch behavior:
        - Keep files from 1..max_frames
        - Before saving the next frame after max_frames, clear the whole batch
        - Restart numbering from 1
        """
        _ = timestamp
        with self._lock:
            if self._counter >= self.max_frames:
                logger.info("Frame batch reached %d; resetting batch.", self.max_frames)
                self._reset_batch_unlocked()
            self._counter += 1
            filename = f"frame_{self._counter:06d}.jpg"
            out_path = self.storage_dir / filename
            ok = cv2.imwrite(str(out_path), frame)
            if not ok:
                self._counter -= 1
                raise RuntimeError(f"Failed to write frame image: {out_path}")
            logger.info("Frame saved path=%s count=%d", out_path, self._counter)
            return str(out_path)

    def get_current_frame_count(self) -> int:
        """Return count of saved frame files in current batch folder."""
        files = list(self.storage_dir.glob("frame_*.jpg"))
        return len(files)

    def reset_batch(self) -> None:
        """Delete all files in the active batch and reset numbering."""
        with self._lock:
            self._reset_batch_unlocked()

    def _reset_batch_unlocked(self) -> None:
        files = list(self.storage_dir.glob("frame_*.jpg"))
        failed = 0
        for f in files:
            try:
                f.unlink(missing_ok=True)
            except Exception as exc:  # pragma: no cover
                failed += 1
                logger.warning("Failed deleting frame file=%s err=%s", f, exc)
        if failed == 0:
            self._counter = 0
            logger.info("Frame batch reset complete; deleted=%d", len(files))
        else:
            logger.warning("Frame batch reset incomplete; failed_deletes=%d", failed)

    def list_saved_frames(self) -> list[str]:
        """List saved frame files in lexical order."""
        files = sorted(self.storage_dir.glob("frame_*.jpg"))
        return [str(f) for f in files]
