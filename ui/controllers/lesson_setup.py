from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING

from models.card_models import VocabularyCard

logger = logging.getLogger(__name__)

CARDS_STATE_KEY = "lesson_setup/cards"
HINT_STATE_KEY = "lesson_setup/hint"
GENERATING_STATE_KEY = "lesson_setup/is_generating"

if TYPE_CHECKING:
    from dev_fixtures.settings import DevFixtureSettings

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


class LessonSetupController:
    def __init__(self, router, view, backend):
        self.url = "ui/views/lesson_setup/index.html"
        self.router = router
        self.view = view
        self.backend = backend
        self._handlers = {
            "btn-click": self._on_btn_click,
            "card-closed": self._on_card_closed,
        }
        self._cards: list[dict[str, object]] = []
        self._generation_error_message: str | None = None
        self._dev_fixtures: DevFixtureSettings | None = None
        self._is_generating = False
        self._hint = ""
        self._next_card_id = 0

        # Placeholders for settings tab
        self._lesson_language: str | None = None
        self._lerner_language: str | None = None
        self._lerner_level: str | None = None
        self._user_request: str | None = None
        self._publish_cards()
        self._publish_hint()
        self._publish_generating()

    def on_load_finished(self):
        self._cards = []
        self._generation_error_message = None
        self._is_generating = False
        self._user_request = None
        self._set_hint(f"Tip: {random.choice(hints)}")
        self._publish_cards()
        self._publish_generating()
        self._load_dev_cards_if_needed()

    def on_ui_event(self, name: str, payload: dict):
        handler = self._handlers.get(name)
        if handler:
            handler(payload)

    def _publish_cards(self) -> None:
        self.backend.publish_state(
            CARDS_STATE_KEY,
            [self._serialize_card_entry(entry) for entry in self._cards],
        )

    def _publish_hint(self) -> None:
        self.backend.publish_state(HINT_STATE_KEY, self._hint)

    def _publish_generating(self) -> None:
        self.backend.publish_state(GENERATING_STATE_KEY, self._is_generating)

    def _serialize_card_entry(self, entry: dict[str, object]) -> dict[str, str]:
        card = entry["card"]
        if not isinstance(card, VocabularyCard):
            raise TypeError(f"Unexpected card payload: {type(card).__name__}")

        return {
            "id": str(entry["id"]),
            "word": card.lexeme,
            "unit": card.lexical_unit,
            "part": card.part_of_speech,
            "level": card.level,
            "transcription": card.transcription,
            "translation": card.translation,
            "definition": card.meaning,
            "example": f'"{card.example}"',
        }

    def _append_card(self, card: VocabularyCard) -> None:
        self._next_card_id += 1
        card_entry = {
            "id": f"card-{self._next_card_id}",
            "card": card,
        }
        self._cards.append(card_entry)
        self._publish_cards()
        logger.debug("Added vocabulary card to UI: ui_card_id=%s lexeme=%s", card_entry["id"], card.lexeme)

    def _set_hint(self, hint: str) -> None:
        self._hint = hint
        self._publish_hint()

    def _set_card_generating(self, is_generating: bool) -> None:
        self._is_generating = is_generating
        self._publish_generating()

    def _load_dev_cards_if_needed(self) -> None:
        fixtures = self._get_dev_fixtures()
        if not fixtures.preload_cards:
            return

        try:
            for card in fixtures.load_cards():
                self._append_card(card)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to load dev cards fixture")

    def _start_card_generation(self, query: str) -> None:
        clean_query = (query or "").strip()
        if not clean_query:
            logger.warning("Not a valid query for card generation")
            return

        self._generation_error_message = None
        self._set_card_generating(True)
        self._ensure_lesson_settings()

        from ui.services.card_generation_worker import CardGenerationWorker

        worker = CardGenerationWorker(
            query=clean_query,
            lesson_language=self._lesson_language or "",
            translation_language=self._lerner_language or "",
        )
        worker.run(
            on_card_generated=self._handle_card_generated,
            on_generation_failed=self._handle_card_generation_error,
            on_finished=self._finish_card_generation
        )
        
    def _handle_card_generated(self, card: VocabularyCard) -> None:
        try:
            self._append_card(card)
        except Exception:  # noqa: BLE001
            logger.exception("Unhandled exception while appending a generated vocabulary card")

    def _handle_card_generation_error(self, message: str) -> None:
        try:
            self._generation_error_message = message
            logger.error("Vocabulary generation failed: %s", message)
        except Exception:  # noqa: BLE001
            logger.exception("Unhandled exception while handling a vocabulary generation error")

    def _finish_card_generation(self) -> None:
        try:
            self._set_card_generating(False)
            if self._generation_error_message:
                self._set_hint("Cards generation failed. Check the logs and try again.")
        except Exception:  # noqa: BLE001
            logger.exception("Unhandled exception while finalizing vocabulary generation")

    def _on_btn_click(self, payload: dict):
        logger.debug("Clicked the button with the id='%s'", payload.get("id"))

        match payload.get("id"):
            case "generate":
                self._start_card_generation(str(payload.get("prompt", "")))
            case "start_lesson":
                from ui.controllers.loading_screen import LoadingScreenController

                self._ensure_lesson_settings()
                for index, entry in enumerate(self._cards):
                    logger.debug("Lesson card %d: %s", index, entry["card"])

                logger.debug(
                    "Starting lesson generation with user_request=%r lerner_level=%s lesson_language=%s lerner_language=%s",
                    self._user_request,
                    self._lerner_level,
                    self._lesson_language,
                    self._lerner_language,
                )

                self.router.navigate_to(
                    LoadingScreenController,
                    [entry["card"] for entry in self._cards if isinstance(entry["card"], VocabularyCard)],
                    self._user_request,
                    self._lerner_level or "",
                    self._lesson_language or "",
                    self._lerner_language or "",
                )

    def _on_card_closed(self, payload: dict):
        card_id = str(payload.get("id", ""))

        for index, entry in enumerate(self._cards):
            if str(entry.get("id")) != card_id:
                continue

            self._cards.pop(index)
            self._publish_cards()
            logger.debug("The card %s was closed by the UI", card_id)
            return

        logger.warning("Received invalid UI card id: %r", card_id)

    def _get_dev_fixtures(self) -> DevFixtureSettings:
        if self._dev_fixtures is None:
            from dev_fixtures.settings import DevFixtureSettings

            self._dev_fixtures = DevFixtureSettings.from_env()
        return self._dev_fixtures

    def _ensure_lesson_settings(self) -> None:
        if self._lesson_language is not None and self._lerner_language is not None and self._lerner_level is not None:
            return

        from app.settings import get_settings_store

        settings = get_settings_store()
        self._lesson_language = settings.get_value("lesson/language") or ""
        self._lerner_language = settings.get_value("lesson/lerner_language") or ""
        self._lerner_level = settings.get_value("lesson/learner_level") or ""
