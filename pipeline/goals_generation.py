from __future__ import annotations

import json
import logging
from pathlib import Path

from app.language_registry import get_language_display_name
from app.settings import get_settings_store
from llm_gateway import LLMTextClient
from models import VocabularyCard


logger = logging.getLogger(__name__)


class LessonGoalGenerator:
    def __init__(
        self,
        *,
        lesson_language: str,
        learner_language: str,
        learner_level: str,
    ) -> None:
        self._learner_language = learner_language
        self._learner_level = learner_level

        settings = get_settings_store()
        self._text_client = LLMTextClient(
            model=settings.get_value("models/lesson_planning/goals"),
            reasoning_effort=settings.get_value("pipeline/lesson_planning/goals/reasoning_effort"),
            text_verbosity=settings.get_value(f"pipeline/lesson_planning/goals/text_verbosity"),
            service_tier=settings.get_value(f"pipeline/lesson_planning/goals/service_tier"),
        )

        prompt_path = Path("prompts") / lesson_language / "lesson_goal_generation.txt"
        self._prompt_path = prompt_path
        self._system_prompt = prompt_path.read_text(encoding="utf-8")
        logger.debug("Loaded lesson goals prompt from %s", prompt_path)

    def generate_goals(
        self,
        *,
        cards: list[VocabularyCard],
        user_request: str | None = None,
    ) -> list[str]:
        prompt = self._build_user_prompt(cards=cards, user_request=user_request)
        logger.info("Generating lesson goals...")

        response = self._text_client.generate_response(
            system_prompt=self._system_prompt,
            user_text=prompt,
        )
        response_text = response.text
        if not isinstance(response_text, str):
            raise TypeError(f"Lesson goals generator returned {type(response_text).__name__}, expected str.")

        try:
            goals = self._parse_goals(response_text)
        except Exception as exc:
            logger.error(
                "Lesson goals parsing failed\n"
                "error: %s\n"
                "llm output summary:\n%s",
                exc,
                response_text,
            )
            raise

        logger.debug(
            "Lesson goals generated\n"
            "goals:\n%s",
            "\n".join(goals)
        )
        return goals

    def _build_user_prompt(
        self,
        *,
        cards: list[VocabularyCard],
        user_request: str | None,
    ) -> str:
        lines: list[str] = [
            f"LEARNER_LANGUAGE: {get_language_display_name(self._learner_language)}"
            f"LEARNER_LEVEL: {self._learner_level}",
        ]

        if user_request:
            lines.extend([
                "LEARNER_REQUEST:",
                user_request,
                "",
            ])

        lines.append("LEARNING_UNITS:")
        for index, card in enumerate(cards, start=1):
            lines.append(
                f"U{index} | lexeme={card.lexeme} | meaning={card.meaning_english} | "
                f"pos={card.part_of_speech} | translation={card.translation}"
            )

        return "\n".join(lines)

    def _parse_goals(self, raw_text: str) -> list[str]:
        normalized = raw_text.strip()
        parsed = self._parse_json_array(normalized)
        if parsed is None:
            parsed = self._parse_lines(normalized)

        goals = [item.strip() for item in parsed if isinstance(item, str) and item.strip()]
        if not goals:
            raise ValueError("Lesson goals response did not contain any valid goal strings.")
        return goals

    def _parse_json_array(self, raw_text: str) -> list[str] | None:
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            start = raw_text.find("[")
            end = raw_text.rfind("]")
            if start < 0 or end <= start:
                return None
            try:
                payload = json.loads(raw_text[start : end + 1])
            except json.JSONDecodeError:
                return None

        if not isinstance(payload, list):
            return None
        return [str(item) for item in payload]

    def _parse_lines(self, raw_text: str) -> list[str]:
        goals: list[str] = []
        for raw_line in raw_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith(("-", "*")):
                line = line[1:].strip()
            goals.append(line)
        return goals
