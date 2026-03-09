from __future__ import annotations

from typing import Any

from agent.summarizer import EventSummarizer


class _FailingResponses:
    def create(self, **_: Any) -> Any:
        raise RuntimeError("simulated api failure")


class _FailingClient:
    def with_options(self, **_: Any) -> "_FailingClient":
        return self

    @property
    def responses(self) -> _FailingResponses:
        return _FailingResponses()


def test_build_event_payload_contains_grounded_fields() -> None:
    state = {
        "risk_level": "high",
        "risk_score": 0.82,
        "state_label": "unsafe_exploration",
        "zone_events": [{"zone_name": "bed_edge"}],
        "fall_risk_score": 0.8,
        "wet_floor_score": 0.1,
        "fire_smoke_score": 0.0,
        "ingestion_risk_score": 0.0,
        "explanation": "near edge zone; forward lean elevated",
    }
    payload = EventSummarizer.build_event_payload(state)
    assert payload["zone"] == "bed_edge"
    assert payload["risk_level"] == "high"
    assert payload["detector_scores"]["fall_risk_score"] == 0.8
    assert payload["contributing_factors"]


def test_summarizer_fallback_on_api_failure() -> None:
    summarizer = EventSummarizer(enable_summarization=True, client=_FailingClient(), max_retries=1)
    out = summarizer.summarize_event(
        {
            "event_type": "fall_risk",
            "risk_level": "high",
            "risk_score": 0.82,
            "state_label": "unsafe_exploration",
            "zone": "bed_edge",
            "contributing_factors": ["near edge zone"],
            "detector_scores": {"fall_risk_score": 0.82},
        }
    )
    assert out["fallback_used"] is True
    assert out["used_llm"] is False
    assert "bed_edge" in out["technical_summary"]
