import json
import logging
from typing import Any, Callable, Optional

from PySide6.QtCore import QObject

logger = logging.getLogger(__name__)


class LessonController(QObject):
    """
    Controls lesson flow: loads tasks from a lesson plan, renders them via JS,
    and validates user answers using JS callbacks where needed.
    """

    def __init__(self, router, view, backend):
        super().__init__()

        # Public-ish fields kept for compatibility with existing codebase usage
        self.url = r"\UI\lesson\index.html"
        self.router = router
        self.view = view
        self.backend = backend

        # UI event handlers (external events -> internal methods)
        self.handlers: dict[str, Callable[[dict], None]] = {
            "btn-click": self._handle_button_click,
        }

        # Lesson/task state
        self.taskIndex: int = 0  # 1-based index for UI; 0 means "not started"
        self.taskID: str = ""
        self.answers: list[str] = []

        # Task loaders and verifiers
        self.task_loaders: dict[str, Callable[[Any], None]] = {
            "explanation": self._load_explanation_task,
            "matching": self._load_matching_task,
            "translation": self._load_translation_task,
            "filling": self._load_filling_task,
        }
        self.task_verifiers: dict[str, Callable[[], bool]] = {
            "explanation": None,
            "matching": None,
            "translation": self._verify_translation_task,
            "filling": self._verify_filling_task,
        }

        # Load lesson plan once
        with open("lesson_plans/lesson.json", encoding="utf-8") as file:
            self.lesson_plan: list[dict[str, Any]] = json.load(file)

        self.tasksTotal: int = len(self.lesson_plan)

        logger.debug(
            "LessonController initialized: tasks_total=%d, url=%s",
            self.tasksTotal,
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

        handler = self.handlers.get(name)
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
        self.taskIndex += 1

        if self.taskIndex > self.tasksTotal:
            logger.info("All tasks completed, navigating back")
            self.router.go_back()
            return

        self._set_step_ui(self.taskIndex, self.tasksTotal)

        task = self.lesson_plan[self.taskIndex - 1]
        self.taskID = task.get("task_id", "")
        content = task.get("content")
        self.answers = task.get("answers") or []

        loader = self.task_loaders.get(self.taskID)
        if not loader:
            logger.error("Unknown task type: %s (taskIndex=%d)", self.taskID, self.taskIndex)
            self._open_next_task()
            return

        logger.info("Opening task: index=%d/%d id=%s", self.taskIndex, self.tasksTotal, self.taskID)
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
        verifier = self.task_verifiers.get(self.taskID)
        if not verifier:
            logger.debug("No verifier registered for task type: %s. Validating the task", self.taskID)
            self._on_check_result(True)
            return

        logger.debug("Running verifier for task type: %s", self.taskID)
        return verifier()

    def _on_check_result(self, is_correct: bool) -> None:
        """Central place to handle verification result."""
        logger.info("Task check result: task_id=%s is_correct=%s", self.taskID, is_correct)
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
            user_answer = (answer or "").strip()
            expected = [str(a).lower() for a in self.answers]
            is_correct = user_answer.lower() in expected

            logger.debug(
                "Translation answer received: user_answer=%r expected=%s is_correct=%s",
                user_answer,
                expected,
                is_correct,
            )

            self._translation_set_highlight(is_correct)
            self._on_check_result(is_correct)

        script = "getTranslationAnswerString();"
        self.view.page().runJavaScript(script, on_answer_received)
        return False

    def _translation_set_highlight(self, is_correct: bool) -> None:
        """Highlight translation field depending on correctness."""
        script = f"highlightTraslation({str(is_correct).lower()});"
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
            user_answer = json.loads(answer or "")
            is_correct = user_answer == self.answers  # Expect exact matching

            logger.debug(
                "Filling answer received: user_answer=%r expected=%s is_correct=%s",
                user_answer,
                self.answers,
                is_correct,
            )

            self._filling_set_highlight(is_correct)
            self._on_check_result(is_correct)

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

