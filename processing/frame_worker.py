from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Callable

import cv2
import numpy as np

from agent.frame_llm_processor import FrameLLMProcessor
from processing.frame_queue import FrameQueue
from processing.frame_store import FrameStorageService
from transport.mqtt_subscriber import FramePacket
from vision.model_runner import ModelRunner

logger = logging.getLogger(__name__)


class FrameWorker:
    """Sequential frame worker: decode -> save -> model -> LLM -> persist callback."""

    def __init__(
        self,
        *,
        frame_queue: FrameQueue,
        frame_store: FrameStorageService,
        model_runner: ModelRunner,
        llm_processor: FrameLLMProcessor,
        on_result: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.frame_queue = frame_queue
        self.frame_store = frame_store
        self.model_runner = model_runner
        self.llm_processor = llm_processor
        self.on_result = on_result
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="frame-worker")
        self._thread.start()
        logger.info("Frame worker started.")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        logger.info("Frame worker stopped.")

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            packet = self.frame_queue.get(timeout=0.5)
            if packet is None:
                continue
            try:
                result = self._process_packet(packet)
                if self.on_result is not None:
                    self.on_result(result)
            except Exception as exc:
                logger.warning("Frame worker packet failure frame_id=%s err=%s", getattr(packet, "frame_id", "?"), exc)

    def _process_packet(self, packet: FramePacket) -> dict[str, Any]:
        logger.info("Frame worker start frame_id=%s", packet.frame_id)
        frame = self._decode_jpeg(packet.jpeg_bytes)
        if frame is None:
            raise RuntimeError("JPEG decode failed")
        timestamp = packet.timestamp or datetime.now(timezone.utc).isoformat()
        frame_path = self.frame_store.save_frame(frame, frame_id=packet.frame_id, timestamp=timestamp)
        model_result = self.model_runner.run(frame=frame, frame_id=packet.frame_id, timestamp=timestamp)
        llm_result = self.llm_processor.process_frame(
            frame_path=frame_path,
            frame_meta=packet.meta,
            model_result=model_result,
        )
        out = {
            "frame_id": packet.frame_id,
            "timestamp": timestamp,
            "frame_path": frame_path,
            "meta": packet.meta,
            "model_result": model_result,
            "llm_result": llm_result,
        }
        logger.info("Frame worker completed frame_id=%s", packet.frame_id)
        return out

    @staticmethod
    def _decode_jpeg(jpeg_bytes: bytes) -> Any | None:
        arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        if arr.size == 0:
            return None
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
