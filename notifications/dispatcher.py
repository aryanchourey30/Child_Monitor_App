from __future__ import annotations

import logging
from typing import Any

from rules.cooldowns import CooldownGate

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    def __init__(self, cfg: dict[str, Any]) -> None:
        self.enabled = bool(cfg.get("enabled", True))
        self.dry_run = bool(cfg.get("dry_run", True))
        self.channels = list(cfg.get("channels", []))
        self.cooldown = CooldownGate(int(cfg.get("cooldown_sec", 30)))

    def send(self, payload: dict[str, Any]) -> bool:
        if not self.enabled:
            return False
        key = f"{payload.get('event_type')}:{payload.get('severity')}"
        if not self.cooldown.allow(key):
            return False
        message = self._choose_message(payload)
        enriched_payload = dict(payload)
        enriched_payload["message"] = message
        if self.dry_run:
            logger.info("DRY-RUN notification: %s", enriched_payload)
            return True
        # Production providers can be added in telegram.py/emailer.py.
        logger.info("Notification sent via %s: %s", self.channels, enriched_payload)
        return True

    @staticmethod
    def _choose_message(payload: dict[str, Any]) -> str:
        caregiver = payload.get("caregiver_message")
        if isinstance(caregiver, str) and caregiver.strip():
            return caregiver
        explanation = payload.get("explanation")
        if isinstance(explanation, str) and explanation.strip():
            return explanation
        severity = payload.get("severity", "low")
        score = payload.get("risk_score", 0.0)
        return f"GuardianBaby alert: severity={severity}, score={score}"
