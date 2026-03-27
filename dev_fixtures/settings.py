from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.card_models import VocabularyCard


logger = logging.getLogger(__name__)

_ROOT_DIR = Path(__file__).resolve().parent.parent
_DEFAULT_FIXTURES_DIR = _ROOT_DIR / "dev_fixtures"
_DEFAULT_CARDS_PATH = _DEFAULT_FIXTURES_DIR / "cards.json"
_DEFAULT_MACRO_PLAN_PATH = _DEFAULT_FIXTURES_DIR / "macro_plan.txt"
_DEFAULT_LESSON_PATH = _DEFAULT_FIXTURES_DIR / "lesson.json"
_TRUE_VALUES = {"1", "true", "yes", "on"}


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in _TRUE_VALUES


def _resolve_path(raw_path: str | None, *, fallback: Path) -> Path:
    candidate = (raw_path or "").strip()
    if not candidate:
        return fallback

    path = Path(candidate)
    if not path.is_absolute():
        path = (_ROOT_DIR / path).resolve()
    return path


@dataclass(frozen=True, slots=True)
class DevFixtureSettings:
    preload_cards: bool
    cards_path: Path
    use_macro_plan_fixture: bool
    macro_plan_path: Path
    use_lesson_fixture: bool
    lesson_path: Path

    @classmethod
    def from_env(cls) -> "DevFixtureSettings":
        return cls(
            preload_cards=_env_flag("LEXIFORGE_DEV_CARDS"),
            cards_path=_resolve_path(os.getenv("LEXIFORGE_DEV_CARDS_FILE"), fallback=_DEFAULT_CARDS_PATH),
            use_macro_plan_fixture=_env_flag("LEXIFORGE_DEV_MACRO_PLAN"),
            macro_plan_path=_resolve_path(
                os.getenv("LEXIFORGE_DEV_MACRO_PLAN_FILE"),
                fallback=_DEFAULT_MACRO_PLAN_PATH,
            ),
            use_lesson_fixture=_env_flag("LEXIFORGE_DEV_LESSON"),
            lesson_path=_resolve_path(os.getenv("LEXIFORGE_DEV_LESSON_FILE"), fallback=_DEFAULT_LESSON_PATH),
        )

    def load_cards(self) -> list[VocabularyCard]:
        raw_data = json.loads(self.cards_path.read_text(encoding="utf-8"))
        if not isinstance(raw_data, list):
            raise ValueError("Cards fixture must be a JSON array.")
        cards = [self._build_card(item) for item in raw_data]
        logger.info("Loaded %d dev fixture cards from %s", len(cards), self.cards_path)
        return cards

    def load_macro_plan_text(self) -> str:
        macro_plan = self.macro_plan_path.read_text(encoding="utf-8").strip()
        if not macro_plan:
            raise ValueError("Macro plan fixture file is empty.")
        logger.info("Loaded macro plan fixture from %s", self.macro_plan_path)
        return macro_plan

    def load_lesson_plan(self) -> list[dict[str, Any]]:
        lesson_plan = json.loads(self.lesson_path.read_text(encoding="utf-8"))
        if not isinstance(lesson_plan, list):
            raise ValueError("Lesson fixture must be a JSON array.")
        logger.info("Loaded lesson fixture from %s", self.lesson_path)
        return lesson_plan

    def _build_card(self, raw_card: Any) -> VocabularyCard:
        if not isinstance(raw_card, dict):
            raise ValueError("Each card fixture entry must be a JSON object.")

        normalized = {str(key).strip().lower(): value for key, value in raw_card.items()}
        return VocabularyCard(
            lexeme=self._require_str(normalized, "lexeme"),
            lexical_unit=self._require_str(normalized, "lexical_unit"),
            part_of_speech=self._require_str(normalized, "part_of_speech"),
            level=self._require_str(normalized, "level"),
            translation=self._require_str(normalized, "translation"),
            transcription=self._require_str(normalized, "transcription"),
            meaning=self._require_str(normalized, "meaning"),
            example=self._require_str(normalized, "example"),
        )

    def _require_str(self, payload: dict[str, Any], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Card fixture field {key!r} must be a non-empty string.")
        return value.strip()
