import logging
from pathlib import Path
from typing import Any

from llm_gateway import OpenAITextClient
from llm_gateway.openai_wrapper import REASONING_EFFORT_MEDIUM, TEXT_VERBOSITY_MEDIUM, SERVICE_TIER_FLEX

from .vocabulary_card import VocabularyCard
from language_converter import get_language_display_name

logger = logging.getLogger(__name__)


class MacroPlanner:
    def __init__(
        self,
        api_key: str,
        model: str,
        lesson_language: str,
        translation_language: str,
    ):
        self._lesson_language = lesson_language
        self._translation_language = translation_language
        self._text_client = OpenAITextClient(
            api_key=api_key,
            model="gpt-5.4-mini",
            # model=model,
            reasoning_effort=REASONING_EFFORT_MEDIUM,
            text_verbosity=TEXT_VERBOSITY_MEDIUM,
            service_tier=SERVICE_TIER_FLEX,
        )

        prompt_path = Path("prompts") / lesson_language / "plan_setup.txt"
        self._system_prompt = prompt_path.read_text(encoding="utf-8")

    def generate_plan(
        self,
        cards: list[VocabularyCard],
        *,
        user_request: str | None = None,
        lesson_size: str | None = None,
        target_step_count: int | None = None,
    ) -> list:
        payload = self._build_user_prompt(
            lesson_language=get_language_display_name(self._lesson_language),
            translation_language=get_language_display_name(self._translation_language),
            learning_units=cards,
            user_request=user_request,
            lesson_size=lesson_size,
            target_step_count=target_step_count
        )

        print(payload)

        macro_plan = self._text_client.generate_text(
            system_prompt=self._system_prompt,
            user_text=payload,
        )

        return macro_plan

    def _build_user_prompt(
        self,
        lesson_language: str,
        translation_language: str,
        learning_units: list[VocabularyCard],
        user_request: str | None = None,
        lesson_size: str | None = None,
        target_step_count: int | None = None,
    ) -> str:
        """
        Builds a plain-text input prompt for the macro lesson planner.

        learning_units format:
        [
            {
                "id": "U1",
                "type": "lexeme",
                "lexeme": "hit",
                "part_of_speech": "verb",
                "meaning": "strike something",
                # optional extra fields allowed
            }
        ]
        """

        lines: list[str] = []

        lines.append(f"LERNER_LANGUAGE: {translation_language}")
        lines.append("")

        if user_request:
            lines.append(f"USER_REQUEST: {user_request}")
            lines.append("")

        if lesson_size:
            lines.append(f"LESSON_SIZE: {lesson_size}")
        elif target_step_count:
            lines.append(f"LESSON_SIZE: {target_step_count} steps")

        if lesson_size or target_step_count:
            lines.append("")

        lines.append("LEARNING_UNITS:")
        for index, unit in enumerate(learning_units, start=1):
            base = (
                f"U{index} | lexeme | "
                f"{unit.lexeme} | {unit.meaning} "
                f"{unit.part_of_speech} | {unit.translation}"
            )

            lines.append(base)

        return "\n".join(lines)
