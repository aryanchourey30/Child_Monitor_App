from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class Detection:
    label: str
    confidence: float
    bbox: dict[str, int]


class Detector:
    def __init__(self, backend: str = "mock", confidence_threshold: float = 0.4, model_path: str = "") -> None:
        self.backend = backend
        self.confidence_threshold = confidence_threshold
        self.model_path = model_path
        self._yolo = None
        if self.backend == "yolo":
            self._init_yolo()

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> "Detector":
        return cls(
            backend=str(cfg.get("backend", "mock")),
            confidence_threshold=float(cfg.get("confidence_threshold", 0.4)),
            model_path=str(cfg.get("model_path", "")),
        )

    def _init_yolo(self) -> None:
        try:
            from ultralytics import YOLO  # type: ignore
        except Exception as exc:
            raise RuntimeError("YOLO backend requested but ultralytics is unavailable.") from exc
        model = self.model_path or "yolov8n.pt"
        self._yolo = YOLO(model)

    def detect(self, frame: Any) -> dict[str, Any]:
        if self.backend == "yolo" and self._yolo is not None:
            return self._detect_yolo(frame)
        return self._detect_mock(frame)

    def _detect_mock(self, frame: Any) -> dict[str, Any]:
        h, w = frame.shape[:2]
        bbox = {"x1": int(w * 0.35), "y1": int(h * 0.25), "x2": int(w * 0.65), "y2": int(h * 0.9)}
        return {
            "baby_detected": True,
            "baby_bbox": bbox,
            "objects": [],
            "confidence": 0.75,
        }

    def _detect_yolo(self, frame: Any) -> dict[str, Any]:
        results = self._yolo(frame, verbose=False)[0]
        names = results.names
        best = None
        for box in results.boxes:
            cls_id = int(box.cls[0].item())
            label = names.get(cls_id, str(cls_id))
            conf = float(box.conf[0].item())
            if label not in {"person"} or conf < self.confidence_threshold:
                continue
            xyxy = box.xyxy[0].tolist()
            det = {
                "label": label,
                "confidence": conf,
                "bbox": {
                    "x1": int(xyxy[0]),
                    "y1": int(xyxy[1]),
                    "x2": int(xyxy[2]),
                    "y2": int(xyxy[3]),
                },
            }
            if best is None or det["confidence"] > best["confidence"]:
                best = det
        return {
            "baby_detected": best is not None,
            "baby_bbox": best["bbox"] if best else {},
            "objects": [],
            "confidence": best["confidence"] if best else 0.0,
        }
