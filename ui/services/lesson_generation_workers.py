from __future__ import annotations

import logging
import time

from PySide6.QtCore import QObject, Signal, Slot

from dev_fixtures import DevFixtureSettings
from pipeline import MacroPlanner, TaskGenerator, VocabularyCardGenerator
from models import VocabularyCard

logger = logging.getLogger(__name__)


class CardGenerationWorker(QObject):
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
                lerner_language=self._translation_language,
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


class LessonGenerationWorker(QObject):
    generation_failed = Signal(str)
    lesson_generated = Signal(object)
    finished = Signal()

    def __init__(
        self,
        *,
        api_key: str,
        plan_generation_model: str,
        task_generation_model: str,
        cards: list[VocabularyCard],
        user_request: str | None,
        lerner_level: str,
        lesson_language: str,
        translation_language: str,
    ) -> None:
        super().__init__()

        self._dev_fixtures = DevFixtureSettings.from_env()
        self._cards = cards
        self._user_request = user_request
        self._api_key = api_key
        self._plan_generation_model = plan_generation_model
        self._task_generation_model = task_generation_model
        self._lesson_language = lesson_language
        self._translation_language = translation_language
        self._lerner_level = lerner_level

    @Slot()
    def run(self) -> None:
        started_at = time.perf_counter()
        try:
            if self._dev_fixtures.use_lesson_fixture:
                lesson_plan = self._dev_fixtures.load_lesson_plan()
                logger.info("Using lesson fixture from %s", self._dev_fixtures.lesson_path)
            else:
                macro_planner = MacroPlanner(
                    api_key=self._api_key,
                    model=self._plan_generation_model,
                    lesson_language=self._lesson_language,
                    lerner_language=self._translation_language,
                    lerner_level=self._lerner_level,
                )
                task_generator = TaskGenerator(
                    api_key=self._api_key,
                    model=self._task_generation_model,
                    lesson_language=self._lesson_language,
                    translation_language=self._translation_language,
                    lerner_level=self._lerner_level,
                )
                macro_plan = macro_planner.generate_plan(
                    cards=self._cards,
                    user_request=self._user_request,
                )
                for i, task in enumerate(macro_plan):
                    logger.debug("%s. %s", i, task)
                logger.debug(
                    "Macro plan was generated in %.2fs",
                    time.perf_counter() - started_at,
                )
                started_at = time.perf_counter()
                lesson_plan = task_generator.generate_tasks(macro_plan)
                logger.debug(
                    "Tasks content was generated in %.2fs",
                    time.perf_counter() - started_at,
                )
            self.lesson_generated.emit(lesson_plan)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Lesson generation failed")
            self.generation_failed.emit(str(exc))
        finally:
            logger.debug(
                "Lesson generation worker finished in %.2fs",
                time.perf_counter() - started_at,
            )
            self.finished.emit()
