from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.lifecycle import create_container
from app.main import build_event_id, to_event_record
from persistence.snapshots import save_snapshot
from vision.camera import CameraReader


def replay_video(video: str, dry_run: bool = True, max_frames: int | None = None) -> dict[str, Any]:
    container = create_container()
    if dry_run:
        container.notifier.dry_run = True
    camera = CameraReader(source=video)
    camera.open()
    processed = 0
    alerts = 0
    try:
        while True:
            packet = camera.read()
            if packet is None:
                break
            state = container.graph.run(
                detector=container.detector,
                frame=packet.frame,
                frame_id=packet.frame_id,
                timestamp=packet.timestamp,
            )
            snapshot_path = None
            sent = False
            if state.get("alert_needed"):
                alerts += 1
                snapshot_path = save_snapshot(packet.frame, container.settings.snapshots_dir, build_event_id(packet.frame_id))
                sent = container.notifier.send(state["alert_payload"])
            event = to_event_record(state, snapshot_path, sent)
            container.repository.insert_event(event)
            processed += 1
            if max_frames is not None and processed >= max_frames:
                break
    finally:
        camera.close()
    return {"processed_frames": processed, "alerts": alerts, "dry_run": dry_run}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay saved video through GuardianBaby pipeline")
    parser.add_argument("--video", required=True, help="Path to input video")
    parser.add_argument("--dry-run", action="store_true", help="Do not send production notifications")
    parser.add_argument("--max-frames", type=int, default=None)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    path = Path(args.video)
    if not path.exists():
        raise SystemExit(f"Video not found: {path}")
    out = replay_video(video=str(path), dry_run=args.dry_run, max_frames=args.max_frames)
    print(out)
