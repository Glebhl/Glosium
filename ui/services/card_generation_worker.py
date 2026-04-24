from __future__ import annotations

import logging
import time
from collections.abc import Callable

# from dev_fixtures import DevFixtureSettings
from models import VocabularyCard
from pipeline import VocabularyCardGenerator

logger = logging.getLogger(__name__)


class CardGenerationWorker:
    def __init__(
        self,
        *,
        query: str,
        lesson_language: str,
        translation_language: str,
    ) -> None:
        self._query = query
        self._lesson_language = lesson_language
        self._translation_language = translation_language

    def run(
        self,
        *,
        on_card_generated: Callable[[VocabularyCard], None],
        on_finished: Callable[[], None],
    ) -> None:
        started_at = time.perf_counter()
        first_card_logged = False

        try:
            card_generator = VocabularyCardGenerator(
                lesson_language=self._lesson_language,
                learner_language=self._translation_language,
            )
            for card in card_generator.stream_cards(self._query):
                if not first_card_logged:
                    logger.debug(
                        "First vocabulary card became available after %.2fs",
                        time.perf_counter() - started_at,
                    )
                    first_card_logged = True

                on_card_generated(card)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Vocabulary generation failed")
        finally:
            logger.debug(
                "Vocabulary generation worker finished in %.2fs",
                time.perf_counter() - started_at,
            )
            on_finished()
