from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import numpy as np

from processing.frame_store import FrameStorageService


def _tmp_dir() -> Path:
    root = Path(__file__).resolve().parents[2] / ".test_tmp"
    root.mkdir(parents=True, exist_ok=True)
    d = root / f"proc_store_{uuid.uuid4().hex}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _frame() -> np.ndarray:
    return np.zeros((16, 16, 3), dtype=np.uint8)


def test_retention_deletes_oldest_when_exceeded() -> None:
    d = _tmp_dir()
    store = FrameStorageService(storage_dir=str(d), max_files=3)
    store.save_frame(_frame(), frame_id="1", timestamp="2026-03-08T10:00:00.000001+00:00")
    store.save_frame(_frame(), frame_id="2", timestamp="2026-03-08T10:00:15.000001+00:00")
    store.save_frame(_frame(), frame_id="3", timestamp="2026-03-08T10:00:30.000001+00:00")
    store.save_frame(_frame(), frame_id="4", timestamp="2026-03-08T10:00:45.000001+00:00")
    names = [p.name for p in store.list_files()]
    assert len(names) == 3
    assert any("_4.jpg" in n for n in names)
    assert not any("_1.jpg" in n for n in names)
    shutil.rmtree(d, ignore_errors=True)
