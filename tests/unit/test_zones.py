from pathlib import Path

from rules.zones import ZoneManager, point_in_polygon

ROOT = Path(__file__).resolve().parents[2]


def test_point_in_polygon_square() -> None:
    poly = [[0, 0], [10, 0], [10, 10], [0, 10]]
    assert point_in_polygon((5, 5), poly)
    assert not point_in_polygon((15, 5), poly)


def test_zone_manager_dwell() -> None:
    manager = ZoneManager.from_yaml(ROOT / "configs" / "zones.yaml")
    bbox = {"x1": 120, "y1": 90, "x2": 180, "y2": 150}
    events = manager.evaluate_bbox(bbox)
    assert events
    assert events[0]["dwell_frames"] == 1
    events2 = manager.evaluate_bbox(bbox)
    assert events2[0]["dwell_frames"] == 2
