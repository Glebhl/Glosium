import logging
from typing import Any, Mapping, Optional

from PySide6.QtCore import QObject, Signal, Slot

logger = logging.getLogger(__name__)


class Backend(QObject):
    """
    Bridge between UI (JavaScript/QML) and Python.
    """
    uiEvent = Signal(str, dict)

    @Slot(str, "QVariantMap")
    def emitEvent(self, event_name: str, payload: Optional[Mapping[str, Any]]) -> None:
        """
        Converts payload into a plain Python dict and forwards it via uiEvent.
        """
        payload_dict: dict[str, Any] = dict(payload or {})
        logger.debug("UI event received: name=%s payload=%s", event_name, payload_dict)
        self.uiEvent.emit(event_name, payload_dict)

    @Slot(str)
    def log(self, message: str) -> None:
        """Receives debug messages from UI."""
        logger.debug("UI log: %s", message)
