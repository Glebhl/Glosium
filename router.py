import logging

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView

from backend import Backend

logger = logging.getLogger(__name__)


class Router:
    """
    Simple page router that switches between controller instances
    and manages signal connections for the active page.
    """

    def __init__(self, view: QWebEngineView, backend: Backend):
        self.view = view
        self.backend = backend
        self._stack = []  # controller history stack

    def navigate_to(self, controller_cls, *args, **kwargs):
        """
        Create a controller and navigate to its URL.
        """
        controller = controller_cls(self, self.view, self.backend, *args, **kwargs)

        logger.debug('Navigating to page: url="%s"', controller.url)

        current = self._current_controller()
        if current is not None:
            self._deactivate_controller(current)
            logger.debug('Deactivated previous page: url="%s"', current.url)

        self._stack.append(controller)
        logger.debug("Pushed new page to history stack (size=%d)", len(self._stack))

        self._activate_controller(controller)
        self._load_controller_url(controller)

        logger.info('Page navigation completed: url="%s"', controller.url)

    def go_back(self):
        """
        Navigate to the previous controller in history.
        """
        if len(self._stack) <= 1:
            logger.warning("Cannot go back: history is empty or contains only one page")
            return

        current = self._stack[-1]
        previous = self._stack[-2]

        logger.debug('Going back: from url="%s" to url="%s"', current.url, previous.url)

        self._deactivate_controller(current)
        self._stack.pop()
        logger.debug("Popped current page from history stack (size=%d)", len(self._stack))

        self._activate_controller(previous)
        self._load_controller_url(previous)

        logger.info('Went back to previous page: url="%s"', previous.url)

    # --- Internal helper methods ---

    def _current_controller(self):
        """Return the active controller or None if stack is empty."""
        return self._stack[-1] if self._stack else None

    def _activate_controller(self, controller):
        """Connect signals for the active controller."""
        # Connect UI event stream to the controller
        self.backend.uiEvent.connect(controller.on_ui_event)
        # Connect page load signal to controller hook
        self.view.loadFinished.connect(controller.on_load_finished)
        logger.debug('Activated controller signals: url="%s"', controller.url)

    def _deactivate_controller(self, controller):
        """Disconnect signals for the previously active controller."""
        # Note: disconnecting can raise if already disconnected; keep behavior stable and safe.
        self._safe_disconnect(self.backend.uiEvent, controller.on_ui_event, "backend.uiEvent")
        self._safe_disconnect(self.view.loadFinished, controller.on_load_finished, "view.loadFinished")
        logger.debug('Deactivated controller signals: url="%s"', controller.url)

    def _load_controller_url(self, controller):
        """Load controller URL into the view."""
        self.view.setUrl(QUrl.fromLocalFile(controller.url))
        logger.debug('Requested page load: url="%s"', controller.url)

    @staticmethod
    def _safe_disconnect(signal, slot, signal_name: str):
        """
        Disconnect a slot from a Qt signal safely.
        """
        try:
            signal.disconnect(slot)
        except (RuntimeError, TypeError) as exc:
            logger.debug(
                'Safe disconnect skipped: %s was not connected (reason="%s")',
                signal_name,
                exc,
            )
