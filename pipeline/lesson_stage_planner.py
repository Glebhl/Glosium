from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path

from app.language_registry import get_language_display_name
from app.settings import get_settings_store
from llm_gateway import LLMTextClient
from models import LessonStageId, MacroPlanStep, VocabularyCard


logger = logging.getLogger(__name__)


class LessonStagePlanStreamParser:
    def __init__(self, cards_by_unit_id: dict[str, VocabularyCard]) -> None:
        self._cards_by_unit_id = cards_by_unit_id
        self._buffer = ""

    def feed(self, chunk: str) -> list[MacroPlanStep]:
        if not chunk:
            return []

        self._buffer += chunk
        return self._consume_available(final=False)

    def finalize(self) -> list[MacroPlanStep]:
        steps = self._consume_available(final=True)
        trailing = self._buffer.strip()
        self._buffer = ""
        if trailing:
            raise ValueError("Lesson stage response ended with incomplete JSONL content.")
        return steps

    def _consume_available(self, *, final: bool) -> list[MacroPlanStep]:
        steps: list[MacroPlanStep] = []

        while True:
            newline_index = self._buffer.find("\n")
            if newline_index < 0:
                break

            raw_line = self._buffer[:newline_index]
            self._buffer = self._buffer[newline_index + 1 :]
            step = self._parse_line(raw_line)
            if step is not None:
                steps.append(step)

        if final and self._buffer.strip():
            step = self._parse_line(self._buffer)
            self._buffer = ""
            if step is not None:
                steps.append(step)

        return steps

    def _parse_line(self, raw_line: str) -> MacroPlanStep | None:
        line = raw_line.strip()
        if not line:
            return None

        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError("Lesson stage step must be a JSON object.")

        description = str(payload.get("description", "")).strip()
        exercise_id = str(payload.get("exercise_id", "")).strip()
        mode = str(payload.get("mode", "")).strip()
        raw_targets = payload.get("targets")

        if not description:
            raise ValueError("Lesson stage step is missing description.")
        if not exercise_id:
            raise ValueError("Lesson stage step is missing exercise_id.")
        if not mode:
            raise ValueError("Lesson stage step is missing mode.")
        if not isinstance(raw_targets, list) or not raw_targets:
            raise ValueError("Lesson stage step must contain a non-empty targets list.")

        targets: list[VocabularyCard] = []
        for raw_target in raw_targets:
            unit_id = str(raw_target).strip()
            card = self._cards_by_unit_id.get(unit_id)
            if card is None:
                raise ValueError(f"Unknown learning unit in lesson stage step: {unit_id!r}")
            targets.append(card)

        return MacroPlanStep(
            description=description,
            exercise_id=exercise_id,
            mode=mode,
            targets=targets,
        )


class LessonStagePlanner:
    _PROMPT_FILENAME_BY_STAGE: dict[LessonStageId, str] = {
        "presentation": "lesson_stage_presentation.txt",
        "recognition": "lesson_stage_recognition.txt",
        "stronger_recall": "lesson_stage_stronger_recall.txt",
    }

    def __init__(
        self,
        *,
        lesson_language: str,
        lerner_language: str,
        lerner_level: str,
        stage_id: LessonStageId,
    ) -> None:
        self._lerner_language = lerner_language
        self._lerner_level = lerner_level
        self._stage_id = stage_id

        settings = get_settings_store()
        self._text_client = LLMTextClient(
            model=settings.get_value(f"models/lesson_planning/{stage_id}"),
            reasoning_effort=settings.get_value(f"pipeline/lesson_planning/{stage_id}/reasoning_effort"),
            text_verbosity=settings.get_value(f"pipeline/lesson_planning/{stage_id}/text_verbosity"),
            service_tier=settings.get_value(f"pipeline/lesson_planning/{stage_id}/service_tier"),
        )

        prompt_path = Path("prompts") / lesson_language / self._PROMPT_FILENAME_BY_STAGE[stage_id]
        self._prompt_path = prompt_path
        self._system_prompt = prompt_path.read_text(encoding="utf-8")
        logger.debug("Loaded lesson stage prompt from %s", prompt_path)

    def generate_plan(
        self,
        *,
        lesson_goals: list[str],
        cards: list[VocabularyCard],
    ) -> list[MacroPlanStep]:
        return list(self.stream_plan(lesson_goals=lesson_goals, cards=cards))

    def stream_plan(
        self,
        *,
        lesson_goals: list[str],
        cards: list[VocabularyCard],
    ) -> Iterator[MacroPlanStep]:
        cards_by_unit_id = {
            f"U{index}": card
            for index, card in enumerate(cards, start=1)
        }
        parser = LessonStagePlanStreamParser(cards_by_unit_id)
        user_prompt = self._build_user_prompt(
            lesson_goals=lesson_goals,
            cards=cards,
        )

        for text_delta in self._text_client.stream_text(
            system_prompt=self._system_prompt,
            user_text=user_prompt,
        ):
            for step in parser.feed(text_delta):
                yield step

        for step in parser.finalize():
            yield step

    def _build_user_prompt(
        self,
        *,
        lesson_goals: list[str],
        cards: list[VocabularyCard],
    ) -> str:
        learner_language = get_language_display_name(self._lerner_language)

        lines = []

        lines.append(f"STAGE: {self._stage_id}")
        lines.append(f"LERNER_LANGUAGE: {learner_language}")
        lines.append(f"LERNER_LEVEL: {self._lerner_level}")
        
        lines.append("LEARNING_UNITS:")
        for index, card in enumerate(cards, start=1):
            lines.append(
                f"U{index} | lexeme={card.lexeme} | meaning={card.meaning_english} | "
                f"translation={card.translation} | pos={card.part_of_speech}"
            )

        lines.append("LESSON_GOALS:")
        for index, goal in enumerate(lesson_goals, start=1):
            lines.append(f"{index}. {goal}")

        return "\n".join(lines)
