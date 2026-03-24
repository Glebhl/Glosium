import json
import logging
from typing import Any, Callable, Optional

from PySide6.QtCore import QObject

from answer_matcher import answer_matcher

logger = logging.getLogger(__name__)

class LessonFlowController(QObject):
    """
    Controls lesson flow: loads tasks from a lesson plan, renders them via JS,
    and validates user answers using JS callbacks where needed.
    """

    def __init__(self, router, view, backend, lesson_plan):
        super().__init__()

        # Public fields
        self.url = r"\ui\views\lesson_flow\index.html"
        self.router = router
        self.view = view
        self.backend = backend

        # Save lesson plan
        self._lesson_plan = lesson_plan
        self._tasksTotal = len(self._lesson_plan)

        # UI event handlers
        self._handlers: dict[str, Callable[[dict], None]] = {
            "btn-click": self._handle_button_click,
        }

        # Lesson/task state
        self._task_index: int = 0  # 1-based index for UI; 0 means "not started"
        self._task_id: str = ""
        self._answers: list[str] = []

        # Task loaders and verifiers
        self._task_loaders: dict[str, Callable[[Any], None]] = {
            "explanation": self._load_explanation_task,
            "matching": self._load_matching_task,
            "translation": self._load_translation_task,
            "filling": self._load_filling_task,
            "question": self._load_question_task,
        }
        self._task_verifiers: dict[str, Callable[[], bool]] = {
            "explanation": None,  # None to skip verification
            "matching": None,
            "translation": self._verify_translation_task,
            "filling": self._verify_filling_task,
            "question": None,
        }

        logger.debug(
            "LessonController initialized: tasks_total=%d, url=%s",
            self._tasksTotal,
            self.url,
        )

    # --- External API (keep signatures for compatibility) ---

    def on_load_finished(self):
        """Called by the view when the HTML page has finished loading."""
        logger.debug("UI load finished, opening the first task")
        self._open_next_task()

    def on_ui_event(self, name: str, payload: dict):
        """Entry point for UI events from JS."""
        logger.debug("UI event received: name=%s payload=%s", name, payload)

        handler = self._handlers.get(name)
        if not handler:
            logger.warning("No handler registered for UI event: %s", name)
            return

        handler(payload)

    # --- UI handlers ---

    def _handle_button_click(self, payload: dict):
        button_id = payload.get("id")
        logger.debug("Button clicked: id=%s", button_id)

        if button_id == "skip":
            self._open_next_task()
            return

        if button_id == "continue":
            # If check passes, next task will be opened from _on_check_result().
            self._check_task_completion()
            return

        logger.warning("Unknown button id received: %s", button_id)

    # --- Lesson flow ---

    def _open_next_task(self) -> None:
        """Advance to the next task and render it in the UI."""
        self._task_index += 1

        if self._task_index > self._tasksTotal:
            logger.info("All tasks completed, navigating back")
            self.router.go_back()
            return

        self._set_step_ui(self._task_index, self._tasksTotal)

        task = self._lesson_plan[self._task_index - 1]
        self._task_id = task.get("task_id", "")
        content = task.get("content")
        self._answers = task.get("answers") or []

        loader = self._task_loaders.get(self._task_id)
        if not loader:
            logger.error("Unknown task type: %s (taskIndex=%d)", self._task_id, self._task_index)
            self._open_next_task()
            return

        logger.info("Opening task: index=%d/%d id=%s", self._task_index, self._tasksTotal, self._task_id)
        loader(content)

    def _set_step_ui(self, current_step: int, total_steps: int) -> None:
        """Update step indicator in the UI."""
        script = f"setStep({current_step}, {total_steps});"
        self.view.page().runJavaScript(script)

    def _check_task_completion(self) -> bool:
        """
        Trigger current task verification.
        Returns a boolean only for synchronous verifiers.
        """
        verifier = self._task_verifiers.get(self._task_id)
        if not verifier:
            logger.debug("No verifier registered for task type: %s. Validating the task", self._task_id)
            self._on_check_result(True)
            return

        logger.debug("Running verifier for task type: %s", self._task_id)
        return verifier()

    def _on_check_result(self, is_correct: bool) -> None:
        """Central place to handle verification result."""
        logger.info("Task check result: task_id=%s is_correct=%s", self._task_id, is_correct)
        if is_correct:
            self._open_next_task()

    # --- EXPLANATION task ---
    
    def _load_explanation_task(self, content: Any) -> None:
        """Render explanation page."""
        script = f'setTask("explanation", "next", {json.dumps(content)});'
        self.view.page().runJavaScript(script)

    # --- MATCHING task ---

    def _verify_matching_task(self) -> bool:
        """
        Matching is verified on JS side in the current implementation.
        Keeping behavior: assume correct and proceed.
        """
        logger.debug("Matching verification is handled by JS; assuming correct")
        self._on_check_result(True)
        return True

    def _load_matching_task(self, content: Any) -> None:
        """Render matching task."""
        script = f'setTask("matching", "next", {json.dumps(content)});'
        self.view.page().runJavaScript(script)

    # --- TRANSLATION task ---

    def _verify_translation_task(self) -> bool:
        """
        Translation verification: request answer from JS and validate asynchronously.
        Returns False because result is delivered via callback.
        """

        def on_answer_received(answer: Optional[str]) -> None:
            language_code = self._get_task_answer_language()
            match_result = answer_matcher.evaluate_text_answer(
                user_answer=answer,
                expected_answers=self._answers,
                language_code=language_code,
            )
            comparison_details = answer_matcher.explain_text_answer(
                user_answer=answer,
                expected_answers=self._answers,
                language_code=language_code,
            )

            logger.debug(
                "Translation answer received: raw_user_answer=%r expected=%s "
                "language_code=%s comparison=%s is_correct=%s",
                answer,
                self._answers,
                language_code,
                comparison_details,
                match_result.is_correct,
            )
            logger.debug(
                "Translation close match: is_close_match=%s closest_answer=%r",
                match_result.is_close_match,
                match_result.closest_answer,
            )

            self._translation_set_highlight(match_result.is_correct)
            self._on_check_result(match_result.is_correct)

        script = "getTranslationAnswerString();"
        self.view.page().runJavaScript(script, on_answer_received)
        return False

    def _translation_set_highlight(self, is_correct: bool) -> None:
        """Highlight translation field depending on correctness."""
        script = f"highlightTranslation({str(is_correct).lower()});"
        self.view.page().runJavaScript(script)

    def _load_translation_task(self, content: Any) -> None:
        """Render translation task."""
        script = f'setTask("translation", "next", {json.dumps(content)});'
        self.view.page().runJavaScript(script)

    # --- FILLING task ---

    def _verify_filling_task(self) -> bool:
        """
        Translation verification: request answer from JS and validate asynchronously.
        Returns False because result is delivered via callback.
        """

        def on_answer_received(answer: Optional[str]) -> None:
            user_answer = json.loads(answer or "[]")
            language_code = self._get_task_answer_language()
            match_result = answer_matcher.evaluate_sequence_answer(
                user_answers=user_answer,
                expected_answers=self._answers,
                language_code=language_code,
            )

            logger.debug(
                "Filling answer received: user_answer=%r expected=%s language_code=%s "
                "is_correct=%s",
                user_answer,
                self._answers,
                language_code,
                match_result.is_correct,
            )
            logger.debug(
                "Filling close match: is_close_match=%s closest_answer=%r",
                match_result.is_close_match,
                match_result.closest_answer,
            )

            self._filling_set_highlight(match_result.is_correct)
            self._on_check_result(match_result.is_correct)

        script = "getFillingAnswerString();"
        self.view.page().runJavaScript(script, on_answer_received)
        return False
    
    def _filling_set_highlight(self, is_correct):
        """Highlight filling field depending on correctness."""
        script = f"highlightFilling({str(is_correct).lower()});"
        self.view.page().runJavaScript(script)

    def _load_filling_task(self, content: Any) -> None:
        """Render filling task."""
        script = f'setTask("filling", "next", {json.dumps(content)});'
        self.view.page().runJavaScript(script)
    
    # --- QUESTION task ---

    def _load_question_task(self, content: Any) -> None:
        """Render question task."""
        script = f'setTask("question", "next", {json.dumps(content)});'
        self.view.page().runJavaScript(script)

    def _get_task_answer_language(self) -> Optional[str]:
        """
        Returns an optional answer language code for the current task.
        Supports several field names to keep lesson JSON flexible as more
        languages are introduced.
        """
        task = self._lesson_plan[self._task_index - 1]
        content = task.get("content") or {}

        return content.get("typing_language")
