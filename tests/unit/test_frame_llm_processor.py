from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any

from agent.frame_llm_processor import FrameLLMProcessor


class _Response:
    def __init__(self, text: str) -> None:
        self.output_text = text


class _ResponsesClient:
    def __init__(self, text: str) -> None:
        self.text = text

    def create(self, **_: Any) -> _Response:
        return _Response(self.text)


class _Client:
    def __init__(self, text: str) -> None:
        self.responses = _ResponsesClient(text)

    def with_options(self, **_: Any) -> "_Client":
        return self


class _FailingResponses:
    def create(self, **_: Any) -> Any:
        raise RuntimeError("openai failure")


class _FailingClient:
    def with_options(self, **_: Any) -> "_FailingClient":
        return self

    @property
    def responses(self) -> _FailingResponses:
        return _FailingResponses()


def _temp_frame() -> Path:
    root = Path(__file__).resolve().parents[2] / ".test_tmp"
    root.mkdir(parents=True, exist_ok=True)
    tmp_path = root / f"frame_llm_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=True)
    frame = tmp_path / "frame_000001.jpg"
    frame.write_bytes(b"fakejpeg")
    return frame


def test_fifo_ordering() -> None:
    proc = FrameLLMProcessor(enable_analysis=False)
    called: list[str] = []

    def _fake_process(frame_path: str) -> dict[str, Any]:
        called.append(frame_path)
        return {"frame_path": frame_path}

    proc.process_frame = _fake_process  # type: ignore[assignment]
    proc.enqueue_frame("a.jpg")
    proc.enqueue_frame("b.jpg")
    proc.enqueue_frame("c.jpg")
    proc.run_once()
    proc.run_once()
    proc.run_once()
    assert called == ["a.jpg", "b.jpg", "c.jpg"]


def test_safe_frame_output() -> None:
    frame = _temp_frame()
    payload = (
        '{"scene_description":"Baby is playing safely on the floor.",'
        '"baby_visible":true,"baby_activity":"playing","risk_level":"low",'
        '"risk_reason":"No immediate hazard visible.","observations":["baby on floor"],'
        '"recommended_action":"Continue monitoring"}'
    )
    proc = FrameLLMProcessor(enable_analysis=True, client=_Client(payload), max_retries=1)
    out = proc.process_frame(str(frame))
    assert out["scene_description"]
    assert out["baby_visible"] is True
    assert out["baby_activity"] == "playing"
    assert out["risk_level"] == "low"
    shutil.rmtree(frame.parent, ignore_errors=True)


def test_no_baby_visible_output() -> None:
    frame = _temp_frame()
    payload = (
        '{"scene_description":"No baby visible in this frame.",'
        '"baby_visible":false,"baby_activity":"no_baby_visible","risk_level":"low",'
        '"risk_reason":"No child visible.","observations":["empty crib"],'
        '"recommended_action":"Continue monitoring"}'
    )
    proc = FrameLLMProcessor(enable_analysis=True, client=_Client(payload), max_retries=1)
    out = proc.process_frame(str(frame))
    assert out["baby_visible"] is False
    assert out["baby_activity"] == "no_baby_visible"
    assert out["risk_level"] == "low"
    shutil.rmtree(frame.parent, ignore_errors=True)


def test_medium_high_risk_output() -> None:
    frame = _temp_frame()
    payload = (
        '{"scene_description":"Baby appears near bed edge.",'
        '"baby_visible":true,"baby_activity":"near_edge","risk_level":"high",'
        '"risk_reason":"Child is close to edge.","observations":["edge proximity"],'
        '"recommended_action":"Check immediately"}'
    )
    proc = FrameLLMProcessor(enable_analysis=True, client=_Client(payload), max_retries=1)
    out = proc.process_frame(str(frame))
    assert out["risk_level"] == "high"
    assert out["risk_reason"]
    shutil.rmtree(frame.parent, ignore_errors=True)


def test_empty_field_autofill_behavior() -> None:
    normalized = FrameLLMProcessor._normalize_payload(
        {
            "scene_description": "",
            "baby_visible": False,
            "baby_activity": "",
            "risk_level": "",
            "risk_reason": "",
            "observations": [],
            "recommended_action": "",
        }
    )
    assert normalized["scene_description"] == "No baby visible in the frame."
    assert normalized["baby_activity"] == "no_baby_visible"
    assert normalized["risk_reason"]
    assert normalized["recommended_action"] == "Continue monitoring"


def test_parse_failure_fallback_behavior() -> None:
    frame = _temp_frame()
    proc = FrameLLMProcessor(enable_analysis=True, client=_FailingClient(), max_retries=1)
    out = proc.process_frame(str(frame))
    assert out["used_llm"] is False
    assert out["scene_description"] == "A frame was captured, but detailed visual interpretation is unavailable."
    assert out["risk_reason"] == "The frame could not be analyzed reliably."
    shutil.rmtree(frame.parent, ignore_errors=True)
