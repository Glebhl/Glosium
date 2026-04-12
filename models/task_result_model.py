from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


LessonStageId = Literal["presentation", "recognition", "stronger_recall"]

LESSON_STAGE_SEQUENCE: tuple[LessonStageId, ...] = (
    "presentation",
    "recognition",
    "stronger_recall",
)


@dataclass(frozen=True, slots=True)
class LessonTaskResult:
    stage_id: LessonStageId
    task_index: int
    task_id: str
    description: str
    user_answer: str
    is_correct: bool | None
    skipped: bool
    task_payload: dict[str, Any]
