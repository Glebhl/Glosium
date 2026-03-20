from __future__ import annotations

import json
import logging
import os
import random
import time
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal, Slot

from pages.lesson import LessonController
from pipeline.vocab import VocabularyCard, VocabularyCardGenerator

logger = logging.getLogger(__name__)

LLM_MODEL = "gpt-5-mini"

hints = [
    "specify level, topic, and format (<code>with examples</code>, <code>phrasal verbs</code>, <code>medical terms</code>).",
    "specify your level and goal (<code>A2 travel</code>, <code>B1 conversation</code>).",
    "choose a topic and format (<code>food vocabulary</code>).",
    "include the situation (<code>at the airport</code>, <code>doctor appointment</code>).",
    "request difficulty and pace (<code>simple sentences</code>, <code>challenge me</code>).",
    "focus on a grammar point (<code>present perfect</code>, <code>conditionals</code>).",
    "set the number of new words (<code>teach 10 words</code>, <code>only 5 new words</code>).",
    "pick a register (<code>formal</code>, <code>casual</code>, <code>business</code>).",
    "ask for phrasal verbs by theme (<code>phrasal verbs for work</code>, <code>for travel</code>).",
    "include your interests (<code>music</code>, <code>gaming</code>, <code>fitness</code>).",
]


class VocabularyGenerationWorker(QObject):
    card_generated = Signal(object)
    generation_failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        *,
        api_key: str,
        query: str,
        lesson_language: str,
        translation_language: str,
        model: str,
    ) -> None:
        super().__init__()
        self._api_key = api_key
        self._query = query
        self._lesson_language = lesson_language
        self._translation_language = translation_language
        self._model = model

    @Slot()
    def run(self) -> None:
        started_at = time.perf_counter()
        first_card_logged = False
        try:
            card_generator = VocabularyCardGenerator(
                api_key=self._api_key,
                lesson_language=self._lesson_language,
                translation_language=self._translation_language,
                model=self._model,
            )
            for card in card_generator.stream_cards(self._query):
                if not first_card_logged:
                    logger.debug(
                        "First vocabulary card became available after %.2fs",
                        time.perf_counter() - started_at,
                    )
                    first_card_logged = True
                self.card_generated.emit(card)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Vocabulary generation failed")
            self.generation_failed.emit(str(exc))
        finally:
            logger.debug(
                "Vocabulary generation worker finished in %.2fs",
                time.perf_counter() - started_at,
            )
            self.finished.emit()


class VocabularySetupController(QObject):
    def __init__(self, router, view, backend):
        super().__init__()
        self.url = r"\UI\vocab_setup\index.html"
        self.router = router
        self.view = view
        self.backend = backend
        self.handlers = {
            "btn-click": self._on_btn_click,
            "card-closed": self._on_card_closed,
        }
        self.cards_by_ui_id: dict[str, VocabularyCard] = {}
        self._next_ui_card_id = 0
        self._api_key = os.getenv("OPENAI_API_KEY") or ""
        self._lesson_language = "en"
        self._translation_language = "ru"
        self._worker_thread: QThread | None = None
        self._worker: VocabularyGenerationWorker | None = None
        self._generation_error_message: str | None = None

    def on_load_finished(self):
        self.cards_by_ui_id = {}
        self._next_ui_card_id = 0
        self._set_hint(f"Tip: {random.choice(hints)}")
        self._set_generating(False)

    def on_ui_event(self, name: str, payload: dict):
        handler = self.handlers.get(name)
        if handler:
            handler(payload)

    def _run_js(self, function_name: str, *args: Any) -> None:
        serialized_args = ", ".join(json.dumps(arg) for arg in args)
        self.view.page().runJavaScript(f"{function_name}({serialized_args});")

    def _allocate_ui_card_id(self) -> str:
        card_id = str(self._next_ui_card_id)
        self._next_ui_card_id += 1
        return card_id

    def _append_card_to_ui(self, card: VocabularyCard) -> None:
        ui_card_id = self._allocate_ui_card_id()
        self.cards_by_ui_id[ui_card_id] = card

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

    def _set_generating(self, is_generating: bool) -> None:
        self._run_js("setGenerating", is_generating)

    def _start_card_generation(self, query: str) -> None:
        clean_query = (query or "").strip()
        if not clean_query:
            return

        if self._worker_thread is not None:
            return

        self._generation_error_message = None
        self._set_generating(True)

        self._worker_thread = QThread(self)
        self._worker = VocabularyGenerationWorker(
            api_key=self._api_key,
            model=LLM_MODEL,
            query=clean_query,
            lesson_language=self._lesson_language,
            translation_language=self._translation_language,
        )
        self._worker.moveToThread(self._worker_thread)

        self._worker_thread.started.connect(self._worker.run)
        self._worker.card_generated.connect(self._handle_card_generated)
        self._worker.generation_failed.connect(self._handle_generation_error)
        self._worker.finished.connect(self._finish_generation)
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker_thread.finished.connect(self._worker_thread.deleteLater)
        self._worker_thread.finished.connect(self._cleanup_worker_refs)
        self._worker_thread.start()

    @Slot(object)
    def _handle_card_generated(self, card: VocabularyCard) -> None:
        self._append_card_to_ui(card)

    @Slot(str)
    def _handle_generation_error(self, message: str) -> None:
        self._generation_error_message = message
        logger.error("Vocabulary generation failed: %s", message)

    @Slot()
    def _finish_generation(self) -> None:
        self._set_generating(False)
        if self._generation_error_message:
            self._set_hint("Generation failed. Check the logs and try again.")

    @Slot()
    def _cleanup_worker_refs(self) -> None:
        self._worker = None
        self._worker_thread = None

    def _on_btn_click(self, payload: dict):
        logger.debug("Clicked the button with the id='%s'", payload.get("id"))

        match payload.get("id"):
            case "generate":
                self.view.page().runJavaScript(
                    "getPromtText();",
                    self._start_card_generation,
                )
            case "start_lesson":
                self.router.navigate_to(LessonController)

    def _on_card_closed(self, payload: dict):
        card_id = str(payload.get("id", ""))
        if card_id in self.cards_by_ui_id:
            self.cards_by_ui_id.pop(card_id)
            logger.debug("The card %s was closed by the UI", card_id)
