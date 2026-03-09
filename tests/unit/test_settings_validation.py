from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest

from app.settings import load_settings


def _write_minimal_config(root: Path) -> None:
    (root / "configs").mkdir(parents=True, exist_ok=True)
    (root / "configs" / "zones.yaml").write_text("zones: []\n", encoding="utf-8")
    (root / "configs" / "config.yaml").write_text(
        """
app:
  ingest_mode: mqtt
camera:
  source: 0
outputs:
  summaries_dir: data/summaries
  logs_dir: data/logs
frame_llm:
  storage_dir: data/frames/current_batch
  batch_size: 240
  model: gpt-4.1-mini
  timeout_seconds: 10
  max_retries: 2
  enable_analysis: true
""".strip(),
        encoding="utf-8",
    )


def test_invalid_frame_batch_size_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    root = Path(__file__).resolve().parents[2] / ".test_tmp"
    root.mkdir(parents=True, exist_ok=True)
    tmp_path = root / f"settings_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=True)
    _write_minimal_config(tmp_path)
    monkeypatch.setenv("GB_CONFIG_PATH", "configs/config.yaml")
    monkeypatch.setenv("GB_ZONES_PATH", "configs/zones.yaml")
    monkeypatch.setenv("FRAME_BATCH_SIZE", "0")
    with pytest.raises(ValueError):
        load_settings(base_dir=tmp_path)
    shutil.rmtree(tmp_path, ignore_errors=True)
