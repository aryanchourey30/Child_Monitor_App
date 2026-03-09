from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class FrameAnalysisRepository:
    """Persistence helper for frame-by-frame LLM analysis results."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def insert_analysis(self, row: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO frame_analyses (
                    frame_path, frame_id, timestamp, summary, scene_description, baby_visible, baby_activity,
                    risk_level, risk_reason, observations_json, recommended_action, used_llm, model, error,
                    model_result_json, frame_meta_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("frame_path"),
                    row.get("frame_id"),
                    row.get("timestamp"),
                    row.get("scene_description", row.get("summary", "")),
                    row.get("scene_description", row.get("summary", "")),
                    int(bool(row.get("baby_visible", False))),
                    row.get("baby_activity", "unknown"),
                    row.get("risk_level"),
                    row.get("risk_reason", ""),
                    json.dumps(row.get("observations", [])),
                    row.get("recommended_action"),
                    int(bool(row.get("used_llm", False))),
                    row.get("model"),
                    row.get("error"),
                    json.dumps(row.get("model_result", {})),
                    json.dumps(row.get("frame_meta", {})),
                ),
            )
            conn.commit()

    def list_analyses(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM frame_analyses ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["observations"] = json.loads(item.pop("observations_json") or "[]")
            item["model_result"] = json.loads(item.pop("model_result_json") or "{}")
            item["frame_meta"] = json.loads(item.pop("frame_meta_json") or "{}")
            item["used_llm"] = bool(item.get("used_llm", 0))
            # Legacy alias to preserve compatibility with older callers.
            item["summary"] = item.get("scene_description", "")
            item["baby_visible"] = bool(item.get("baby_visible", 0))
            out.append(item)
        return out
