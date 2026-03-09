from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable

import cv2
import numpy as np
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class MQTTTopics:
    frame_jpeg: str
    frame_meta: str
    heartbeat: str
    video_meta: str


class MQTTFrameSubscriber:
    """MQTT subscriber that pairs metadata + raw JPEG messages and emits decoded frames."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        topics: MQTTTopics,
        on_frame: Callable[[dict[str, Any], Any], None],
        on_heartbeat: Callable[[dict[str, Any]], None] | None = None,
        on_video_meta: Callable[[dict[str, Any]], None] | None = None,
        username: str | None = None,
        password: str | None = None,
        keepalive: int = 60,
        pair_ttl_seconds: float = 3.0,
        max_queue_size: int = 200,
    ) -> None:
        self.host = host
        self.port = port
        self.topics = topics
        self.on_frame = on_frame
        self.on_heartbeat = on_heartbeat
        self.on_video_meta = on_video_meta
        self.keepalive = keepalive
        self.pair_ttl_seconds = pair_ttl_seconds
        self.max_queue_size = max_queue_size
        self._meta_queue: deque[tuple[dict[str, Any], float]] = deque()
        self._jpeg_queue: deque[tuple[bytes, float]] = deque()
        self._processed_frame_ids: deque[str] = deque()
        self._processed_maxlen = 3000
        self._processed_set: set[str] = set()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

        self.client = mqtt.Client()
        if username:
            self.client.username_pw_set(username=username, password=password)
        self.client.enable_logger(logger)
        self.client.reconnect_delay_set(min_delay=1, max_delay=15)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def start(self) -> None:
        logger.info("Connecting to MQTT broker %s:%s", self.host, self.port)
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
            logger.error("MQTT connect failed rc=%s", rc)
            return
        logger.info("MQTT connected. Subscribing to topics.")
        client.subscribe(self.topics.frame_jpeg)
        client.subscribe(self.topics.frame_meta)
        client.subscribe(self.topics.heartbeat)
        client.subscribe(self.topics.video_meta)

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, rc: int) -> None:
        if rc == 0:
            logger.info("MQTT disconnected cleanly.")
        else:
            logger.warning("MQTT disconnected unexpectedly rc=%s; auto-reconnect active.", rc)

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        if self._stop_event.is_set():
            return
        topic = msg.topic
        now = time.time()
        try:
            if topic == self.topics.frame_meta:
                meta = json.loads(msg.payload.decode("utf-8"))
                if not isinstance(meta, dict):
                    return
                frame_id = str(meta.get("frame_id", ""))
                if not frame_id or self._is_duplicate(frame_id):
                    return
                with self._lock:
                    self._meta_queue.append((meta, now))
                    self._trim_queues()
                    self._drain_pairs_locked()
                return

            if topic == self.topics.frame_jpeg:
                payload = bytes(msg.payload)
                if not payload:
                    return
                with self._lock:
                    self._jpeg_queue.append((payload, now))
                    self._trim_queues()
                    self._drain_pairs_locked()
                return

            if topic == self.topics.heartbeat and self.on_heartbeat:
                heartbeat = json.loads(msg.payload.decode("utf-8"))
                if isinstance(heartbeat, dict):
                    self.on_heartbeat(heartbeat)
                return

            if topic == self.topics.video_meta and self.on_video_meta:
                video_meta = json.loads(msg.payload.decode("utf-8"))
                if isinstance(video_meta, dict):
                    self.on_video_meta(video_meta)
                return
        except json.JSONDecodeError:
            logger.warning("Invalid JSON payload on topic=%s", topic)
        except Exception as exc:
            logger.warning("Failed to process MQTT message topic=%s err=%s", topic, exc)

    def _trim_queues(self) -> None:
        cutoff = time.time() - self.pair_ttl_seconds
        while self._meta_queue and (self._meta_queue[0][1] < cutoff or len(self._meta_queue) > self.max_queue_size):
            self._meta_queue.popleft()
        while self._jpeg_queue and (self._jpeg_queue[0][1] < cutoff or len(self._jpeg_queue) > self.max_queue_size):
            self._jpeg_queue.popleft()

    def _drain_pairs_locked(self) -> None:
        while self._meta_queue and self._jpeg_queue:
            meta, _ = self._meta_queue.popleft()
            jpeg_bytes, _ = self._jpeg_queue.popleft()
            frame_id = str(meta.get("frame_id", ""))
            if not frame_id or self._is_duplicate(frame_id):
                continue
            frame = self._decode_jpeg(jpeg_bytes)
            if frame is None:
                logger.warning("Corrupt JPEG for frame_id=%s", frame_id)
                continue
            self._mark_processed(frame_id)
            try:
                self.on_frame(meta, frame)
            except Exception as exc:
                logger.warning("Frame callback failed frame_id=%s err=%s", frame_id, exc)

    @staticmethod
    def _decode_jpeg(payload: bytes) -> Any | None:
        arr = np.frombuffer(payload, dtype=np.uint8)
        if arr.size == 0:
            return None
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return frame

    def _is_duplicate(self, frame_id: str) -> bool:
        return frame_id in self._processed_set

    def _mark_processed(self, frame_id: str) -> None:
        self._processed_frame_ids.append(frame_id)
        self._processed_set.add(frame_id)
        while len(self._processed_frame_ids) > self._processed_maxlen:
            old = self._processed_frame_ids.popleft()
            self._processed_set.discard(old)
