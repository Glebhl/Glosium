from .card_models import VocabularyCard
from dataclasses import dataclass


@dataclass(frozen=True)
class MacroPlanStep:
    description: str
    exercise_id: str
    mode: str
    