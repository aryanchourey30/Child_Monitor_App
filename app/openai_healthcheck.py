from __future__ import annotations

import logging
import os

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


def run_openai_healthcheck() -> None:
    """Run a one-time OpenAI connectivity check using Responses API."""
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        logger.info("OpenAI healthcheck skipped: OPENAI_API_KEY missing")
        return
    if OpenAI is None:
        logger.warning("OpenAI healthcheck failed: openai package not available")
        return

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    try:
        client = OpenAI()
        response = client.responses.create(
            model=model,
            input="Say hello in one short sentence.",
        )
        output_text = (getattr(response, "output_text", "") or "").strip()
        if output_text:
            logger.info("OpenAI healthcheck success: %s", output_text)
        else:
            logger.warning("OpenAI healthcheck failed: empty response output_text")
    except Exception as exc:
        logger.warning("OpenAI healthcheck failed: %s", exc)
