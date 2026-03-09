from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import numpy as np

from vision.frame_store import FrameStore


def _dummy_frame() -> np.ndarray:
    return np.zeros((16, 16, 3), dtype=np.uint8)


def _mktemp_dir() -> Path:
    root = Path(__file__).resolve().parents[2] / ".test_tmp"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"frame_store_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_save_frame_and_count() -> None:
    tmp_path = _mktemp_dir()
    store = FrameStore(storage_dir=str(tmp_path), max_frames=240)
    path = store.save_frame(_dummy_frame())
    assert Path(path).exists()
    assert store.get_current_frame_count() == 1
    shutil.rmtree(tmp_path, ignore_errors=True)


def test_rollover_deletes_old_batch() -> None:
    tmp_path = _mktemp_dir()
    store = FrameStore(storage_dir=str(tmp_path), max_frames=3)
    store.save_frame(_dummy_frame())
    store.save_frame(_dummy_frame())
    store.save_frame(_dummy_frame())
    assert store.get_current_frame_count() == 3
    # Next save triggers reset and starts new batch at frame_000001
    new_path = store.save_frame(_dummy_frame())
    assert Path(new_path).name == "frame_000001.jpg"
    files = store.list_saved_frames()
    assert len(files) == 1
    assert files[0].endswith("frame_000001.jpg")
    shutil.rmtree(tmp_path, ignore_errors=True)
