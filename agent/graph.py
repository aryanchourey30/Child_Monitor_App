from __future__ import annotations

from typing import Any

from agent.nodes import (
    compose_alert_node,
    detect_node,
    fuse_node,
    generate_explanation_node,
    pose_node,
    safety_scores_node,
    track_node,
    zones_node,
)
from agent.state import MonitorState
from agent.summarizer import EventSummarizer
from vision.tracker import TrackState

try:
    from langgraph.graph import END, StateGraph
except Exception:  # pragma: no cover
    END = None
    StateGraph = None


class MonitorGraph:
    def __init__(self, settings: dict[str, Any], zone_manager: Any, notifier: Any) -> None:
        self.settings = settings
        self.zone_manager = zone_manager
        self.notifier = notifier
        self.tracker = TrackState()
        openai_cfg = settings.get("openai", {})
        self.summarizer = EventSummarizer(
            enable_summarization=bool(openai_cfg.get("enable_summarization", True)),
            model=str(openai_cfg.get("model", "gpt-4.1-mini")),
            timeout_seconds=float(openai_cfg.get("timeout_seconds", 8.0)),
            max_retries=int(openai_cfg.get("max_retries", 2)),
        )
        self.openai_timeout_seconds = float(openai_cfg.get("timeout_seconds", 8.0))
        self.backend = "sequential"
        self._current_frame: Any | None = None
        self._current_detector: Any | None = None
        self._compiled = self._build_langgraph_if_available()

    def _build_langgraph_if_available(self) -> Any:
        if StateGraph is None:
            return None
        graph = StateGraph(dict)
        graph.add_node("detect", self._node_detect)
        graph.add_node("track", self._node_track)
        graph.add_node("pose", self._node_pose)
        graph.add_node("zones", self._node_zones)
        graph.add_node("scores", self._node_scores)
        graph.add_node("fuse", self._node_fuse)
        graph.add_node("explain", self._node_explain)
        graph.add_node("alert", self._node_alert)
        graph.set_entry_point("detect")
        graph.add_edge("detect", "track")
        graph.add_edge("track", "pose")
        graph.add_edge("pose", "zones")
        graph.add_edge("zones", "scores")
        graph.add_edge("scores", "fuse")
        graph.add_edge("fuse", "explain")
        graph.add_edge("explain", "alert")
        graph.add_edge("alert", END)
        self.backend = "langgraph"
        return graph.compile()

    def _node_detect(self, state: MonitorState) -> MonitorState:
        if self._current_detector is None or self._current_frame is None:
            raise RuntimeError("Graph runtime context missing detector/frame in detect node.")
        return detect_node(state, detector=self._current_detector, frame=self._current_frame)

    def _node_track(self, state: MonitorState) -> MonitorState:
        return track_node(state, tracker=self.tracker)

    def _node_pose(self, state: MonitorState) -> MonitorState:
        if not state.get("baby_detected"):
            return state
        if self._current_frame is None:
            raise RuntimeError("Graph runtime context missing frame in pose node.")
        return pose_node(state, frame=self._current_frame)

    def _node_zones(self, state: MonitorState) -> MonitorState:
        return zones_node(state, zone_manager=self.zone_manager)

    def _node_scores(self, state: MonitorState) -> MonitorState:
        if self._current_frame is None:
            raise RuntimeError("Graph runtime context missing frame in scores node.")
        return safety_scores_node(state, frame=self._current_frame)

    def _node_fuse(self, state: MonitorState) -> MonitorState:
        return fuse_node(state, risk_cfg=self.settings.get("risk", {}))

    def _node_explain(self, state: MonitorState) -> MonitorState:
        return generate_explanation_node(
            state,
            summarizer=self.summarizer,
            timeout_seconds=self.openai_timeout_seconds,
        )

    def _node_alert(self, state: MonitorState) -> MonitorState:
        return compose_alert_node(state)

    def run(self, *, detector: Any, frame: Any, frame_id: str, timestamp: str) -> MonitorState:
        state: MonitorState = {"frame_id": frame_id, "timestamp": timestamp}
        self._current_frame = frame
        self._current_detector = detector
        try:
            if self._compiled is not None:
                out = self._compiled.invoke(state)
            else:
                out = detect_node(state, detector=detector, frame=frame)
                out = track_node(out, tracker=self.tracker)
                if out.get("baby_detected"):
                    out = pose_node(out, frame=frame)
                out = zones_node(out, zone_manager=self.zone_manager)
                out = safety_scores_node(out, frame=frame)
                out = fuse_node(out, risk_cfg=self.settings.get("risk", {}))
                out = generate_explanation_node(
                    out,
                    summarizer=self.summarizer,
                    timeout_seconds=self.openai_timeout_seconds,
                )
                out = compose_alert_node(out)
            return out
        finally:
            self._current_frame = None
            self._current_detector = None
