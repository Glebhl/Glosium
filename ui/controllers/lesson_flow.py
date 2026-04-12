from __future__ import annotations

import json
import logging
from typing import Any, Callable

from pipeline import AnswerMatcher
from pipeline.answer_matcher import CORRECT, MINOR_MISTAKE
from ui.services import is_filling_answer_correct, is_translation_answer_correct

logger = logging.getLogger(__name__)

PROGRESS_STATE_KEY = "lesson_flow/progress"
TASK_STATE_KEY = "lesson_flow/task"
VALIDATION_STATE_KEY = "lesson_flow/validation"


class LessonFlowController:
    """
    Lesson flow controller for prebuilt tasks only.
    Dynamic lesson generation and streaming are disabled.
    """

    def __init__(self, router, view, backend, lesson_session, lesson_language, translation_language):
        self.url = "ui/views/lesson_flow/index.html"
        self.disable_transition = True
        self.router = router
        self.view = view
        self.backend = backend

        self._lesson_session = lesson_session
        self._tasks_total = 0
        self._lesson_language = lesson_language
        self._translation_language = translation_language

        self._handlers: dict[str, Callable[[dict], None]] = {
            "btn-click": self._handle_button_click,
        }

        self._task_index = -1
        self._task_id = ""
        self._task_list: list[dict] = []
        self._task: dict[str, Any] = {}
        self.is_lesson_fully_generated = False
        self._pending_answer: Any = None
        self._task_state: dict[str, Any] | None = None
        self._validation_state: dict[str, Any] | None = None

        self._task_verifiers: dict[str, Callable[[], bool] | None] = {
            "translation": self._verify_translation_task,
            "filling": self._verify_filling_task,
        }

        self._answer_matcher = AnswerMatcher(
            lesson_language=self._lesson_language,
        )
        self._lesson_session.subscribe_new_task_generated(self._handle_new_task_generated)
        self._lesson_session.subscribe_new_stage_appeared(self._handle_new_stage_appeared)
        self._publish_progress()
        self._publish_task()
        self._publish_validation()

    def on_load_finished(self):
        pass

    def on_ui_event(self, name: str, payload: dict):
        handler = self._handlers.get(name)
        if not handler:
            logger.warning("No handler registered for UI event: %s", name)
            return

        handler(payload)

    def _publish_progress(self) -> None:
        self.backend.publish_state(PROGRESS_STATE_KEY, {
            "stepIndex": self._task_index + 1,
            "totalSteps": self._tasks_total + 1,
        })

    def _publish_task(self) -> None:
        self.backend.publish_state(TASK_STATE_KEY, self._task_state)

    def _publish_validation(self) -> None:
        self.backend.publish_state(VALIDATION_STATE_KEY, self._validation_state)
    
    def _show_loading_stage_screen(self) -> None:
        content = {
            "task_id": "loading",
            "title": "Generating the next part of the lesson",
            "message": "The next task will appear soon.",
        }

        self._render_task("loading", content)

    def _handle_button_click(self, payload: dict):
        button_id = payload.get("id")
        self._pending_answer = payload.get("answer")

        if button_id == "skip":
            self._open_task(self._task_index + 1)
            return

        if button_id == "continue":
            if self._check_task_completion():
                self._open_task(self._task_index + 1)
            return

        logger.warning("Unknown button id received: %s", button_id)
    
    def _handle_new_stage_appeared(self):
        logger.debug("The first task of a new stage has appeard")
        self._open_task(self._task_index + 1)

    def _handle_new_task_generated(self, task: dict, index: int, is_lesson_fully_generated) -> None:
        self._tasks_total = index
        self.is_lesson_fully_generated = is_lesson_fully_generated
        self._task_list.append(task)
        logger.debug("Recieved task #%s", index)
        self._publish_progress()

    def _open_task(self, task_index: int) -> None:
        if task_index > self._tasks_total:
            if not self.is_lesson_fully_generated:
                self._show_loading_stage_screen()
                self._lesson_session.request_next_stage(history=self._task_list)
            else:
                self.router.go_back()
            return
        
        self._task_index = task_index
        self._task = self._task_list[task_index]
        self._task_id = self._task.get("task_id") or "n/a"
        self._validation_state = None
        self._publish_progress()
        self._publish_validation()

        self._render_task(self._task_id, self._task)

    def _render_task(self, task_type: str, content: Any) -> None:
        logger.debug("Rendering a new task")
        self._task_state = {
            "taskIndex": self._task_index,
            "type": task_type,
            "direction": "next",
            "payload": content,
        }
        self._publish_task()

    def _set_task_validity(self, is_correct: bool) -> None:
        self._validation_state = {
            "isCorrect": bool(is_correct),
        }
        self._publish_validation()

    def _check_task_completion(self) -> bool:
        verifier = self._task_verifiers.get(self._task_id)
        if not verifier:
            self._on_check_result(True)
            return True

        return verifier()

    def _on_check_result(self, is_correct: bool) -> None:
        pass
        
    def _verify_translation_task(self) -> bool:
        answer = "" if self._pending_answer is None else str(self._pending_answer)
        expected_answers = self._task.get("answers") or []

        python_match = is_translation_answer_correct(
            user_answer=answer,
            expected_answers=expected_answers,
            language_code=self._translation_language,
        )
        if python_match:
            self._set_task_validity(True)
            self._on_check_result(True)
            return True

        match_result = self._answer_matcher.evaluate_text_answer(
            original_text=self._task.get("sentence"),
            user_answer=answer,
        )
        is_correct = match_result.evaluation in (CORRECT, MINOR_MISTAKE)
        self._set_task_validity(is_correct)
        self._on_check_result(is_correct)
        return is_correct

    def _verify_filling_task(self) -> bool:
        raw_answer = "[]" if self._pending_answer is None else str(self._pending_answer)

        user_answer = json.loads(raw_answer)

        expected_answers = self._task.get("answers") or []
        python_match = is_filling_answer_correct(
            user_answers=user_answer,
            expected_answers=expected_answers,
            language_code=self._lesson_language,
        )

        if python_match:
            self._set_task_validity(True)
            self._on_check_result(True)
            return True

        match_result = self._answer_matcher.evaluate_filling_answer(
            sentence_parts=self._task.get("sentence") or [],
            expected_answers=expected_answers,
            user_answers=user_answer,
        )
        is_correct = match_result.evaluation in (CORRECT, MINOR_MISTAKE)
        self._set_task_validity(is_correct)
        self._on_check_result(is_correct)
        return is_correct
