from __future__ import annotations

import json
import logging
from threading import Lock, Thread
from collections.abc import Callable, Mapping
from typing import Any

logger = logging.getLogger(__name__)


class Backend:
    """
    JS API bridge for pywebview.
    """

    def __init__(self) -> None:
        self._ui_event_handler: Callable[[str, dict[str, Any]], None] | None = None
        self._window: Any | None = None
        self._state: dict[str, Any] = {}
        self._state_lock = Lock()

    def attach_window(self, window: Any) -> None:
        self._window = window

    def set_ui_event_handler(
        self,
        handler: Callable[[str, dict[str, Any]], None] | None,
    ) -> None:
        self._ui_event_handler = handler

    def emit_event(
        self,
        event_name: str,
        payload: Mapping[str, Any] | None = None,
    ) -> dict[str, bool]:
        payload_dict: dict[str, Any] = dict(payload or {})
        logger.debug("UI event received: name=%s payload=%s", event_name, payload_dict)

        if self._ui_event_handler is None:
            logger.warning("UI event dropped because no handler is active: %s", event_name)
            return {"accepted": False}

        self._ui_event_handler(event_name, payload_dict)
        return {"accepted": True}

    def log(self, message: str) -> None:
        logger.debug("JS: %s", message)

    def publish_state(self, key: str, value: Any) -> None:
        with self._state_lock:
            self._state[key] = value
        self._push_state_to_ui(key, value)

    def set_state(self, key: str, value: Any) -> None:
        self.publish_state(key, value)

    def get_state(self, key: str) -> Any:
        with self._state_lock:
            return self._state.get(key)

    def clear_state(self, key: str) -> None:
        with self._state_lock:
            self._state.pop(key, None)
        self._push_state_to_ui(key, None)

    def _push_state_to_ui(self, key: str, value: Any) -> None:
        window = self._window
        if window is None:
            return

        key_json = json.dumps(key)
        value_json = json.dumps(value)
        script = (
            "window.appBridge && "
            f"window.appBridge.__deliverStateUpdate({key_json}, {value_json});"
        )

        try:
            window.evaluate_js(script)
        except Exception:  # noqa: BLE001
            logger.debug("Failed to push UI state for key=%s", key, exc_info=True)
