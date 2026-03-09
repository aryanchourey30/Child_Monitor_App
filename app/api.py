from __future__ import annotations

import threading
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.health import build_health_payload
from app.lifecycle import create_container
from app.main import MonitoringBackendService
from persistence.frame_analysis_repo import FrameAnalysisRepository
from replay.replay_runner import replay_video

app = FastAPI(title="GuardianBaby API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
data_dir = Path(__file__).resolve().parents[1] / "data"
if data_dir.exists():
    app.mount("/media", StaticFiles(directory=str(data_dir)), name="media")

container = create_container()
service = MonitoringBackendService(container)
frame_analysis_repo = FrameAnalysisRepository(container.settings.db_path)
service_thread: threading.Thread | None = None


class ReplayRequest(BaseModel):
    video: str
    dry_run: bool = True


@app.on_event("startup")
def startup_monitoring() -> None:
    """Start MQTT/camera ingestion automatically when backend starts."""
    global service_thread
    if service_thread and service_thread.is_alive():
        return

    def _runner() -> None:
        service.start()

    service_thread = threading.Thread(target=_runner, daemon=True, name="guardianbaby-service")
    service_thread.start()


@app.on_event("shutdown")
def shutdown_monitoring() -> None:
    service.stop()


@app.get("/health")
def get_health() -> dict[str, Any]:
    db_ok = True
    try:
        container.repository.list_events(limit=1)
    except Exception:
        db_ok = False
    return build_health_payload(
        camera_connected=True,
        detector_ready=True,
        notification_ready=True,
        db_writable=db_ok,
        graph_operational=True,
    )


@app.get("/events")
def get_events(limit: int = 100) -> list[dict[str, Any]]:
    return container.repository.list_events(limit=max(1, min(limit, 500)))


@app.get("/events/{event_id}")
def get_event(event_id: str) -> dict[str, Any]:
    event = container.repository.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@app.get("/latest-state")
def latest_state() -> dict[str, Any]:
    payload = dict(container.latest_state or {})
    if "frame_result" not in payload:
        latest_rows = frame_analysis_repo.list_analyses(limit=1)
        if latest_rows:
            payload["frame_result"] = latest_rows[0]

    if "state" not in payload:
        events = container.repository.list_events(limit=1)
        if events:
            payload["state"] = events[0]

    frame_result = payload.get("frame_result", {}) or {}
    state = payload.get("state", {}) or {}
    payload["live_analysis"] = {
        "frame_id": frame_result.get("frame_id") or state.get("frame_id"),
        "timestamp": frame_result.get("timestamp") or state.get("timestamp"),
        "baby_visible": bool(frame_result.get("baby_visible", state.get("baby_detected", False))),
        "activity": frame_result.get("baby_activity") or state.get("state_label"),
        "risk_level": frame_result.get("risk_level") or state.get("risk_level"),
        "scene_summary": frame_result.get("scene_description") or state.get("explanation"),
        "risk_reason": frame_result.get("risk_reason") or state.get("technical_summary"),
        "observations": frame_result.get("observations", []),
        "recommended_action": frame_result.get("recommended_action") or state.get("caregiver_message"),
        "used_llm": bool(frame_result.get("used_llm", state.get("llm_used", False))),
        "model": frame_result.get("model") or state.get("llm_model"),
        "error": frame_result.get("error"),
    }
    return payload


@app.get("/latest-frame")
def latest_frame() -> dict[str, Any]:
    rows = frame_analysis_repo.list_analyses(limit=1)
    if not rows:
        raise HTTPException(status_code=404, detail="No frame analyses available")
    row = rows[0]
    return {
        "frame_id": row.get("frame_id"),
        "frame_path": row.get("frame_path"),
        "timestamp": row.get("timestamp"),
        "thumbnail_path": row.get("frame_path"),
        "scene_description": row.get("scene_description"),
        "risk_level": row.get("risk_level"),
    }


@app.get("/recent-frames")
def recent_frames(limit: int = 10) -> list[dict[str, Any]]:
    rows = frame_analysis_repo.list_analyses(limit=max(1, min(limit, 50)))
    return [
        {
            "frame_id": row.get("frame_id"),
            "frame_path": row.get("frame_path"),
            "timestamp": row.get("timestamp"),
            "thumbnail_path": row.get("frame_path"),
            "scene_description": row.get("scene_description"),
            "risk_level": row.get("risk_level"),
        }
        for row in rows
    ]


@app.get("/sessions")
def sessions(limit: int = 50) -> list[dict[str, Any]]:
    summaries_dir = container.settings.summaries_dir
    if not summaries_dir.exists():
        return []
    files = sorted(summaries_dir.glob("sess_*.json"), reverse=True)[: max(1, min(limit, 200))]
    out: list[dict[str, Any]] = []
    for file in files:
        try:
            out.append(json.loads(file.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out


@app.get("/sessions/{session_id}")
def session_by_id(session_id: str) -> dict[str, Any]:
    summaries_dir = container.settings.summaries_dir
    file = summaries_dir / f"{session_id}.json"
    if not file.exists():
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        return json.loads(file.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Session file unreadable: {exc}") from exc


@app.get("/current-session-summary")
def current_session_summary() -> dict[str, Any]:
    return service.get_current_session_summary()


@app.post("/acknowledge/{event_id}")
def acknowledge(event_id: str) -> dict[str, Any]:
    ok = container.repository.acknowledge(event_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"acknowledged": True, "event_id": event_id}


@app.post("/config/reload")
def reload_config() -> dict[str, str]:
    global container, service, service_thread
    service.stop()
    container = create_container()
    service = MonitoringBackendService(container)
    service_thread = threading.Thread(target=service.start, daemon=True, name="guardianbaby-service")
    service_thread.start()
    return {"status": "reloaded"}


@app.post("/replay")
def replay(req: ReplayRequest) -> dict[str, Any]:
    video_path = Path(req.video)
    if not video_path.exists():
        raise HTTPException(status_code=400, detail="Video path not found")
    return replay_video(video=str(video_path), dry_run=req.dry_run)


@app.post("/run-once")
def run_once() -> dict[str, Any]:
    # In streaming mode, expose latest state snapshot.
    return {"status": "streaming", "latest_state_available": bool(container.latest_state)}
