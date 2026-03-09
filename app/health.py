from __future__ import annotations

from typing import Any


def build_health_payload(
    *,
    camera_connected: bool,
    detector_ready: bool,
    notification_ready: bool,
    db_writable: bool,
    graph_operational: bool,
) -> dict[str, Any]:
    ok = all(
        [camera_connected, detector_ready, notification_ready, db_writable, graph_operational]
    )
    return {
        "status": "ok" if ok else "degraded",
        "camera_connected": camera_connected,
        "detector_ready": detector_ready,
        "notification_provider_ready": notification_ready,
        "db_writable": db_writable,
        "graph_operational": graph_operational,
    }
