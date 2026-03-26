from __future__ import annotations

from dataclasses import asdict, replace

from .lesson_planning import MacroPlanStep
from .task_generation import (
    FillingTaskGenerator,
    MatchingTaskGenerator,
    QuestionTaskGenerator,
    TranslationTaskGenerator,
)


class TaskGenerator:
    def __init__(
        self,
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
            exercise_id = step.exercise_id.strip().lower()
            if exercise_id == "explanation":
                continue

            generator = self._generator_by_exercise_id.get(exercise_id)
            if generator is None:
                raise ValueError(f"Unsupported exercise_id in macro plan: {step.exercise_id!r}")

            task = generator.generate_task(
                description=step.description,
                targets=step.targets,
            )
            if hasattr(task, "mode"):
                task = replace(task, mode=step.mode)

            tasks.append(asdict(task))

        return tasks
