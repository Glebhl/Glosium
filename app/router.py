from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .backend import Backend

logger = logging.getLogger(__name__)


class Router:
    """
    Simple page router for pywebview windows.
    """

    def __init__(self, window: Any, backend: Backend, project_root: Path):
        self.window = window
        self.backend = backend
        self.project_root = Path(project_root).resolve()
        self._stack: list[Any] = []

        self.backend.attach_window(window)
        self.window.events.loaded += self._on_view_loaded

    def navigate_to(self, controller_cls, *args, **kwargs) -> None:
        controller = controller_cls(self, self.window, self.backend, *args, **kwargs)

        current = self._current_controller()
        if current is not None:
            self._deactivate_controller(current)

        self._stack.append(controller)
        self._show_controller(controller)

        logger.info('Page navigation completed: url="%s"', controller.url)

    def set_initial_controller(self, controller_cls, *args, **kwargs) -> None:
        controller = controller_cls(self, self.window, self.backend, *args, **kwargs)

        if self._stack:
            current = self._current_controller()
            if current is not None:
                self._deactivate_controller(current)
            self._stack = []

        self._stack.append(controller)
        self._activate_controller(controller)

        logger.info('Initial page controller registered: url="%s"', controller.url)

    def go_back(self) -> None:
        if len(self._stack) <= 1:
            logger.warning("Cannot go back: history is empty or contains only one page")
            return

        current = self._stack.pop()
        previous = self._stack[-1]

        self._deactivate_controller(current)
        self._show_controller(previous)

        logger.info('Went back to previous page: url="%s"', previous.url)

    def replace_current(self, controller_cls, *args, **kwargs) -> None:
        controller = controller_cls(self, self.window, self.backend, *args, **kwargs)
        current = self._current_controller()

        if current is not None:
            self._deactivate_controller(current)
            self._stack[-1] = controller
        else:
            self._stack.append(controller)

        self._show_controller(controller)

        logger.info('Page replacement completed: url="%s"', controller.url)

    def _current_controller(self):
        return self._stack[-1] if self._stack else None

    def _activate_controller(self, controller) -> None:
        self.backend.set_ui_event_handler(controller.on_ui_event)
        logger.debug('Activated controller: url="%s"', controller.url)

    def _deactivate_controller(self, controller) -> None:
        self.backend.set_ui_event_handler(None)
        logger.debug('Deactivated controller: url="%s"', controller.url)

    def _show_controller(self, controller) -> None:
        self._activate_controller(controller)
        self.window.load_url(self._resolve_url(controller.url))
        logger.debug('Requested page load: url="%s"', controller.url)

    def _resolve_url(self, controller_url: str) -> str:
        relative_path = str(controller_url).lstrip("\\/")
        absolute_path = (self.project_root / relative_path).resolve()
        return absolute_path.as_uri()

    def _on_view_loaded(self) -> None:
        controller = self._current_controller()
        if controller is None:
            return

        try:
            controller.on_load_finished()
        except Exception:  # noqa: BLE001
            logger.exception('Unhandled exception in on_load_finished for url="%s"', controller.url)
