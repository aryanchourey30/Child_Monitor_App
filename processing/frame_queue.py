from __future__ import annotations

import logging
import queue
from typing import Any

logger = logging.getLogger(__name__)


class FrameQueue:
    """FIFO frame queue with configurable backpressure behavior."""

    def __init__(self, max_size: int = 200, overflow_strategy: str = "drop_oldest") -> None:
        self.max_size = max_size
        self.overflow_strategy = overflow_strategy
        self._q: queue.Queue[Any] = queue.Queue(maxsize=max_size)

    def enqueue(self, item: Any) -> bool:
        if self.overflow_strategy == "block":
            self._q.put(item, block=True)
            logger.info("Frame queue enqueue strategy=block size=%d", self._q.qsize())
            return True

        if self._q.full():
            if self.overflow_strategy == "drop_oldest":
                try:
                    _ = self._q.get_nowait()
                except queue.Empty:
                    pass
                self._q.put_nowait(item)
                logger.warning("Frame queue full; dropped oldest item size=%d", self._q.qsize())
                return True
            if self.overflow_strategy == "drop_new":
                logger.warning("Frame queue full; dropped new item")
                return False
        self._q.put_nowait(item)
        logger.info("Frame queue enqueue size=%d", self._q.qsize())
        return True

    def get(self, timeout: float | None = None) -> Any | None:
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            return None

    def qsize(self) -> int:
        return self._q.qsize()
