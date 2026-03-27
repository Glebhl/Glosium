from __future__ import annotations

from pathlib import Path
from typing import Callable, Generic, TypeVar

from llm_gateway import OpenAITextClient
from llm_gateway.openai_wrapper import (
    REASONING_EFFORT_LOW,
    SERVICE_TIER_FLEX,
    TEXT_VERBOSITY_LOW,
)

from .task_generation_models import (
    FillInTheBlankExercise,
    MatchingExercise,
    MultipleChoiceExercise,
    TranslationExercise,
)
from .task_generation_parsers import (
    parse_fill_in_the_blank_exercise,
    parse_matching_exercise,
    parse_multiple_choice_exercise,
    parse_translation_exercise,
)
from pipeline import VocabularyCard
from app.language_registry import get_language_display_name

ParsedExerciseT = TypeVar("ParsedExerciseT")
ExerciseParser = Callable[[str], ParsedExerciseT]


class BaseTaskGenerator(Generic[ParsedExerciseT]):
    prompt_filename: str
    parser: ExerciseParser[ParsedExerciseT]

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        lesson_language: str,
        translation_language: str,
        lerner_level: str,
    ) -> None:
        self._translation_language = translation_language
        self._lerner_level = lerner_level
        self._text_client = OpenAITextClient(
            api_key=api_key,
            model=model,
            reasoning_effort=REASONING_EFFORT_LOW,
            text_verbosity=TEXT_VERBOSITY_LOW,
            service_tier=SERVICE_TIER_FLEX,
        )

        common_prompt_path = Path("prompts") / lesson_language / "task_generation_common.txt"
        task_prompt_path = Path("prompts") / lesson_language / self.prompt_filename
        self._system_prompt = "\n".join([
            common_prompt_path.read_text(encoding="utf-8"),
            task_prompt_path.read_text(encoding="utf-8"),
        ])

    def generate_task(
        self,
        *,
        description: str,
        targets: list[VocabularyCard],
    ) -> ParsedExerciseT:
        response = self._text_client.generate_text(
            system_prompt=self._system_prompt,
            user_text=self._build_user_prompt(
                translation_language=get_language_display_name(self._translation_language),
                lerner_level=self._lerner_level,
                description=description,
                targets=targets,
            ),
        )
        return self.parser(response)

    def _build_user_prompt(
        self,
        *,
        translation_language: str,
        lerner_level,
        description: str,
        targets: list[VocabularyCard],
    ) -> str:
        """
        Builds a plain-text input prompt for the task content generator.
        """

        lines: list[str] = []

        lines.append(f"LERNER_LANGUAGE: {translation_language}")
        lines.append("")

        lines.append(f"LERNER_LEVEL: {lerner_level}")
        lines.append("")

        lines.append(f"DESCRIPTION: {description}")
        lines.append("")

        lines.append(f"TARGETS:")
        for index, unit in enumerate(targets, start=1):
            base = (
                f"U{index} | lexeme | "
                f"{unit.lexeme} | {unit.meaning} "
                f"{unit.part_of_speech} | {unit.translation}"
            )

            lines.append(base)
        
        return "\n".join(lines)
    

class FillingTaskGenerator(BaseTaskGenerator[FillInTheBlankExercise]):
    prompt_filename = "filling_task_generation.txt"
    parser = staticmethod(parse_fill_in_the_blank_exercise)


class MatchingTaskGenerator(BaseTaskGenerator[MatchingExercise]):
    prompt_filename = "matching_task_generation.txt"
    parser = staticmethod(parse_matching_exercise)


class QuestionTaskGenerator(BaseTaskGenerator[MultipleChoiceExercise]):
    prompt_filename = "question_task_generation.txt"
    parser = staticmethod(parse_multiple_choice_exercise)


class TranslationTaskGenerator(BaseTaskGenerator[TranslationExercise]):
    prompt_filename = "translation_task_generation.txt"
    parser = staticmethod(parse_translation_exercise)
