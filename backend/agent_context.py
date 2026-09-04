"""Services made available to background agents at runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AgentContext:
    """Optional runtime services; tests may provide lightweight fakes."""

    task_manager: Any = None
    google_account: Any = None
    notification_manager: Any = None
    plugin_manager: Any = None
    openclaw_bridge: Any = None
    kasa_agent: Any = None
    printer_agent: Any = None
