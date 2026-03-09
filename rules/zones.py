from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


def load_zones(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    zones = data.get("zones", [])
    if not isinstance(zones, list):
        raise ValueError("zones must be a list")
    return zones


def point_in_polygon(point: tuple[float, float], polygon: list[list[float]]) -> bool:
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i, pi in enumerate(polygon):
        xi, yi = pi
        xj, yj = polygon[j]
        intersect = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi
        )
        if intersect:
            inside = not inside
        j = i
    return inside


def bbox_center(bbox: dict[str, int]) -> tuple[float, float]:
    return ((bbox["x1"] + bbox["x2"]) / 2.0, (bbox["y1"] + bbox["y2"]) / 2.0)


@dataclass(slots=True)
class ZoneManager:
    zones: list[dict[str, Any]]
    dwell: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ZoneManager":
        return cls(zones=load_zones(path))

    def evaluate_bbox(self, bbox: dict[str, int] | None) -> list[dict[str, Any]]:
        if not bbox:
            for name in list(self.dwell):
                self.dwell[name] = 0
            return []
        center = bbox_center(bbox)
        events: list[dict[str, Any]] = []
        active = set()
        for zone in self.zones:
            name = str(zone["name"])
            poly = zone["polygon"]
            if point_in_polygon(center, poly):
                self.dwell[name] = self.dwell.get(name, 0) + 1
                active.add(name)
                events.append(
                    {
                        "zone_name": name,
                        "zone_type": zone.get("type", "unknown"),
                        "dwell_frames": self.dwell[name],
                        "severity_weight": float(zone.get("severity_weight", 0.5)),
                    }
                )
        for name in list(self.dwell):
            if name not in active:
                self.dwell[name] = 0
        return events
