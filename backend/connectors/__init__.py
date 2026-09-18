"""
F.R.I.D.A.Y connectors — external data sources and local device discovery.

Each connector fetches, normalises, and publishes to the central event bus.
"""
from .news_connector import NewsConnector, get_news_connector
from .science_connector import ScienceConnector, get_science_connector
from .local_device_connector import LocalDeviceConnector, get_local_device_connector
from ..actions.weather_report import weather_action as weather_report

__all__ = [
    "NewsConnector",
    "get_news_connector",
    "ScienceConnector",
    "get_science_connector",
    "LocalDeviceConnector",
    "get_local_device_connector",
    "weather_report",
]
