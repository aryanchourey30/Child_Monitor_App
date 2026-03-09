from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

try:
    from openai import APIError, APITimeoutError, OpenAI
except Exception:  # pragma: no cover
    APIError = Exception
    APITimeoutError = TimeoutError
    OpenAI = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


def _safe_json_loads(value: str) -> dict[str, Any] | None:
    try:
        loaded = json.loads(value)
    except Exception:
        return None
    return loaded if isinstance(loaded, dict) else None


class EventSummarizer:
    """LLM-backed summarizer with deterministic fallback.

    This class must never affect deterministic safety decisions.
    """

    def __init__(
        self,
        *,
        enable_summarization: bool = True,
        model: str | None = None,
        timeout_seconds: float = 8.0,
        max_retries: int = 2,
        client: Any | None = None,
    ) -> None:
        self.enable_summarization = enable_summarization
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.client = client
        if self.client is None and self.enable_summarization and OpenAI is not None:
            api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
            if not api_key:
                logger.warning("OPENAI_API_KEY is missing; LLM summarization disabled (fallback only).")
                self.enable_summarization = False
                self.client = None
            else:
                try:
                    self.client = OpenAI(api_key=api_key)
                except Exception as exc:
                    logger.warning("OpenAI client initialization failed; fallback only. err=%s", exc)
                    self.enable_summarization = False
                    self.client = None

    @staticmethod
    def build_event_payload(state: dict[str, Any]) -> dict[str, Any]:
        zone = None
        zone_events = state.get("zone_events") or []
        if zone_events:
            zone = zone_events[0].get("zone_name")
        factors = []
        if state.get("debug", {}).get("fall_reasons"):
            factors.extend(state["debug"]["fall_reasons"])
        explanation = state.get("explanation")
        if explanation and isinstance(explanation, str):
            factors.extend([f.strip() for f in explanation.split(";") if f.strip()])
        if not factors:
            factors = ["no major contributors"]
        return {
            "event_type": state.get("event_type", "safety_risk"),
            "state_label": state.get("state_label", "unknown"),
            "risk_level": state.get("risk_level", "low"),
            "risk_score": float(state.get("risk_score", 0.0)),
            "zone": zone,
            "contributing_factors": factors[:4],
            "detector_scores": {
                "fall_risk_score": float(state.get("fall_risk_score", 0.0)),
                "wet_floor_score": float(state.get("wet_floor_score", 0.0)),
                "fire_smoke_score": float(state.get("fire_smoke_score", 0.0)),
                "ingestion_risk_score": float(state.get("ingestion_risk_score", 0.0)),
            },
        }

    @staticmethod
    def _fallback_summary(event_payload: dict[str, Any]) -> dict[str, Any]:
        level = str(event_payload.get("risk_level", "low")).lower()
        score = float(event_payload.get("risk_score", 0.0))
        zone = event_payload.get("zone") or "unknown_zone"
        state = event_payload.get("state_label", "unknown")
        factors = event_payload.get("contributing_factors") or []
        top = factors[0] if factors else "no major contributors"
        prefix = "Urgent" if level in {"high", "critical"} else "Alert"
        caregiver_message = (
            f"{prefix}: Baby safety risk is {level} ({score:.2f}) near {zone}. "
            f"Reason: {top}. Please check now."
        )
        technical_summary = (
            f"Event={event_payload.get('event_type', 'safety_risk')}, "
            f"zone={zone}, score={score:.2f}, state={state}, level={level}."
        )
        short_summary = f"{level.title()} risk {score:.2f} at {zone}"
        return {
            "short_summary": short_summary,
            "caregiver_message": caregiver_message,
            "technical_summary": technical_summary,
            "used_llm": False,
            "model": None,
            "fallback_used": True,
        }

    @staticmethod
    def _build_messages(event_payload: dict[str, Any]) -> tuple[str, str]:
        system_text = (
            "You are generating concise, safety-focused summaries for a baby-monitoring system. "
            "Use only the facts provided. Do not invent causes, diagnoses, or medical advice. "
            "Keep language calm, actionable, and short."
        )
        user_text = (
            "Generate strict JSON with keys caregiver_message and technical_summary.\n"
            f"event_type: {event_payload.get('event_type')}\n"
            f"risk_level: {event_payload.get('risk_level')}\n"
            f"risk_score: {event_payload.get('risk_score')}\n"
            f"state_label: {event_payload.get('state_label')}\n"
            f"zone: {event_payload.get('zone')}\n"
            f"contributing_factors: {event_payload.get('contributing_factors')}\n"
            f"detector_scores: {event_payload.get('detector_scores')}\n"
        )
        return system_text, user_text

    @staticmethod
    def _extract_output_text(response: Any) -> str:
        text = getattr(response, "output_text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()
        output = getattr(response, "output", None) or []
        chunks: list[str] = []
        for item in output:
            for content in getattr(item, "content", []) or []:
                candidate = getattr(content, "text", None)
                if isinstance(candidate, str) and candidate.strip():
                    chunks.append(candidate.strip())
        return "\n".join(chunks).strip()

    def summarize_event(self, event_payload: dict[str, Any], timeout_seconds: float = 8.0) -> dict[str, Any]:
        """Summarize an event payload with LLM, then fallback if needed."""
        if not self.enable_summarization or self.client is None:
            return self._fallback_summary(event_payload)

        timeout = timeout_seconds or self.timeout_seconds
        system_text, user_text = self._build_messages(event_payload)
        logger.info("LLM summarization attempt model=%s", self.model)
        for attempt in range(1, self.max_retries + 1):
            try:
                client = self.client.with_options(timeout=timeout)
                response = client.responses.create(
                    model=self.model,
                    input=[
                        {"role": "system", "content": [{"type": "input_text", "text": system_text}]},
                        {"role": "user", "content": [{"type": "input_text", "text": user_text}]},
                    ],
                    max_output_tokens=120,
                )
                raw = self._extract_output_text(response)
                data = _safe_json_loads(raw)
                if not data:
                    raise ValueError("LLM output is not valid JSON.")
                caregiver_message = str(data.get("caregiver_message", "")).strip()
                technical_summary = str(data.get("technical_summary", "")).strip()
                if not caregiver_message or not technical_summary:
                    raise ValueError("LLM output missing required fields.")
                logger.info("LLM summarization success model=%s", self.model)
                return {
                    "short_summary": caregiver_message[:120],
                    "caregiver_message": caregiver_message,
                    "technical_summary": technical_summary,
                    "used_llm": True,
                    "model": self.model,
                    "fallback_used": False,
                }
            except (APITimeoutError, APIError, ValueError, KeyError, TypeError) as exc:
                logger.warning("LLM summarization failed attempt=%d model=%s err=%s", attempt, self.model, exc)
                if attempt < self.max_retries:
                    time.sleep(0.2 * attempt)
                    continue
            except Exception as exc:  # pragma: no cover
                logger.warning("LLM unexpected failure model=%s err=%s", self.model, exc)
                break
        logger.info("LLM fallback activated")
        return self._fallback_summary(event_payload)
