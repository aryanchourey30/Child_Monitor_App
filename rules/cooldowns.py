from __future__ import annotations

from datetime import datetime, timedelta, timezone


class CooldownGate:
    def __init__(self, cooldown_sec: int = 30) -> None:
        self.cooldown = timedelta(seconds=cooldown_sec)
        self._last: dict[str, datetime] = {}

    def allow(self, key: str) -> bool:
        now = datetime.now(timezone.utc)
        last = self._last.get(key)
        if last is None or (now - last) >= self.cooldown:
            self._last[key] = now
            return True
        return False
