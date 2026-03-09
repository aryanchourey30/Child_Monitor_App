from __future__ import annotations

import argparse
import json
import logging
import sys
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from agent.frame_llm_processor import FrameLLMProcessor
from app.lifecycle import AppContainer, create_container
from persistence.events_repo import build_event_record
from persistence.frame_analysis_repo import FrameAnalysisRepository
from processing.frame_queue import FrameQueue
from processing.frame_store import FrameStorageService
from processing.frame_worker import FrameWorker
from transport.mqtt_subscriber import FramePacket, MQTTFrameSubscriber
from vision.camera import CameraReader
from vision.model_runner import ModelRunner

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
logger = logging.getLogger("guardian_baby.main")


def setup_logging(logs_dir: Path) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "monitoring.log"
    handlers: list[logging.Handler] = [
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding="utf-8"),
    ]
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, handlers=handlers, force=True)


def build_event_id(frame_id: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"evt_{stamp}_{frame_id}"


def to_event_record(
    *,
    frame_id: str,
    timestamp: str,
    state: dict[str, Any],
    snapshot_path: str | None,
    notification_sent: bool,
) -> dict[str, Any]:
    return build_event_record(
        event_id=build_event_id(frame_id),
        timestamp=timestamp,
        event_type=str(state.get("event_type", "safety_risk")),
        risk_score=float(state.get("risk_score", 0.0)),
        risk_level=str(state.get("risk_level", "low")),
        state_label=str(state.get("state_label", "unknown")),
        explanation=str(state.get("explanation", "")),
        caregiver_message=state.get("caregiver_message"),
        technical_summary=state.get("technical_summary"),
        llm_used=bool(state.get("llm_used", False)),
        llm_fallback_used=bool(state.get("llm_fallback_used", False)),
        llm_model=state.get("llm_model"),
        snapshot_path=snapshot_path,
        detectors={
            "fall_risk_score": float(state.get("fall_risk_score", 0.0)),
            "wet_floor_score": float(state.get("wet_floor_score", 0.0)),
            "fire_smoke_score": float(state.get("fire_smoke_score", 0.0)),
            "ingestion_risk_score": float(state.get("ingestion_risk_score", 0.0)),
        },
        notification_sent=notification_sent,
    )


def _is_risk_level(level: str) -> bool:
    return level.lower() in {"medium", "high", "critical"}


class SessionAccumulator:
    """Collect session-level monitoring summary data."""

    def __init__(self, summaries_dir: Path) -> None:
        self.summaries_dir = summaries_dir
        self.session_id = f"sess_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        self.start_time = datetime.now(timezone.utc)
        self.frames_processed = 0
        self.subject_detected = False
        self.events: list[dict[str, Any]] = []
        self.state_counter: Counter[str] = Counter()
        self.max_risk_score = 0.0
        self.final_risk_level = "low"
        self.snapshot_paths: list[str] = []
        self._risk_rank = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        self._lock = threading.Lock()

    def update(self, state: dict[str, Any], snapshot_path: str | None, timestamp: str) -> None:
        with self._lock:
            self.frames_processed += 1
            if bool(state.get("baby_detected", state.get("subject_detected", False))):
                self.subject_detected = True
            state_label = str(state.get("state_label", "unknown"))
            self.state_counter[state_label] += 1
            score = float(state.get("risk_score", 0.0))
            if score > self.max_risk_score:
                self.max_risk_score = score
            level = str(state.get("risk_level", "low"))
            if self._risk_rank.get(level, 0) > self._risk_rank.get(self.final_risk_level, 0):
                self.final_risk_level = level
            if _is_risk_level(level):
                self.events.append(
                    {
                        "event_type": str(state.get("event_type", "safety_risk")),
                        "timestamp": timestamp,
                        "risk_score": score,
                        "details": str(state.get("technical_summary") or state.get("explanation") or "risk signal"),
                    }
                )
            if snapshot_path:
                self.snapshot_paths.append(snapshot_path)

    def _build_summary(self, end_time: datetime, *, finalized: bool) -> dict[str, Any]:
        dominant = self.state_counter.most_common(1)[0][0] if self.state_counter else "unknown"
        if self.events:
            explanation = (
                f"Detected {len(self.events)} elevated-risk events. "
                f"Highest risk score {self.max_risk_score:.2f} ({self.final_risk_level})."
            )
        elif self.subject_detected:
            explanation = "Subject detected with no elevated hazards observed."
        else:
            explanation = "No subject reliably detected; no elevated hazards observed."
        summary = {
            "session_id": self.session_id,
            "start_time": self.start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": int((end_time - self.start_time).total_seconds()),
            "frames_processed": self.frames_processed,
            "subject_detected": self.subject_detected,
            "events": self.events,
            "dominant_state": dominant,
            "final_risk_level": self.final_risk_level,
            "max_risk_score": self.max_risk_score,
            "explanation": explanation,
            "snapshot_paths": self.snapshot_paths,
            "finalized": finalized,
        }
        return summary

    def current(self) -> dict[str, Any]:
        with self._lock:
            now = datetime.now(timezone.utc)
            return self._build_summary(now, finalized=False)

    def finalize(self) -> dict[str, Any]:
        with self._lock:
            end_time = datetime.now(timezone.utc)
            summary = self._build_summary(end_time, finalized=True)
        self.summaries_dir.mkdir(parents=True, exist_ok=True)
        out = self.summaries_dir / f"{self.session_id}.json"
        with out.open("w", encoding="utf-8") as file:
            json.dump(summary, file, indent=2)
        logger.info("Session summary written: %s", out)
        return summary


class MonitoringBackendService:
    """Backend service that ingests frames, runs model, then LLM sequentially."""

    def __init__(self, container: AppContainer) -> None:
        self.container = container
        self.accumulator = SessionAccumulator(container.settings.summaries_dir)
        cfg = container.settings.processing
        frame_cfg = container.settings.frame_llm

        self.frame_queue = FrameQueue(
            max_size=int(cfg.get("queue_max_size", 200)),
            overflow_strategy=str(cfg.get("queue_overflow_strategy", "drop_oldest")),
        )
        self.frame_store = FrameStorageService(
            storage_dir=str(frame_cfg.get("storage_dir", "data/frames/current_batch")),
            max_files=int(frame_cfg.get("batch_size", 240)),
        )
        self.model_runner = ModelRunner(graph=container.graph, detector=container.detector)
        self.llm_processor = FrameLLMProcessor(
            enable_analysis=bool(frame_cfg.get("enable_analysis", True)),
            model=str(frame_cfg.get("model", "gpt-4.1-mini")),
            timeout_seconds=float(frame_cfg.get("timeout_seconds", 10)),
            max_retries=int(frame_cfg.get("max_retries", 2)),
        )
        self.frame_analysis_repo = FrameAnalysisRepository(container.settings.db_path)
        self.frame_worker = FrameWorker(
            frame_queue=self.frame_queue,
            frame_store=self.frame_store,
            model_runner=self.model_runner,
            llm_processor=self.llm_processor,
            on_result=self._on_processed_result,
        )

        self._subscriber: MQTTFrameSubscriber | None = None
        self._camera_reader: CameraReader | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._last_heartbeat: dict[str, Any] | None = None
        self._last_video_meta: dict[str, Any] | None = None

    def start(self, camera_source: int | str | None = None) -> None:
        self.frame_worker.start()
        ingest_mode = str(self.container.settings.config.get("app", {}).get("ingest_mode", "mqtt")).lower()
        if ingest_mode == "camera":
            self._start_camera_fallback(camera_source=camera_source)
        else:
            self._start_mqtt()

    def stop(self) -> dict[str, Any]:
        self._stop_event.set()
        if self._subscriber is not None:
            self._subscriber.stop()
            self._subscriber = None
        if self._camera_reader is not None:
            self._camera_reader.close()
            self._camera_reader = None
        self.frame_worker.stop()
        summary = self.accumulator.finalize()
        self.container.latest_state = {"session_summary": summary}
        return summary

    def get_current_session_summary(self) -> dict[str, Any]:
        return self.accumulator.current()

    def _start_mqtt(self) -> None:
        mqtt_cfg = self.container.settings.mqtt
        topics_cfg = mqtt_cfg.get("topics", {})
        self._subscriber = MQTTFrameSubscriber(
            host=str(mqtt_cfg.get("host", "localhost")),
            port=int(mqtt_cfg.get("port", 1883)),
            username=str(mqtt_cfg.get("username", "") or ""),
            password=str(mqtt_cfg.get("password", "") or ""),
            keepalive=int(mqtt_cfg.get("keepalive", 60)),
            pair_ttl_seconds=float(mqtt_cfg.get("pair_ttl_seconds", 60.0)),
            max_pending_pairs=int(mqtt_cfg.get("max_pending_pairs", 500)),
            topic_meta=str(topics_cfg.get("frame_meta", "guardianbaby/frame/meta")),
            topic_jpeg=str(topics_cfg.get("frame_jpeg", "guardianbaby/frame/jpeg")),
            frame_queue=self.frame_queue,
        )
        self._subscriber.start()
        logger.info("MQTT frame subscriber started.")

    def _start_camera_fallback(self, camera_source: int | str | None = None) -> None:
        camera_cfg = self.container.settings.camera
        source = camera_source if camera_source is not None else camera_cfg.get("source", 0)
        reader = CameraReader(
            source=source,
            width=camera_cfg.get("width"),
            height=camera_cfg.get("height"),
            reconnect_attempts=int(camera_cfg.get("reconnect_attempts", 5)),
            reconnect_delay_sec=float(camera_cfg.get("reconnect_delay_sec", 1.0)),
        )
        reader.open()
        self._camera_reader = reader

        def _loop() -> None:
            while not self._stop_event.is_set():
                packet = reader.read()
                if packet is None:
                    continue
                ok, encoded = cv2.imencode(".jpg", packet.frame)
                if not ok:
                    continue
                frame_packet = FramePacket(
                    frame_id=packet.frame_id,
                    timestamp=packet.timestamp,
                    meta={"frame_id": packet.frame_id, "timestamp": packet.timestamp, "source": "local-camera"},
                    jpeg_bytes=encoded.tobytes(),
                    received_at=time.time(),
                )
                self.frame_queue.enqueue(frame_packet)

        thread = threading.Thread(target=_loop, daemon=True, name="camera-fallback-loop")
        thread.start()
        logger.info("Camera fallback frame source started source=%s", source)

    def _on_processed_result(self, result: dict[str, Any]) -> None:
        frame_id = str(result.get("frame_id", "unknown"))
        timestamp = str(result.get("timestamp", datetime.now(timezone.utc).isoformat()))
        frame_path = result.get("frame_path")
        model_result = result.get("model_result", {}) or {}
        llm_result = result.get("llm_result", {}) or {}

        try:
            analysis_row = dict(llm_result)
            analysis_row["model_result"] = model_result
            analysis_row["frame_meta"] = result.get("meta", {})
            self.frame_analysis_repo.insert_analysis(analysis_row)
            logger.info("Frame LLM analysis persisted frame_id=%s", frame_id)
        except Exception as exc:
            logger.warning("Failed persisting frame LLM analysis frame_id=%s err=%s", frame_id, exc)

        state = dict(model_result.get("raw_state", {}))
        if not state:
            state = {
                "event_type": "safety_risk",
                "risk_score": float(model_result.get("risk_score", 0.0)),
                "risk_level": str(model_result.get("risk_level", "low")),
                "state_label": str(model_result.get("state_label", "unknown")),
                "explanation": str(llm_result.get("scene_description", "")),
                "baby_detected": bool(model_result.get("subject_detected", False)),
            }
        state.setdefault("event_type", "safety_risk")
        state["frame_id"] = frame_id
        state["timestamp"] = timestamp
        state["explanation"] = str(
            state.get("explanation")
            or llm_result.get("scene_description")
            or "Frame captured and analyzed."
        )
        state["technical_summary"] = str(
            llm_result.get("risk_reason")
            or llm_result.get("scene_description")
            or "Frame analyzed"
        )
        state["caregiver_message"] = str(llm_result.get("recommended_action") or "Continue monitoring")
        state["llm_used"] = bool(llm_result.get("used_llm", False))
        state["llm_model"] = llm_result.get("model")
        state["llm_fallback_used"] = not bool(llm_result.get("used_llm", False))
        state["baby_detected"] = bool(llm_result.get("baby_visible", state.get("baby_detected", False)))
        state["state_label"] = str(llm_result.get("baby_activity", state.get("state_label", "unknown")))
        state["risk_level"] = str(llm_result.get("risk_level", state.get("risk_level", "low")))

        logger.info(
            "Frame analyzed %s baby_visible=%s activity=%s risk=%s desc='%s'",
            frame_id,
            llm_result.get("baby_visible", False),
            llm_result.get("baby_activity", "unknown"),
            llm_result.get("risk_level", "unknown"),
            str(llm_result.get("scene_description", ""))[:140],
        )

        snapshot_path = frame_path if _is_risk_level(str(state.get("risk_level", "low"))) else None
        sent = False
        if _is_risk_level(str(state.get("risk_level", "low"))):
            try:
                sent = self.container.notifier.send(
                    {
                        "timestamp": timestamp,
                        "severity": state.get("risk_level"),
                        "event_type": state.get("event_type"),
                        "risk_score": state.get("risk_score"),
                        "caregiver_message": state.get("caregiver_message"),
                        "explanation": state.get("explanation"),
                        "technical_summary": state.get("technical_summary"),
                        "frame_id": frame_id,
                    }
                )
            except Exception as exc:
                logger.warning("Notification send failed frame_id=%s err=%s", frame_id, exc)

        try:
            self.container.repository.insert_event(
                to_event_record(
                    frame_id=frame_id,
                    timestamp=timestamp,
                    state=state,
                    snapshot_path=snapshot_path,
                    notification_sent=sent,
                )
            )
        except Exception as exc:
            logger.warning("Event persistence failed frame_id=%s err=%s", frame_id, exc)

        self.accumulator.update(state, snapshot_path, timestamp=timestamp)
        self.container.latest_state = {"frame_result": result, "state": state}


def run_backend(camera_source: int | str | None = None) -> dict[str, Any]:
    container = create_container()
    setup_logging(container.settings.logs_dir)
    service = MonitoringBackendService(container)
    service.start(camera_source=camera_source)
    logger.info("GuardianBaby backend started. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        logger.info("Stopping backend...")
    return service.stop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GuardianBaby backend")
    parser.add_argument("--camera-source", type=str, default=None, help="Used only when ingest_mode=camera.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    result = run_backend(camera_source=args.camera_source)
    print(json.dumps(result, indent=2))
