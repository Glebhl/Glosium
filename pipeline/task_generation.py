from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Generic, TypeVar
from dataclasses import asdict, replace

from app.settings import get_settings_store
from app.language_registry import get_language_display_name
from llm_gateway import OpenAITextClient

from models import MacroPlanStep
from .task_generation_parsers import (
    parse_fill_in_the_blank_exercise,
    parse_matching_exercise,
    parse_multiple_choice_exercise,
    parse_translation_exercise,
)
from models import VocabularyCard
from models import (
    FillInTheBlankExercise,
    MatchingExercise,
    MultipleChoiceExercise,
    TranslationExercise,
)

logger = logging.getLogger(__name__)

ParsedExerciseT = TypeVar("ParsedExerciseT")
ExerciseParser = Callable[[str], ParsedExerciseT]


class TaskGenerator:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        lesson_language: str,
        translation_language: str,
        lerner_level: str,
    ) -> None:
        self._generator_by_exercise_id = {
            "filling": FillingTaskGenerator(
                api_key=api_key,
                model=model,
                lesson_language=lesson_language,
                translation_language=translation_language,
                lerner_level=lerner_level,
            ),
            "matching": MatchingTaskGenerator(
                api_key=api_key,
                model=model,
                lesson_language=lesson_language,
                translation_language=translation_language,
                lerner_level=lerner_level,
            ),
            "question": QuestionTaskGenerator(
                api_key=api_key,
                model=model,
                lesson_language=lesson_language,
                translation_language=translation_language,
                lerner_level=lerner_level,
            ),
            "translation": TranslationTaskGenerator(
                api_key=api_key,
                model=model,
                lesson_language=lesson_language,
                translation_language=translation_language,
                lerner_level=lerner_level,
            ),
        }

    def generate_tasks(self, macro_plan: list[MacroPlanStep]) -> list[dict]:
        tasks: list[dict] = []

        for step in macro_plan:
            try:
                exercise_id = step.exercise_id.strip().lower()
                if exercise_id == "explanation":  # Not supported yet
                    continue

                generator = self._generator_by_exercise_id.get(exercise_id)
                if generator is None:
                    print(f"Unsupported exercise_id in macro plan: {step.exercise_id!r}")
                    continue

                task = generator.generate_task(
                    description=step.description,
                    targets=step.targets,
                )
                if hasattr(task, "mode"):
                    task = replace(task, mode=step.mode)

                tasks.append(asdict(task))
            except Exception as exc:
                print(exc)

        return tasks


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
        settings = get_settings_store()
        self._text_client = OpenAITextClient(
            api_key=api_key,
            model=model,
            reasoning_effort=settings.get_value("pipeline/task_generation/reasoning_effort"),
            text_verbosity=settings.get_value("pipeline/task_generation/text_verbosity"),
            service_tier=settings.get_value("pipeline/task_generation/service_tier"),
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
        logger.debug("task raw content:\n%s", response)
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
                f"{unit.lexeme} | {unit.meaning} | "
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
