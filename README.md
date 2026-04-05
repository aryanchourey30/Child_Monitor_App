# GuardianBaby

GuardianBaby is a local-first, vision-based baby safety monitoring backend using deterministic safety rules and LangGraph-style orchestration.

## Features
- Camera ingestion from webcam or video files
- Baby/person detection (mock + optional YOLO backend)
- Tracking, restricted-zone checks, fall-risk and wet-floor heuristics
- Risk fusion with explainable severity labels
- Event persistence in SQLite with snapshots
- FastAPI endpoints for health, events, latest state, acknowledge, config reload, replay
- Dry-run notification dispatcher
- Offline replay runner for deterministic testing
- Optional OpenAI-based explanation summarization with deterministic fallback
- MQTT ingestion from Raspberry Pi (`rpicam-still` publisher)
- Frame-buffered sequential LLM analysis (save -> queue -> analyze one by one)

## Quick Start
```bash
cd guardian_baby
python -m venv .venv
# Windows
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.api:app --reload
```

## MQTT Ingestion Architecture
- Raspberry Pi publishes:
  - `guardianbaby/frame/jpeg` (raw JPEG bytes)
  - `guardianbaby/frame/meta` (JSON metadata)
  - optional `guardianbaby/device/heartbeat`
  - optional `guardianbaby/video/meta`
- Laptop backend subscribes and processes all downstream logic locally.
- Backend startup automatically starts MQTT consumption and frame processing.

-Pipeline modules:
- `transport/mqtt_subscriber.py`: subscribes to `guardianbaby/frame/meta` and `guardianbaby/frame/jpeg`, correlates packets, pushes queue items.
- `processing/frame_queue.py`: FIFO queue with configurable overflow strategy.
- `processing/frame_store.py`: saves every frame and keeps rolling latest 240 files.
- `processing/frame_worker.py`: sequential worker: decode -> save -> model -> LLM -> persist.
- `vision/model_runner.py`: per-frame model interface (graph-backed or placeholder fallback).

## Frame Storage + Sequential LLM Pipeline
- Every incoming frame is saved first to `data/frames/current_batch/` with sortable timestamp-based names:
  - `YYYYMMDDTHHMMSS_microsecondsZ_<frame_id>.jpg`
- Rolling retention:
  - keep at most 240 files
  - if file count exceeds 240, delete oldest files until only 240 remain
- Per-frame sequential flow:
  1. receive MQTT meta + JPEG
  2. queue packet
  3. worker decodes and saves frame
  4. model runs on frame
  5. LLM runs with model output + metadata
  6. result persisted

Per-frame LLM output now always includes meaningful interpretation fields:
- `scene_description`
- `baby_visible`
- `baby_activity`
- `risk_level`
- `risk_reason`
- `observations`
- `recommended_action`

Examples:
- "Baby is playing safely on the floor."
- "No baby visible in the frame."
- "Baby appears near the bed edge, which may increase fall risk."

## Setup From Scratch
1. Install Python 3.11+, Git, and VS Code.
2. Create venv and install dependencies:
```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1  # Windows
pip install -r requirements.txt
```
3. Copy environment variables:
```bash
copy .env.example .env
```
4. Update zone polygons in `configs/zones.yaml`.

## Run Monitor (One Command)
```bash
python app/main.py
```

API mode (also auto-starts consumer):
```bash
uvicorn app.api:app --reload
```

Camera fallback mode:
```bash
GB_INGEST_MODE=camera python app/main.py --camera-source 0
```

## Run Replay
```bash
python replay/replay_runner.py --video tests/sample_videos/demo.mp4 --dry-run
```

## Run Tests
```bash
pytest -q
```

## OpenAI Summarization (Optional)
- `OPENAI_API_KEY` enables server-side LLM summaries via OpenAI Responses API.
- LLM is used only for:
  - caregiver-facing alert wording
  - concise technical summary for logs
  - readable narration text
- Critical safety decisions (detection, scoring, alert thresholds) remain deterministic and rule-based.

Environment variables:
```bash
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4.1-mini
OPENAI_TIMEOUT_SECONDS=10
OPENAI_MAX_RETRIES=2
OPENAI_ENABLE_SUMMARIZATION=true
ENABLE_FRAME_LLM_ANALYSIS=true
FRAME_STORAGE_DIR=data/frames/current_batch
FRAME_BATCH_SIZE=240
```

Disable LLM summarization:
```bash
OPENAI_ENABLE_SUMMARIZATION=false
```

Fallback behavior:
- If API timeout/failure/unusable response occurs, the system uses deterministic templates.
- Monitoring loop and alert routing continue without interruption.

## Debugging Guide
Use layered debugging:
1. Camera: validate source index/path and frame dimensions.
2. Detector: inspect `baby_detected`, `baby_bbox`, confidence.
3. Tracker: verify trajectory continuity and velocity stability.
4. Zones: verify polygon coordinates match frame resolution.
5. Risk fusion: check each detector score and thresholds in `configs/config.yaml`.
6. Graph: inspect `GET /latest-state` and persisted events.
7. Notifications: set dry-run mode and inspect logs for cooldown suppression.

Common issue checks:
- Blank frames: wrong camera index or source unavailable.
- No alerts: risk thresholds too high or no active hazard zones.
- False alerts: tune zone polygons and weights; require persistence via cooldown.
- Missing DB events: verify `GB_DB_PATH` and write permissions for `data/events`.
- Frame write failure: verify write permission for `FRAME_STORAGE_DIR`.
- OpenAI API failure: verify `OPENAI_API_KEY`, model access, timeout, and connectivity.
- Batch reset issues: ensure no external process is locking files in `data/frames/current_batch`.

## API
- `GET /health`
- `GET /events`
- `GET /events/{id}`
- `GET /latest-state`
- `POST /acknowledge/{id}`
- `POST /config/reload`
- `POST /replay`

## Safety Disclaimer
GuardianBaby is an aid for caregivers, not a substitute for supervision and not a medical or life-critical certified system.
