from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VocabularyCard:
    lexeme: str
    lexical_unit: str
    part_of_speech: str
    level: str
    translation: str
    transcription: str
    meaning: str
    example: str

    def to_dict(self) -> dict[str, str]:
        return {
            "LEXEME": self.lexeme,
            "LEXICAL_UNIT": self.lexical_unit,
            "PART_OF_SPEECH": self.part_of_speech,
            "TRANSLATION": self.translation,
            "LEVEL": self.level,
            "TRANSCRIPTION": self.transcription,
            "MEANING": self.meaning,
            "EXAMPLE": self.example,
        }
