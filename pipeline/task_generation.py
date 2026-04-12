from __future__ import annotations

import logging
from typing import Callable, Generic, TypeVar
from dataclasses import asdict, replace
from pathlib import Path

from app.language_registry import get_language_display_name
from app.settings import get_settings_store
from llm_gateway import LLMTextClient

from models import (
    ExplanationExercise,
    FillInTheBlankExercise,
    MacroPlanStep,
    MatchingExercise,
    MultipleChoiceExercise,
    TranslationExercise,
    VocabularyCard,
)
from .task_generation_parsers import (
    parse_explanation_exercise,
    parse_fill_in_the_blank_exercise,
    parse_matching_exercise,
    parse_multiple_choice_exercise,
    parse_translation_exercise,
)

logger = logging.getLogger(__name__)

ParsedExerciseT = TypeVar("ParsedExerciseT")
ExerciseParser = Callable[[str], ParsedExerciseT]


class TaskGenerator:
    def __init__(
        self,
        *,
        lesson_language: str,
        lerner_language: str,
        lerner_level: str,
    ) -> None:
        self._generator_by_exercise_id = {
            "explanation": ExplanationTaskGenerator(
                lesson_language=lesson_language,
                lerner_language=lerner_language,
                lerner_level=lerner_level,
            ),
            "filling": FillingTaskGenerator(
                lesson_language=lesson_language,
                lerner_language=lerner_language,
                lerner_level=lerner_level,
            ),
            "matching": MatchingTaskGenerator(
                lesson_language=lesson_language,
                lerner_language=lerner_language,
                lerner_level=lerner_level,
            ),
            "question": QuestionTaskGenerator(
                lesson_language=lesson_language,
                lerner_language=lerner_language,
                lerner_level=lerner_level,
            ),
            "translation": TranslationTaskGenerator(
                lesson_language=lesson_language,
                lerner_language=lerner_language,
                lerner_level=lerner_level,
            ),
        }

    def generate_task(
        self,
        step: MacroPlanStep,
    ) -> dict | None:
        exercise_id = step.exercise_id.strip().lower()

        generator = self._generator_by_exercise_id.get(exercise_id)
        if generator is None:
            logger.warning("Unsupported exercise_id in macro plan: %r", step.exercise_id)
            return None

        task = generator.generate_task(
            description=step.description,
            targets=step.targets,
        )
        if hasattr(task, "mode"):
            task = replace(task, mode=step.mode)

        payload = asdict(task)
        payload["lesson_description"] = step.description
        payload["lesson_targets"] = [card.lexeme for card in step.targets]
        # logger.info(
        #     "Task payload ready\n"
        #     "macro step:\n%s\n"
        #     "payload:\n%s",
        #     step,  # TODO make this readable
        #     "\n".join(payload),
        # )
        return payload


class BaseTaskGenerator(Generic[ParsedExerciseT]):
    prompt_filename: str
    parser: ExerciseParser[ParsedExerciseT]
    output_format_prompt: str

    def __init__(
        self,
        *,
        lesson_language: str,
        lerner_language: str,
        lerner_level: str,
    ) -> None:
        self._lerner_language = lerner_language
        self._lerner_level = lerner_level
        settings = get_settings_store()
        self._text_client = LLMTextClient(
            model=settings.get_value("models/task_generation"),
            reasoning_effort=settings.get_value("pipeline/task_generation/reasoning_effort"),
            text_verbosity=settings.get_value("pipeline/task_generation/text_verbosity"),
            service_tier=settings.get_value("pipeline/task_generation/service_tier"),
        )

        common_prompt_path = Path("prompts") / lesson_language / "task_generation_common.txt"
        task_prompt_path = Path("prompts") / lesson_language / self.prompt_filename
        self._common_prompt_path = common_prompt_path
        self._task_prompt_path = task_prompt_path
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
        prompt = self._build_user_prompt(
            lerner_language=get_language_display_name(self._lerner_language),
            lerner_level=self._lerner_level,
            description=description,
            targets=targets,
        )
        logger.debug("Task generation request")

        response = self._text_client.generate_response(
            system_prompt=self._system_prompt,
            user_text=prompt,
        )
        response_text = response.text
        try:
            parsed = self.parser(response_text)
        except Exception as exc:
            logger.error(  # TODO Remove this exception handler and move this log directly to the parser
                "Task parsing failed\n"
                "exercise_id: N/A\n"  # TODO add exercise id
                "error: %s\n"
                "llm output:\n%s",
                exc,
                response_text,
            )
            raise

        payload = asdict(parsed)
        # logger.debug(
        #     "Task generation completed\n"
        #     "exercise_id: N/A\n"  # TODO add exercise id
        #     "parsed payload:%s\n",
        #     "\n".join(payload),  # TODO make this readable
        # )
        return parsed

    def _build_user_prompt(
        self,
        *,
        lerner_language: str,
        lerner_level,
        description: str,
        targets: list[VocabularyCard],
    ) -> str:
        """
        Builds a plain-text input prompt for the task content generator.
        """

        lines: list[str] = []
        lines.append(f"LERNER_LANGUAGE: {lerner_language}")
        lines.append(f"LERNER_LEVEL: {lerner_level}")
        lines.append(f"DESCRIPTION: {description}")
        lines.append(f"TARGETS:")
        for index, card in enumerate(targets, start=1):
            base = (
                f"U{index} | lexeme={card.lexeme} | meaning={card.meaning_english} | "
                f"pos={card.part_of_speech} | translation={card.translation}"
            )

            lines.append(base)
        
        return "\n".join(lines)
    

class ExplanationTaskGenerator(BaseTaskGenerator[ExplanationExercise]):
    prompt_filename = "explanation_task_generation.txt"
    parser = staticmethod(parse_explanation_exercise)


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
