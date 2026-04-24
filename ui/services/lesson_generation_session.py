from __future__ import annotations

import logging
from typing import Callable, Any

from models import VocabularyCard
from pipeline import LessonGoalGenerator
from pipeline import LessonStagePlanner
from pipeline import TaskGenerator

logger = logging.getLogger(__name__)


class LessonGenerationSession:
    _STAGE_IDS = ["presentation", "recognition", "stronger_recall"]

    def __init__(
        self,
        *,
        lesson_language: str,
        learner_language: str,
        learner_level: str,
        user_request: str | None = None,
        disabled_task_ids: tuple[str, ...] | list[str] = (),
    ) -> None:
        self._lesson_language = lesson_language
        self._learner_language = learner_language
        self._learner_level = learner_level
        self._user_request = user_request
        self._disabled_task_ids = tuple(str(task_id) for task_id in disabled_task_ids)

        # Callbacks
        self._on_first_task_generated: None | Callable = None
        self._on_task_generated: None | Callable = None
        self._on_new_stage_appeared: None | Callable = None
        
        # Generators
        self._goal_generator: LessonGoalGenerator = LessonGoalGenerator(
            lesson_language=lesson_language,
            learner_language=learner_language,
            learner_level=learner_level
        )
        self._task_generator: TaskGenerator = TaskGenerator(
            lesson_language=lesson_language,
            learner_language=learner_language,
            learner_level=learner_level,

        )
        self._cards: list[VocabularyCard] = []
        self._goals = []
        self._next_stage_index = 0
        self._generated_tasks_count = 0

    def subscribe_new_task_generated(self, function) -> None:
        self._on_new_task_generated = function

    def subscribe_new_stage_appeared(self, function) -> None:
        self._on_new_stage_appeared = function

    def subscribe_first_task_generated(self, function) -> None:
        self._on_first_task_generated = function

    def request_next_stage(self, history: Any) -> None:  # TODO add lesson history support
        if self._next_stage_index >= len(self._STAGE_IDS):
            logger.debug("All lesson stages are already generated; skipping next stage request")
            return

        self._generate_stage(self._STAGE_IDS[self._next_stage_index])
        self._next_stage_index += 1

    def start_generation(
        self,
        *,
        cards: list[VocabularyCard],
        user_request: str | None,
    ) -> list:
        self._goals = self._goal_generator.generate_goals(
            cards=cards,
            user_request=user_request
        )
        self._cards = cards
        self._next_stage_index = 0
        self._generated_tasks_count = 0

        self.request_next_stage(history=[])

    def _generate_stage(self, stage_id: str) -> None:
        stage_planner = LessonStagePlanner(
            lesson_language=self._lesson_language,
            learner_language=self._learner_language,
            learner_level=self._learner_level,
            stage_id=stage_id,
            user_request=self._user_request,
            disabled_task_ids=self._disabled_task_ids,
        )

        first_task_in_session = self._generated_tasks_count == 0

        for index, step in enumerate(
            stage_planner.stream_plan(
                lesson_goals=self._goals,
                cards=self._cards,
            )
        ):
            task = self._task_generator.generate_task(step)

            if first_task_in_session:
                if self._on_first_task_generated is None:
                    raise ValueError("Callback function for the first task is not assigned.")
                self._on_first_task_generated()
                first_task_in_session = False

            if self._on_new_task_generated is None:
                raise ValueError("Callback function for a new task is not assigned.")

            is_final_stage = stage_id == self._STAGE_IDS[-1]  # TODO make it be True when lesson is fully generated
            self._on_new_task_generated(task, self._generated_tasks_count, is_final_stage)
            self._generated_tasks_count += 1

            if index == 0:
                self._on_new_stage_appeared()
        
        logger.info("Finished %s stage generation", stage_id)
