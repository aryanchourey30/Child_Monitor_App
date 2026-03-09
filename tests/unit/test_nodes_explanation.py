from __future__ import annotations

from typing import Any

from agent.nodes import generate_explanation_node


class _MockSummarizer:
    @staticmethod
    def build_event_payload(state: dict[str, Any]) -> dict[str, Any]:
        return {"risk_level": state.get("risk_level", "low")}

    def summarize_event(self, event_payload: dict[str, Any], timeout_seconds: float = 8.0) -> dict[str, Any]:
        _ = (event_payload, timeout_seconds)
        return {
            "short_summary": "High risk near edge",
            "caregiver_message": "Urgent: Baby is near edge. Please check immediately.",
            "technical_summary": "Event=safety_risk, zone=bed_edge, score=0.80",
            "used_llm": True,
            "model": "gpt-4.1-mini",
            "fallback_used": False,
        }


def test_generate_explanation_node_updates_state() -> None:
    state = {"risk_level": "high", "risk_score": 0.8, "alert_needed": True}
    out = generate_explanation_node(state, summarizer=_MockSummarizer())
    assert out["explanation"] == "High risk near edge"
    assert out["caregiver_message"].startswith("Urgent:")
    assert out["llm_used"] is True
    assert out["llm_fallback_used"] is False
