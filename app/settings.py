from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


@dataclass(slots=True)
class Settings:
    config_path: Path
    zones_path: Path
    db_path: Path
    snapshots_dir: Path
    summaries_dir: Path
    logs_dir: Path
    config: dict[str, Any]

    @property
    def camera(self) -> dict[str, Any]:
        return self.config.get("camera", {})

    @property
    def risk(self) -> dict[str, Any]:
        return self.config.get("risk", {})

    @property
    def notifications(self) -> dict[str, Any]:
        return self.config.get("notifications", {})

    @property
    def openai(self) -> dict[str, Any]:
        return self.config.get("openai", {})

    @property
    def mqtt(self) -> dict[str, Any]:
        return self.config.get("mqtt", {})

    @property
    def frame_llm(self) -> dict[str, Any]:
        return self.config.get("frame_llm", {})

    @property
    def processing(self) -> dict[str, Any]:
        return self.config.get("processing", {})


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _require_positive_int(value: int, key: str) -> int:
    if value <= 0:
        raise ValueError(f"{key} must be > 0, got {value}")
    return value


def _require_positive_float(value: float, key: str) -> float:
    if value <= 0:
        raise ValueError(f"{key} must be > 0, got {value}")
    return value


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing config file: {path}")
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML root in {path}: expected object")
    return data


def load_settings(base_dir: Path | None = None) -> Settings:
    load_dotenv()
    root = (base_dir or Path(__file__).resolve().parents[1]).resolve()
    config_path = root / os.getenv("GB_CONFIG_PATH", "configs/config.yaml")
    zones_path = root / os.getenv("GB_ZONES_PATH", "configs/zones.yaml")
    db_path = root / os.getenv("GB_DB_PATH", "data/events/guardian_baby.db")
    snapshots_dir = root / os.getenv("GB_SNAPSHOTS_DIR", "data/snapshots")
    config = _read_yaml(config_path)
    summaries_dir = root / str(config.get("outputs", {}).get("summaries_dir", "data/summaries"))
    logs_dir = root / str(config.get("outputs", {}).get("logs_dir", "data/logs"))
    config.setdefault("openai", {})
    config["openai"]["model"] = os.getenv("OPENAI_MODEL", str(config["openai"].get("model", "gpt-4.1-mini")))
    config["openai"]["timeout_seconds"] = float(
        os.getenv("OPENAI_TIMEOUT_SECONDS", str(config["openai"].get("timeout_seconds", 8.0)))
    )
    config["openai"]["enable_summarization"] = _to_bool(
        os.getenv("OPENAI_ENABLE_SUMMARIZATION"),
        bool(config["openai"].get("enable_summarization", True)),
    )
    config["openai"]["max_retries"] = int(config["openai"].get("max_retries", 2))
    config.setdefault("app", {})
    config["app"]["ingest_mode"] = os.getenv("GB_INGEST_MODE", str(config["app"].get("ingest_mode", "mqtt")))
    config.setdefault("mqtt", {})
    config["mqtt"]["host"] = os.getenv("MQTT_HOST", str(config["mqtt"].get("host", "localhost")))
    config["mqtt"]["port"] = int(os.getenv("MQTT_PORT", str(config["mqtt"].get("port", 1883))))
    config["mqtt"]["username"] = os.getenv("MQTT_USERNAME", str(config["mqtt"].get("username", "")))
    config["mqtt"]["password"] = os.getenv("MQTT_PASSWORD", str(config["mqtt"].get("password", "")))
    config["mqtt"]["max_pending_pairs"] = _require_positive_int(
        int(os.getenv("MQTT_MAX_PENDING_PAIRS", str(config["mqtt"].get("max_pending_pairs", 500)))),
        "MQTT_MAX_PENDING_PAIRS",
    )
    config.setdefault("frame_llm", {})
    config["frame_llm"]["storage_dir"] = os.getenv(
        "FRAME_STORAGE_DIR",
        str(config["frame_llm"].get("storage_dir", "data/frames/current_batch")),
    )
    config["frame_llm"]["batch_size"] = _require_positive_int(
        int(os.getenv("FRAME_BATCH_SIZE", str(config["frame_llm"].get("batch_size", 240)))),
        "FRAME_BATCH_SIZE",
    )
    config["frame_llm"]["model"] = os.getenv("OPENAI_MODEL", str(config["frame_llm"].get("model", "gpt-4.1-mini")))
    config["frame_llm"]["timeout_seconds"] = _require_positive_float(
        float(os.getenv("OPENAI_TIMEOUT_SECONDS", str(config["frame_llm"].get("timeout_seconds", 10)))),
        "OPENAI_TIMEOUT_SECONDS",
    )
    config["frame_llm"]["max_retries"] = _require_positive_int(
        int(os.getenv("OPENAI_MAX_RETRIES", str(config["frame_llm"].get("max_retries", 2)))),
        "OPENAI_MAX_RETRIES",
    )
    config["frame_llm"]["enable_analysis"] = _to_bool(
        os.getenv("ENABLE_FRAME_LLM_ANALYSIS"),
        bool(config["frame_llm"].get("enable_analysis", True)),
    )
    config.setdefault("processing", {})
    config["processing"]["queue_max_size"] = _require_positive_int(
        int(os.getenv("FRAME_QUEUE_MAX_SIZE", str(config["processing"].get("queue_max_size", 200)))),
        "FRAME_QUEUE_MAX_SIZE",
    )
    overflow = os.getenv("FRAME_QUEUE_OVERFLOW_STRATEGY", str(config["processing"].get("queue_overflow_strategy", "drop_oldest")))
    if overflow not in {"drop_oldest", "drop_new", "block"}:
        raise ValueError("FRAME_QUEUE_OVERFLOW_STRATEGY must be one of: drop_oldest, drop_new, block")
    config["processing"]["queue_overflow_strategy"] = overflow
    # Inject zone path for convenience.
    config.setdefault("zones", {})
    config["zones"]["path"] = str(zones_path)
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    summaries_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    (root / str(config["frame_llm"]["storage_dir"])).mkdir(parents=True, exist_ok=True)
    return Settings(
        config_path=config_path,
        zones_path=zones_path,
        db_path=db_path,
        snapshots_dir=snapshots_dir,
        summaries_dir=summaries_dir,
        logs_dir=logs_dir,
        config=config,
    )
