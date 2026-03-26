from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

__all__ = [
    "FillInTheBlankExercise",
    "MatchingExercise",
    "MultipleChoiceExercise",
    "TranslationExercise",
]


@dataclass(frozen=True, slots=True)
class FillInTheBlankExercise:
    task_id: Literal["filling"]
    sentence: tuple[str, ...]
    keyboard: tuple[str, ...]
    mode: str
    answers: tuple[str, ...]
    audio: bool


@dataclass(frozen=True, slots=True)
class MatchingExercise:
    task_id: Literal["matching"]
    pairs: tuple[tuple[str, str], ...]
    answers: tuple[str, ...]
    audio: bool


@dataclass(frozen=True, slots=True)
class MultipleChoiceExercise:
    task_id: Literal["question"]
    question: str
    paragraph: str
    options: tuple[str, ...]
    answer: int
    audio: bool


@dataclass(frozen=True, slots=True)
class TranslationExercise:
    task_id: Literal["translation"]
    sentence: str
    keyboard: tuple[str, ...]
    mode: str
    answers: tuple[str, ...]
    audio: bool
