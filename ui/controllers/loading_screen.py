from __future__ import annotations

import logging

from ui.services import LessonGenerationSession

logger = logging.getLogger(__name__)


class LoadingScreenController:
    def __init__(
        self,
        router,
        view,
        backend,
        cards,
        user_request,
        learner_level,
        lesson_language,
        translation_language,
        disabled_task_ids,
    ) -> None:
        self.url = "ui/views/loading_screen/index.html"
        self.router = router
        self.view = view
        self.backend = backend
        self._handlers = {
            "btn-click": self._on_btn_click,
        }
        self._cards = cards
        self._user_request = user_request
        self._learner_level = learner_level
        self._lesson_language = lesson_language
        self._learner_language = translation_language
        self._disabled_task_ids = tuple(str(task_id) for task_id in disabled_task_ids or [])
        self._generation_started = False
        self._generation_error_message: str | None = None
        self._lesson_session = None
        self._lesson_opened = False

    def on_load_finished(self) -> None:
        if self._generation_started:
            logger.debug("Ignoring repeated UI load finished event for loading screen")
            return

        self._generation_started = True
        self._start_lesson_generation()

    def on_ui_event(self, name: str, payload: dict) -> None:
        handler = self._handlers.get(name)
        if handler:
            handler(payload)

    def _on_btn_click(self, payload: dict) -> None:
        logger.debug("Clicked the button with the id='%s'", payload.get("id"))

        match payload.get("id"):
            case "stop":
                logger.info("Stop button clicked on loading screen; action is not implemented yet")

    def _start_lesson_generation(self) -> None:
        if self._lesson_session is not None:
            logger.warning("Lesson generation is already running; ignoring duplicate start request")
            return

        self._generation_error_message = None
        logger.info(
            "Opening stub lesson from loading screen: cards=%d lesson_language=%s translation_language=%s learner_level=%s user_request=%r",
            len(self._cards),
            self._lesson_language,
            self._learner_language,
            self._learner_level,
            self._user_request,
        )

        self._lesson_session = LessonGenerationSession(
            learner_level=self._learner_level,
            lesson_language=self._lesson_language,
            learner_language=self._learner_language,
            user_request=self._user_request,
            disabled_task_ids=self._disabled_task_ids,
        )
        self._lesson_session.subscribe_first_task_generated(self._handle_first_task_generated)
        self._lesson_session.start_generation(
            cards=self._cards,
            user_request=self._user_request,
        )

    def _handle_first_task_generated(self) -> None:
        if self._lesson_session is None:
            return

        from .lesson_flow import LessonFlowController

        self.router.replace_current(
            LessonFlowController,
            self._lesson_session,
            self._lesson_language,
            self._learner_language,
        )

    def _handle_lesson_generation_error(self, message: str) -> None:
        try:
            self._generation_error_message = message
            logger.error("Stub lesson flow failed: %s", message)
        except Exception:  # noqa: BLE001
            logger.exception("Unhandled exception while handling a stub lesson error")

    def _finish_lesson_generation(self) -> None:
        if self._generation_error_message:
            logger.warning("Stub lesson flow finished with an error: %s", self._generation_error_message)
