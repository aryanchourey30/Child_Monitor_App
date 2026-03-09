from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

import paho.mqtt.client as mqtt

from processing.frame_queue import FrameQueue

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class FramePacket:
    """Normalized frame packet built from meta + jpeg topics."""

    frame_id: str
    timestamp: str
    meta: dict[str, Any]
    jpeg_bytes: bytes
    received_at: float


class MQTTFrameSubscriber:
    """Subscribes to frame topics and pushes packets to processing queue."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        topic_meta: str,
        topic_jpeg: str,
        frame_queue: FrameQueue,
        username: str = "",
        password: str = "",
        keepalive: int = 60,
        pair_ttl_seconds: float = 60.0,
        max_pending_pairs: int = 500,
    ) -> None:
        self.host = host
        self.port = port
        self.topic_meta = topic_meta
        self.topic_jpeg = topic_jpeg
        self.frame_queue = frame_queue
        self.keepalive = keepalive
        self.pair_ttl_seconds = pair_ttl_seconds
        self.max_pending_pairs = max_pending_pairs
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._pending_meta: dict[str, tuple[dict[str, Any], float]] = {}
        self._pending_jpeg: dict[str, tuple[bytes, float]] = {}
        self._recent_processed: dict[str, float] = {}

        self.client = mqtt.Client()
        if username:
            self.client.username_pw_set(username=username, password=password or None)
        self.client.enable_logger(logger)
        self.client.reconnect_delay_set(min_delay=1, max_delay=15)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

    def start(self) -> None:
        logger.info("Connecting MQTT subscriber host=%s port=%s", self.host, self.port)
        self.client.connect(self.host, self.port, self.keepalive)
        self.client.loop_start()

    def stop(self) -> None:
        self._stop_event.set()
        self.client.loop_stop()
        try:
            self.client.disconnect()
        except Exception:
            pass

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Any, rc: int) -> None:
        if rc != 0:
            logger.error("MQTT connection failed rc=%s", rc)
            return
        logger.info("MQTT connected; subscribing topics.")
        client.subscribe(self.topic_meta)
        client.subscribe(self.topic_jpeg)

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, rc: int) -> None:
        if rc == 0:
            logger.info("MQTT disconnected cleanly.")
        else:
            logger.warning("MQTT disconnected unexpectedly rc=%s. Reconnect will be attempted.", rc)

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        if self._stop_event.is_set():
            return
        now = time.time()
        topic = msg.topic
        with self._lock:
            self._evict_stale(now)
            try:
                if topic == self.topic_meta:
                    meta = json.loads(msg.payload.decode("utf-8"))
                    if not isinstance(meta, dict):
                        logger.warning("Malformed meta payload: not an object")
                        return
                    frame_id = str(meta.get("frame_id", "")).strip()
                    if not frame_id:
                        logger.warning("Malformed meta payload: missing frame_id")
                        return
                    self._pending_meta[frame_id] = (meta, now)
                    self._try_emit(frame_id, now)
                    return

                if topic == self.topic_jpeg:
                    frame_id = str(getattr(msg, "properties", None) and getattr(msg.properties, "CorrelationData", "") or "")
                    # If correlation data is missing, map to latest unmatched meta by arrival order fallback.
                    if not frame_id:
                        frame_id = self._infer_latest_unpaired_meta_id()
                    if not frame_id:
                        logger.warning("JPEG payload received without correlatable frame_id")
                        return
                    payload = bytes(msg.payload)
                    if not payload:
                        logger.warning("Empty JPEG payload frame_id=%s", frame_id)
                        return
                    self._pending_jpeg[frame_id] = (payload, now)
                    self._try_emit(frame_id, now)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON in MQTT meta topic")
            except Exception as exc:
                logger.warning("MQTT callback error topic=%s err=%s", topic, exc)

    def _infer_latest_unpaired_meta_id(self) -> str:
        if not self._pending_meta:
            return ""
        # latest by timestamp in pending meta
        return sorted(self._pending_meta.items(), key=lambda it: it[1][1], reverse=True)[0][0]

    def _try_emit(self, frame_id: str, now: float) -> None:
        if frame_id in self._recent_processed:
            return
        meta_item = self._pending_meta.get(frame_id)
        jpeg_item = self._pending_jpeg.get(frame_id)
        if not meta_item or not jpeg_item:
            return
        meta, _ = meta_item
        jpeg_bytes, _ = jpeg_item
        packet = FramePacket(
            frame_id=frame_id,
            timestamp=str(meta.get("timestamp", "")),
            meta=meta,
            jpeg_bytes=jpeg_bytes,
            received_at=now,
        )
        pushed = self.frame_queue.enqueue(packet)
        if pushed:
            logger.info("Frame packet queued frame_id=%s queue_size=%d", frame_id, self.frame_queue.qsize())
            self._recent_processed[frame_id] = now
        self._pending_meta.pop(frame_id, None)
        self._pending_jpeg.pop(frame_id, None)

    def _evict_stale(self, now: float) -> None:
        cutoff = now - self.pair_ttl_seconds
        self._pending_meta = {k: v for k, v in self._pending_meta.items() if v[1] >= cutoff}
        self._pending_jpeg = {k: v for k, v in self._pending_jpeg.items() if v[1] >= cutoff}
        self._recent_processed = {k: v for k, v in self._recent_processed.items() if v >= cutoff}

        # Bound pending size to avoid memory growth on malformed streams.
        if len(self._pending_meta) > self.max_pending_pairs:
            for key in sorted(self._pending_meta, key=lambda x: self._pending_meta[x][1])[: len(self._pending_meta) - self.max_pending_pairs]:
                self._pending_meta.pop(key, None)
        if len(self._pending_jpeg) > self.max_pending_pairs:
            for key in sorted(self._pending_jpeg, key=lambda x: self._pending_jpeg[x][1])[: len(self._pending_jpeg) - self.max_pending_pairs]:
                self._pending_jpeg.pop(key, None)
