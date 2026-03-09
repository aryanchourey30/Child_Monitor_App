from __future__ import annotations

from dataclasses import dataclass
import logging

from agent.graph import MonitorGraph
from app.settings import Settings, load_settings
from notifications.dispatcher import NotificationDispatcher
from persistence.db import EventRepository
from rules.zones import ZoneManager
from vision.detector import Detector


@dataclass(slots=True)
class AppContainer:
    settings: Settings
    repository: EventRepository
    zone_manager: ZoneManager
    detector: Detector
    notifier: NotificationDispatcher
    graph: MonitorGraph
    latest_state: dict


def create_container() -> AppContainer:
    settings = load_settings()
    logging.getLogger(__name__).info("Initializing app container with db=%s", settings.db_path)
    repository = EventRepository(settings.db_path)
    repository.init_db()
    zone_manager = ZoneManager.from_yaml(settings.zones_path)
    detector = Detector.from_config(settings.config.get("detector", {}))
    notifier = NotificationDispatcher(settings.notifications)
    graph = MonitorGraph(settings=config_or_empty(settings), zone_manager=zone_manager, notifier=notifier)
    return AppContainer(
        settings=settings,
        repository=repository,
        zone_manager=zone_manager,
        detector=detector,
        notifier=notifier,
        graph=graph,
        latest_state={},
    )


def config_or_empty(settings: Settings) -> dict:
    return settings.config if isinstance(settings.config, dict) else {}
