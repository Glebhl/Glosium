import logging

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, QUrl, Qt
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel
from PySide6.QtWebEngineWidgets import QWebEngineView

from .backend import Backend
from .exception_logging import get_logged_bound_method, make_logged_callback

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
        self._pending_controller = None
        self._is_transitioning = False
        self._fade_duration_ms = 90

        self._transition_overlay = QLabel(self.view.parentWidget())
        self._transition_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._transition_overlay.setScaledContents(True)
        self._transition_overlay.hide()

        self._overlay_opacity_effect = QGraphicsOpacityEffect(self._transition_overlay)
        self._overlay_opacity_effect.setOpacity(1.0)
        self._transition_overlay.setGraphicsEffect(self._overlay_opacity_effect)

        self._fade_animation = QPropertyAnimation(
            self._overlay_opacity_effect,
            b"opacity",
            self._transition_overlay,
        )
        self._fade_animation.setDuration(self._fade_duration_ms)
        self._fade_animation.setEasingCurve(QEasingCurve.InOutQuad)
        self._fade_finished_handler = None

        self.view.loadFinished.connect(
            get_logged_bound_method(
                self,
                "_on_view_load_finished",
                logger=logger,
                message="Unhandled exception while processing QWebEngineView.loadFinished",
            )
        )

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

        use_fade = current is not None and not getattr(controller, "disable_transition", False)
        self._transition_to(controller, use_fade=use_fade)

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

        self._transition_to(previous, use_fade=True)

        logger.info('Went back to previous page: url="%s"', previous.url)

    # --- Internal helper methods ---

    def _current_controller(self):
        """Return the active controller or None if stack is empty."""
        return self._stack[-1] if self._stack else None

    def _activate_controller(self, controller):
        """Connect signals for the active controller."""
        # Connect UI event stream to the controller
        self.backend.uiEvent.connect(
            get_logged_bound_method(
                controller,
                "on_ui_event",
                logger=logger,
                message=f'Unhandled exception in controller UI event handler for "{controller.__class__.__name__}"',
            )
        )
        # Connect page load signal to controller hook
        self.view.loadFinished.connect(
            get_logged_bound_method(
                controller,
                "on_load_finished",
                logger=logger,
                message=f'Unhandled exception in controller load-finished handler for "{controller.__class__.__name__}"',
            )
        )
        logger.debug('Activated controller signals: url="%s"', controller.url)

    def _deactivate_controller(self, controller):
        """Disconnect signals for the previously active controller."""
        # Note: disconnecting can raise if already disconnected; keep behavior stable and safe.
        self._safe_disconnect(
            self.backend.uiEvent,
            get_logged_bound_method(controller, "on_ui_event", logger=logger),
            "backend.uiEvent",
        )
        self._safe_disconnect(
            self.view.loadFinished,
            get_logged_bound_method(controller, "on_load_finished", logger=logger),
            "view.loadFinished",
        )
        logger.debug('Deactivated controller signals: url="%s"', controller.url)

    def _load_controller_url(self, controller):
        """Load controller URL into the view."""
        self.view.setUrl(QUrl.fromLocalFile(controller.url))
        logger.debug('Requested page load: url="%s"', controller.url)

    def _transition_to(self, controller, use_fade: bool):
        """
        Switch the current page using a fading snapshot overlay.
        """
        self._pending_controller = controller

        if not use_fade:
            self._show_controller(controller)
            return

        if self._is_transitioning:
            self._fade_animation.stop()

        self._is_transitioning = True
        self._prepare_transition_overlay()
        self._load_pending_controller()
        logger.debug('Started overlay transition: url="%s"', controller.url)

    def _show_controller(self, controller):
        """Activate controller and request its page load."""
        self._activate_controller(controller)
        self._load_controller_url(controller)

    def _load_pending_controller(self):
        """Load the controller selected for the current transition."""
        controller = self._pending_controller
        if controller is None:
            self._is_transitioning = False
            return

        self._show_controller(controller)
        logger.debug('Fade-out completed, loading page: url="%s"', controller.url)

    def _on_view_load_finished(self, is_ok: bool):
        """Fade out the previous-page overlay after the new page has loaded."""
        if not self._is_transitioning:
            return

        controller = self._pending_controller
        logger.debug(
            'View load finished during transition: url="%s" ok=%s',
            controller.url if controller is not None else None,
            is_ok,
        )
        QTimer.singleShot(
            0,
            get_logged_bound_method(
                self,
                "_deferred_finish_transition",
                logger=logger,
                message="Unhandled exception during deferred router transition",
            ),
        )

    def _finish_transition(self):
        """Mark the current transition as complete."""
        controller = self._pending_controller
        self._pending_controller = None
        self._is_transitioning = False
        self._transition_overlay.hide()
        self._transition_overlay.clear()
        logger.debug(
            'Fade-in transition completed: url="%s"',
            controller.url if controller is not None else None,
        )

    def _deferred_finish_transition(self) -> None:
        """Run the fade-out after the view load signal has been processed."""
        self._run_fade(1.0, 0.0, self._finish_transition)

    def _run_fade(self, start_value: float, end_value: float, on_finished):
        """Configure and start opacity animation for the view."""
        if self._fade_finished_handler is not None:
            self._safe_disconnect(
                self._fade_animation.finished,
                self._fade_finished_handler,
                "fade_animation.finished",
            )
            self._fade_finished_handler = None

        self._overlay_opacity_effect.setOpacity(start_value)
        self._fade_animation.setStartValue(start_value)
        self._fade_animation.setEndValue(end_value)
        self._fade_finished_handler = make_logged_callback(
            on_finished,
            logger=logger,
            message="Unhandled exception in router fade animation callback",
        )
        self._fade_animation.finished.connect(self._fade_finished_handler)
        self._fade_animation.start()

    def _prepare_transition_overlay(self):
        """Capture the current page and place it over the view for a stable fade."""
        pixmap = self.view.grab()
        if pixmap.isNull():
            logger.debug("Transition overlay skipped because view snapshot is empty")
            return

        self._transition_overlay.setGeometry(self.view.geometry())
        self._transition_overlay.setPixmap(pixmap)
        self._overlay_opacity_effect.setOpacity(1.0)
        self._transition_overlay.show()
        self._transition_overlay.raise_()

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
