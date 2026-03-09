from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None


@dataclass(slots=True)
class FramePacket:
    frame_id: str
    timestamp: str
    frame: Any


class CameraReader:
    def __init__(
        self,
        source: int | str = 0,
        width: int | None = None,
        height: int | None = None,
        reconnect_attempts: int = 5,
        reconnect_delay_sec: float = 1.0,
    ) -> None:
        if cv2 is None:
            raise RuntimeError("opencv-python is required for CameraReader.")
        self.source = self._normalize_source(source)
        self.width = width
        self.height = height
        self.reconnect_attempts = reconnect_attempts
        self.reconnect_delay_sec = reconnect_delay_sec
        self.cap: Any = None
        self._frame_counter = 0

    @staticmethod
    def _normalize_source(source: int | str) -> int | str:
        if isinstance(source, int):
            return source
        candidate = source.strip()
        if candidate.isdigit():
            return int(candidate)
        return candidate

    def open(self) -> None:
        self.cap = cv2.VideoCapture(self.source)
        if self.width:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        if self.height:
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        if not self.cap.isOpened():
            raise RuntimeError(f"Unable to open camera source: {self.source}")

    def reconnect(self) -> None:
        for _ in range(self.reconnect_attempts):
            self.close()
            time.sleep(self.reconnect_delay_sec)
            try:
                self.open()
                return
            except Exception:
                continue
        raise RuntimeError("Camera reconnect failed after retries.")

    def read(self) -> FramePacket | None:
        if self.cap is None or not self.cap.isOpened():
            self.reconnect()
        ok, frame = self.cap.read()
        if not ok or frame is None:
            return None
        self._frame_counter += 1
        ts = datetime.now(timezone.utc).isoformat()
        frame_id = f"frm_{self._frame_counter:08d}"
        return FramePacket(frame_id=frame_id, timestamp=ts, frame=frame)

    def close(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None
