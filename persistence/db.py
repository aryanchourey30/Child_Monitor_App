from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class EventRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    risk_score REAL NOT NULL,
                    risk_level TEXT NOT NULL,
                    state_label TEXT NOT NULL,
                    explanation TEXT NOT NULL,
                    caregiver_message TEXT,
                    technical_summary TEXT,
                    llm_used INTEGER NOT NULL DEFAULT 0,
                    llm_fallback_used INTEGER NOT NULL DEFAULT 0,
                    llm_model TEXT,
                    snapshot_path TEXT,
                    detectors_json TEXT NOT NULL,
                    notification_sent INTEGER NOT NULL DEFAULT 0,
                    acknowledged INTEGER NOT NULL DEFAULT 0
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS frame_analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    frame_path TEXT NOT NULL,
                    frame_id TEXT NOT NULL,
                    timestamp TEXT,
                    summary TEXT NOT NULL DEFAULT '',
                    scene_description TEXT NOT NULL,
                    baby_visible INTEGER NOT NULL DEFAULT 0,
                    baby_activity TEXT NOT NULL DEFAULT 'unknown',
                    risk_level TEXT NOT NULL,
                    risk_reason TEXT NOT NULL DEFAULT '',
                    observations_json TEXT NOT NULL,
                    recommended_action TEXT NOT NULL,
                    used_llm INTEGER NOT NULL DEFAULT 0,
                    model TEXT,
                    error TEXT,
                    model_result_json TEXT,
                    frame_meta_json TEXT
                );
                """
            )
            self._ensure_columns(conn)
            self._ensure_frame_analysis_columns(conn)
            conn.commit()

    @staticmethod
    def _ensure_columns(conn: sqlite3.Connection) -> None:
        expected: dict[str, str] = {
            "caregiver_message": "TEXT",
            "technical_summary": "TEXT",
            "llm_used": "INTEGER NOT NULL DEFAULT 0",
            "llm_fallback_used": "INTEGER NOT NULL DEFAULT 0",
            "llm_model": "TEXT",
        }
        rows = conn.execute("PRAGMA table_info(events)").fetchall()
        existing = {row[1] for row in rows}
        for name, col_type in expected.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE events ADD COLUMN {name} {col_type}")

    @staticmethod
    def _ensure_frame_analysis_columns(conn: sqlite3.Connection) -> None:
        expected: dict[str, str] = {
            "summary": "TEXT NOT NULL DEFAULT ''",
            "model_result_json": "TEXT",
            "frame_meta_json": "TEXT",
            "scene_description": "TEXT NOT NULL DEFAULT ''",
            "baby_visible": "INTEGER NOT NULL DEFAULT 0",
            "baby_activity": "TEXT NOT NULL DEFAULT 'unknown'",
            "risk_reason": "TEXT NOT NULL DEFAULT ''",
        }
        rows = conn.execute("PRAGMA table_info(frame_analyses)").fetchall()
        existing = {row[1] for row in rows}
        for name, col_type in expected.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE frame_analyses ADD COLUMN {name} {col_type}")

    def insert_event(self, event: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO events (
                    event_id, timestamp, event_type, risk_score, risk_level,
                    state_label, explanation, caregiver_message, technical_summary,
                    llm_used, llm_fallback_used, llm_model, snapshot_path, detectors_json,
                    notification_sent, acknowledged
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["event_id"],
                    event["timestamp"],
                    event.get("event_type", "safety_risk"),
                    float(event.get("risk_score", 0.0)),
                    event.get("risk_level", "low"),
                    event.get("state_label", "unknown"),
                    event.get("explanation", ""),
                    event.get("caregiver_message"),
                    event.get("technical_summary"),
                    int(bool(event.get("llm_used", False))),
                    int(bool(event.get("llm_fallback_used", False))),
                    event.get("llm_model"),
                    event.get("snapshot_path"),
                    json.dumps(event.get("detectors", {})),
                    int(bool(event.get("notification_sent", False))),
                    int(bool(event.get("acknowledged", False))),
                ),
            )
            conn.commit()

    def list_events(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM events ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_event(self, event_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM events WHERE event_id = ?", (event_id,)).fetchone()
        return self._row_to_dict(row) if row else None

    def acknowledge(self, event_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("UPDATE events SET acknowledged = 1 WHERE event_id = ?", (event_id,))
            conn.commit()
        return cur.rowcount > 0

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["detectors"] = json.loads(item.pop("detectors_json"))
        item["notification_sent"] = bool(item["notification_sent"])
        item["acknowledged"] = bool(item["acknowledged"])
        item["llm_used"] = bool(item.get("llm_used", 0))
        item["llm_fallback_used"] = bool(item.get("llm_fallback_used", 0))
        return item
