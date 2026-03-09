from __future__ import annotations

import base64
import json
import logging
import os
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from openai import APIError, APITimeoutError, OpenAI
except Exception:  # pragma: no cover
    APIError = Exception
    APITimeoutError = TimeoutError
    OpenAI = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

RISK_LEVELS = {"low", "medium", "high", "critical", "unknown"}
BABY_ACTIVITIES = {
    "playing",
    "sitting",
    "crawling",
    "standing",
    "sleeping",
    "calm",
    "restless",
    "near_edge",
    "unknown",
    "no_baby_visible",
}

FRAME_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "scene_description": {"type": "string"},
        "baby_visible": {"type": "boolean"},
        "baby_activity": {
            "type": "string",
            "enum": sorted(BABY_ACTIVITIES),
        },
        "risk_level": {
            "type": "string",
            "enum": sorted(RISK_LEVELS),
        },
        "risk_reason": {"type": "string"},
        "observations": {
            "type": "array",
            "items": {"type": "string"},
        },
        "recommended_action": {"type": "string"},
    },
    "required": [
        "scene_description",
        "baby_visible",
        "baby_activity",
        "risk_level",
        "risk_reason",
        "observations",
        "recommended_action",
    ],
}


class FrameLLMProcessor:
    """Sequential FIFO frame analyzer using OpenAI image input."""

    def __init__(
        self,
        *,
        enable_analysis: bool = True,
        model: str | None = None,
        timeout_seconds: float = 10.0,
        max_retries: int = 2,
        client: Any | None = None,
    ) -> None:
        self.enable_analysis = enable_analysis
        self.model = (model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")).strip()
        self.fallback_model = self.model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._queue: deque[str] = deque()
        self.client = client

        if self.client is None and self.enable_analysis and OpenAI is not None:
            api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
            if api_key:
                try:
                    self.client = OpenAI(api_key=api_key)
                except Exception as exc:  # pragma: no cover
                    logger.warning(
                        "Frame LLM client init failed; fallback mode enabled. err=%s",
                        exc,
                        exc_info=True,
                    )
                    self.enable_analysis = False
            else:
                logger.warning("OPENAI_API_KEY missing; frame LLM analysis disabled.")
                self.enable_analysis = False

    def enqueue_frame(self, frame_path: str) -> None:
        self._queue.append(frame_path)
        logger.info("Frame enqueued path=%s queue_size=%d", frame_path, len(self._queue))

    def process_next_frame(self) -> dict[str, Any] | None:
        if not self._queue:
            return None
        frame_path = self._queue.popleft()
        return self.process_frame(frame_path)

    def run_once(self) -> dict[str, Any] | None:
        return self.process_next_frame()

    def process_frame(
        self,
        frame_path: str,
        *,
        frame_meta: dict[str, Any] | None = None,
        model_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        frame_id = Path(frame_path).stem
        logger.info("Frame sent to OpenAI frame=%s model=%s", frame_path, self.model)

        if not self.enable_analysis or self.client is None:
            return self._fallback(frame_path, "LLM disabled or unavailable")

        p = Path(frame_path)
        if not p.exists():
            return self._fallback(frame_path, f"Frame file missing: {frame_path}")

        try:
            image_bytes = p.read_bytes()
        except Exception as exc:
            return self._fallback(frame_path, f"Frame read failed: {exc}")

        encoded = base64.b64encode(image_bytes).decode("utf-8")
        image_url = f"data:image/jpeg;base64,{encoded}"

        system_text = (
            "You are analyzing a single frame from a baby monitoring system. "
            "Your task is to describe what is visibly happening in the frame and estimate the apparent safety level. "
            "You must always return a useful, grounded interpretation of the frame, even when there is no major risk. "
            "If the child appears safe, describe the activity or calm state. "
            "If no child is visible, clearly state that. "
            "Use only visible evidence. Do not invent hidden events, diagnoses, or causes. "
            "Do not provide medical advice."
        )

        user_text = (
            "Analyze this frame and return ONLY valid JSON with exactly these fields:\n"
            "- scene_description\n"
            "- baby_visible\n"
            "- baby_activity\n"
            "- risk_level\n"
            "- risk_reason\n"
            "- observations\n"
            "- recommended_action\n\n"
            "Rules:\n"
            "- Return ONLY valid JSON\n"
            "- No markdown\n"
            "- No code fences\n"
            "- No extra text\n"
            "- observations must be an array of short strings\n"
            "- baby_activity must be one of: playing, sitting, crawling, standing, sleeping, calm, restless, near_edge, unknown, no_baby_visible\n"
            "- risk_level must be one of: low, medium, high, critical, unknown\n"
            "- If child is visible and appears safe, still describe the visible activity\n"
            "- If no risk is visible, set risk_level to low and explain why\n"
            "- If no baby is visible, set baby_visible=false and baby_activity=no_baby_visible\n"
            "- recommended_action must never be empty\n\n"
            f"Frame metadata: {json.dumps(frame_meta or {}, ensure_ascii=False)}\n"
            f"Model output: {json.dumps(model_result or {}, ensure_ascii=False)}"
        )

        for attempt in range(1, self.max_retries + 1):
            try:
                client = self.client.with_options(timeout=self.timeout_seconds)
                model_used = self.model
                response = client.responses.create(
                    model=self.model,
                    input=[
                        {
                            "role": "system",
                            "content": [{"type": "input_text", "text": system_text}],
                        },
                        {
                            "role": "user",
                            "content": [
                                {"type": "input_text", "text": user_text},
                                {
                                    "type": "input_image",
                                    "image_url": image_url,
                                    "detail": "auto",
                                },
                            ],
                        },
                    ],
                    max_output_tokens=300,
                )

                raw_text = self._extract_text(response)
                logger.debug("Raw model output frame=%s raw=%r", frame_path, raw_text)

                if not raw_text.strip():
                    self._log_empty_output_details(
                        response=response,
                        frame_path=frame_path,
                        model_name=self.model,
                        attempt=attempt,
                    )
                    fallback_text = self._retry_with_fallback_model(
                        client=client,
                        frame_path=frame_path,
                        system_text=system_text,
                        user_text=user_text,
                        image_url=image_url,
                    )
                    if fallback_text is not None:
                        raw_text = fallback_text
                        model_used = self.fallback_model
                    else:
                        raise ValueError("Empty output_text from model")

                payload = self._parse_model_output(raw_text)
                if payload is None:
                    payload = self._adapt_plain_text_output(raw_text)

                normalized = self._normalize_payload(payload, model_result=model_result)
                result = {
                    "frame_path": frame_path,
                    "frame_id": frame_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "scene_description": normalized["scene_description"],
                    "baby_visible": normalized["baby_visible"],
                    "baby_activity": normalized["baby_activity"],
                    "risk_level": normalized["risk_level"],
                    "risk_reason": normalized["risk_reason"],
                    "observations": normalized["observations"],
                    "recommended_action": normalized["recommended_action"],
                    "used_llm": True,
                    "model": model_used,
                    "error": None,
                }

                logger.info(
                    "Frame analyzed frame=%s baby_visible=%s activity=%s risk=%s desc=%s",
                    frame_path,
                    result["baby_visible"],
                    result["baby_activity"],
                    result["risk_level"],
                    result["scene_description"][:120],
                )
                return result

            except (APITimeoutError, APIError, ValueError, KeyError, TypeError) as exc:
                logger.warning(
                    "Frame LLM failed frame=%s attempt=%d err=%s",
                    frame_path,
                    attempt,
                    exc,
                    exc_info=True,
                )
                if attempt < self.max_retries:
                    time.sleep(0.2 * attempt)
                    continue
                return self._fallback(frame_path, str(exc))
            except Exception as exc:  # pragma: no cover
                logger.warning(
                    "Unexpected frame LLM error frame=%s attempt=%d err=%s",
                    frame_path,
                    attempt,
                    exc,
                    exc_info=True,
                )
                return self._fallback(frame_path, str(exc))

        return self._fallback(frame_path, "unknown error")

    def _retry_with_fallback_model(
        self,
        *,
        client: Any,
        frame_path: str,
        system_text: str,
        user_text: str,
        image_url: str,
    ) -> str | None:
        """Retry once with a fallback vision model when primary output is empty."""
        if not self.fallback_model or self.fallback_model == self.model:
            return None
        try:
            logger.info(
                "Retrying frame with fallback model frame=%s primary=%s fallback=%s",
                frame_path,
                self.model,
                self.fallback_model,
            )
            response = client.responses.create(
                model=self.fallback_model,
                input=[
                    {
                        "role": "system",
                        "content": [{"type": "input_text", "text": system_text}],
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": user_text},
                            {
                                "type": "input_image",
                                "image_url": image_url,
                                "detail": "auto",
                            },
                        ],
                    },
                ],
                max_output_tokens=300,
            )
            raw_text = self._extract_text(response)
            if raw_text.strip():
                logger.info(
                    "Fallback model returned output frame=%s model=%s",
                    frame_path,
                    self.fallback_model,
                )
                return raw_text
            self._log_empty_output_details(
                response=response,
                frame_path=frame_path,
                model_name=self.fallback_model,
                attempt=1,
            )
            return None
        except Exception as exc:
            logger.warning(
                "Fallback model retry failed frame=%s model=%s err=%s",
                frame_path,
                self.fallback_model,
                exc,
                exc_info=True,
            )
            return None

    def _log_empty_output_details(
        self,
        *,
        response: Any,
        frame_path: str,
        model_name: str,
        attempt: int,
    ) -> None:
        """Log response shape when model returns no extractable text."""
        status = self._safe_get(response, "status")
        incomplete = self._safe_get(response, "incomplete_details")
        content_types = self._collect_output_content_types(response)
        logger.warning(
            "Empty model output frame=%s model=%s attempt=%d status=%s content_types=%s incomplete=%s",
            frame_path,
            model_name,
            attempt,
            status,
            content_types,
            incomplete,
        )

    @staticmethod
    def _collect_output_content_types(response: Any) -> list[str]:
        output = getattr(response, "output", None)
        if output is None and isinstance(response, dict):
            output = response.get("output", [])
        output = output or []

        types: list[str] = []
        for item in output:
            content_items = getattr(item, "content", None)
            if content_items is None and isinstance(item, dict):
                content_items = item.get("content", [])
            content_items = content_items or []

            for content in content_items:
                ctype = getattr(content, "type", None)
                if ctype is None and isinstance(content, dict):
                    ctype = content.get("type")
                if isinstance(ctype, str) and ctype:
                    types.append(ctype)
        return types

    @staticmethod
    def _safe_get(obj: Any, key: str) -> Any:
        value = getattr(obj, key, None)
        if value is None and isinstance(obj, dict):
            return obj.get(key)
        return value

    @staticmethod
    def _extract_text(response: Any) -> str:
        text = getattr(response, "output_text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()

        chunks: list[str] = []
        output = getattr(response, "output", []) or []

        for item in output:
            content_items = getattr(item, "content", None)
            if content_items is None and isinstance(item, dict):
                content_items = item.get("content", [])
            content_items = content_items or []

            for content in content_items:
                ctype = getattr(content, "type", None)
                if ctype is None and isinstance(content, dict):
                    ctype = content.get("type")

                t = getattr(content, "text", None)
                if t is None and isinstance(content, dict):
                    t = content.get("text")

                if isinstance(t, str) and t.strip():
                    chunks.append(t.strip())
                    continue

                value = getattr(t, "value", None)
                if value is None and isinstance(t, dict):
                    value = t.get("value")
                if isinstance(value, str) and value.strip():
                    chunks.append(value.strip())
                    continue

                if ctype == "output_text" and isinstance(content, dict):
                    # Some SDK payloads expose output text as content["text"].
                    fallback_text = content.get("text")
                    if isinstance(fallback_text, str) and fallback_text.strip():
                        chunks.append(fallback_text.strip())

        return "\n".join(chunks).strip()

    @staticmethod
    def _parse_model_output(text: str) -> dict[str, Any] | None:
        if not text:
            return None

        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```json").removeprefix("```").strip()
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3].strip()

        try:
            data = json.loads(cleaned)
            return data if isinstance(data, dict) else None
        except Exception:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start == -1 or end == -1 or end <= start:
                return None
            try:
                data = json.loads(cleaned[start : end + 1])
                return data if isinstance(data, dict) else None
            except Exception:
                return None

    @staticmethod
    def _adapt_plain_text_output(text: str) -> dict[str, Any]:
        """Convert non-JSON model output into minimal structured payload."""
        cleaned = " ".join(text.split()).strip()
        lowered = cleaned.lower()

        baby_visible = "no baby" not in lowered and "not visible" not in lowered
        baby_activity = "unknown"
        for activity in (
            "playing",
            "sitting",
            "crawling",
            "standing",
            "sleeping",
            "calm",
            "restless",
            "near_edge",
        ):
            if activity in lowered:
                baby_activity = activity
                break
        if not baby_visible:
            baby_activity = "no_baby_visible"

        risk_level = "low"
        if "critical" in lowered:
            risk_level = "critical"
        elif "high" in lowered:
            risk_level = "high"
        elif "medium" in lowered:
            risk_level = "medium"
        elif "unknown" in lowered:
            risk_level = "unknown"

        scene_description = cleaned or "Frame received and analyzed."
        risk_reason = "Derived from model free-text output."
        if risk_level == "low":
            risk_reason = "No immediate visible safety concern in this frame."
        elif risk_level in {"medium", "high", "critical"}:
            risk_reason = "Model indicated possible safety concern."

        return {
            "scene_description": scene_description,
            "baby_visible": baby_visible,
            "baby_activity": baby_activity,
            "risk_level": risk_level,
            "risk_reason": risk_reason,
            "observations": [scene_description] if scene_description else [],
            "recommended_action": "Continue monitoring",
        }

    @staticmethod
    def _coerce_bool(value: Any, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            v = value.strip().lower()
            if v in {"true", "1", "yes", "y"}:
                return True
            if v in {"false", "0", "no", "n"}:
                return False
        if value is None:
            return default
        return bool(value)

    @staticmethod
    def _normalize_payload(
        payload: dict[str, Any],
        model_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        model_result = model_result or {}

        raw_baby_visible = payload.get(
            "baby_visible",
            model_result.get("subject_detected", False),
        )
        baby_visible = FrameLLMProcessor._coerce_bool(raw_baby_visible, default=False)

        baby_activity = str(
            payload.get("baby_activity", model_result.get("state_label", "unknown"))
        ).strip().lower()
        if baby_activity not in BABY_ACTIVITIES:
            baby_activity = "unknown"
        if not baby_visible:
            baby_activity = "no_baby_visible"

        risk_level = str(
            payload.get("risk_level", model_result.get("risk_level", "unknown"))
        ).strip().lower()
        if risk_level not in RISK_LEVELS:
            risk_level = "unknown"

        observations_raw = payload.get("observations", [])
        if isinstance(observations_raw, list):
            observations = [str(x).strip() for x in observations_raw if str(x).strip()]
        elif isinstance(observations_raw, str):
            observations = [observations_raw.strip()] if observations_raw.strip() else []
        else:
            observations = []

        scene_description = str(payload.get("scene_description", "")).strip()
        risk_reason = str(payload.get("risk_reason", "")).strip()
        recommended_action = str(payload.get("recommended_action", "")).strip()

        if not baby_visible:
            if not scene_description:
                scene_description = "No baby visible in the frame."
            if risk_level == "unknown":
                risk_level = "low"
            if not risk_reason:
                risk_reason = "No immediate visible risk because no baby is visible in the frame."
            if not recommended_action:
                recommended_action = "Continue monitoring"
        else:
            if not scene_description:
                if baby_activity in {
                    "playing",
                    "sitting",
                    "crawling",
                    "standing",
                    "sleeping",
                    "calm",
                    "restless",
                    "near_edge",
                }:
                    scene_description = f"Baby appears {baby_activity}."
                else:
                    scene_description = "Baby is visible in the frame."

            if not risk_reason:
                if risk_level in {"low", "unknown"}:
                    risk_level = "low"
                    risk_reason = "No immediate visible safety concern in this frame."
                else:
                    risk_reason = "Visible conditions suggest elevated safety concern."

            if not recommended_action:
                recommended_action = "Continue monitoring"

        if not scene_description:
            scene_description = "A frame was captured."
        if not risk_reason:
            risk_reason = "The frame was analyzed with limited confidence."
        if not recommended_action:
            recommended_action = "Continue monitoring"

        return {
            "scene_description": scene_description,
            "baby_visible": baby_visible,
            "baby_activity": baby_activity,
            "risk_level": risk_level,
            "risk_reason": risk_reason,
            "observations": observations,
            "recommended_action": recommended_action,
        }

    def _fallback(self, frame_path: str, error: str) -> dict[str, Any]:
        logger.warning("Frame analysis fallback frame=%s err=%s", frame_path, error)
        return {
            "frame_path": frame_path,
            "frame_id": Path(frame_path).stem,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scene_description": "A frame was captured, but detailed visual interpretation is unavailable.",
            "baby_visible": False,
            "baby_activity": "unknown",
            "risk_level": "unknown",
            "risk_reason": "The frame could not be analyzed reliably.",
            "observations": [],
            "recommended_action": "Continue monitoring",
            "used_llm": False,
            "model": None,
            "error": error,
        }
