from __future__ import annotations

import json
import logging
import random
from typing import Any

from PySide6.QtCore import QObject, QThread, Qt, Slot

from app import get_settings_store
from dev_fixtures import DevFixtureSettings
from ui.controllers.loading_screen import LoadingScreenController
from ui.services import CardGenerationWorker
from models import VocabularyCard


logger = logging.getLogger(__name__)

hints = [
    "specify your level and goal (<code>A2 travel</code>, <code>B1 conversation</code>).",
    "choose a topic and format (<code>food vocabulary</code>, <code>short sentences</code>).",
    "include the situation (<code>at the airport</code>, <code>doctor appointment</code>).",
    "request difficulty and pace (<code>simple sentences</code>, <code>challenge me</code>).",
    "focus on a grammar point (<code>present perfect</code>, <code>conditionals</code>).",
    "set the number of new words (<code>teach 10 B2 words</code>, <code>5 new B1 words</code>).",
    "pick a register (<code>formal</code>, <code>casual</code>, <code>business</code>).",
    "ask for phrasal verbs by theme (<code>phrasal verbs for work</code>, <code>for travel</code>).",
    "include your interests (<code>music</code>, <code>gaming</code>, <code>fitness</code>).",
]


class LessonSetupController(QObject):
    def __init__(self, router, view, backend):
        super().__init__()
        self.url = r"\ui\views\lesson_setup\index.html"
        self.router = router
        self.view = view
        self.backend = backend
        self._handlers = {
            "btn-click": self._on_btn_click,
            "card-closed": self._on_card_closed,
        }
        self._cards: list[VocabularyCard] = []
        self._generation_error_message: str | None = None
        self._dev_fixtures = DevFixtureSettings.from_env()
        self._card_generation_thread: QThread | None = None
        self._card_generation_worker: CardGenerationWorker | None = None

        settings = get_settings_store()

        self._lesson_language = settings.get_value("lesson/language")
        self._translation_language = settings.get_value("lesson/lerner_language")
        self._lerner_level = settings.get_value("lesson/learner_level")
        self._user_request = None
        self._plan_generation_model = settings.get_value("models/lesson_planning")
        self._task_generation_model = settings.get_value("models/task_generation")

    def on_load_finished(self):
        self._cards = []
        self._set_hint(f"Tip: {random.choice(hints)}")
        self._set_card_generating(False)
        
        self._load_dev_cards_if_needed()

    def on_ui_event(self, name: str, payload: dict):
        handler = self._handlers.get(name)
        if handler:
            handler(payload)

    def _run_js(self, function_name: str, *args: Any) -> None:
        serialized_args = ", ".join(json.dumps(arg) for arg in args)
        self.view.page().runJavaScript(f"{function_name}({serialized_args});")

    def _append_card_to_ui(self, card: VocabularyCard) -> None:
        self._cards.append(card)
        ui_card_id = str(len(self._cards) - 1)

        self._run_js(
            "addCard",
            card.lexeme,
            card.lexical_unit,
            card.part_of_speech,
            card.level,
            card.transcription,
            card.translation,
            card.meaning,
            f"“{card.example}”",
            ui_card_id,
        )
        logger.debug("Added vocabulary card to UI: ui_card_id=%s lexeme=%s", ui_card_id, card.lexeme)

    def _set_hint(self, hint: str) -> None:
        self._run_js("setHint", hint)

    def _set_card_generating(self, is_generating: bool) -> None:
        self._run_js("setGenerating", is_generating)

    def _load_dev_cards_if_needed(self) -> None:
        if not self._dev_fixtures.preload_cards:
            return

        try:
            for card in self._dev_fixtures.load_cards():
                self._append_card_to_ui(card)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to load dev cards fixture")

    def _start_card_generation(self, query: str) -> None:
        clean_query = (query or "").strip()
        if not clean_query:
            logger.warning("Not a valid query for card generation")
            return

        if self._card_generation_thread is not None:
            logger.warning("Card generation is already running; ignoring duplicate start request")
            return

        self._generation_error_message = None
        self._user_request = clean_query
        self._set_card_generating(True)

        worker_thread = QThread(self)
        worker = CardGenerationWorker(
            query=clean_query,
            lesson_language=self._lesson_language,
            translation_language=self._translation_language,
        )
        self._card_generation_thread = worker_thread
        self._card_generation_worker = worker
        worker.moveToThread(worker_thread)

        worker_thread.started.connect(worker.run)
        worker.card_generated.connect(self._handle_card_generated, Qt.ConnectionType.QueuedConnection)
        worker.generation_failed.connect(self._handle_card_generation_error, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(self._finish_card_generation, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(worker_thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker_thread.finished.connect(worker_thread.deleteLater)
        worker_thread.finished.connect(self._clear_card_generation_references, Qt.ConnectionType.QueuedConnection)
        worker_thread.start()

    @Slot(object)
    def _handle_card_generated(self, card: VocabularyCard) -> None:
        try:
            self._append_card_to_ui(card)
        except Exception:  # noqa: BLE001
            logger.exception("Unhandled exception while appending a generated vocabulary card")

    @Slot(str)
    def _handle_card_generation_error(self, message: str) -> None:
        try:
            self._generation_error_message = message
            logger.error("Vocabulary generation failed: %s", message)
        except Exception:  # noqa: BLE001
            logger.exception("Unhandled exception while handling a vocabulary generation error")

    @Slot()
    def _finish_card_generation(self) -> None:
        try:
            self._set_card_generating(False)
            if self._generation_error_message:
                self._set_hint("Cards generation failed. Check the logs and try again.")
        except Exception:  # noqa: BLE001
            logger.exception("Unhandled exception while finalizing vocabulary generation")

    @Slot()
    def _clear_card_generation_references(self) -> None:
        self._card_generation_thread = None
        self._card_generation_worker = None

    def _on_btn_click(self, payload: dict):
        logger.debug("Clicked the button with the id='%s'", payload.get("id"))

        match payload.get("id"):
            case "generate":
                self.view.page().runJavaScript(
                    "getPromtText();",
                    self._start_card_generation,
                )
            case "start_lesson":
                for i, card in enumerate(self._cards):
                    logger.debug("Lesson card %d: %s", i, card)
                self.router.navigate_to(
                    LoadingScreenController,
                    self._cards.copy(),
                    self._user_request,
                    self._lerner_level,
                    self._lesson_language,
                    self._translation_language,
                    self._api_key,
                    self._plan_generation_model,
                    self._task_generation_model,
                )

    def _on_card_closed(self, payload: dict):
        card_id = str(payload.get("id", ""))
        try:
            card_index = int(card_id)
        except (TypeError, ValueError):
            logger.warning("Received invalid UI card id: %r", card_id)
            return

        if 0 <= card_index < len(self._cards):
            self._cards.pop(card_index)
            self._run_js("syncCardIds")
            logger.debug("The card %s was closed by the UI", card_id)
