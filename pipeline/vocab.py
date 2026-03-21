from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from llm_gateway import OpenAITextClient
from llm_gateway.openai_wrapper import REASONING_EFFORT_MINIMAL, TEXT_VERBOSITY_LOW


logger = logging.getLogger(__name__)

CARD_FIELDS = (
    "LEXEME",
    "LEXICAL_UNIT",
    "PART_OF_SPEECH",
    "LEVEL",
    "TRANSCRIPTION",
    "TRANSLATION",
    "MEANING",
    "EXAMPLE",
)
CARD_FIELDS_SET = set(CARD_FIELDS)

LANGUAGE_MAP = {
    "en": "English",
    "zh": "Chinese (Mandarin)",
    "hi": "Hindi",
    "es": "Spanish",
    "fr": "French",
    "ar": "Arabic",
    "bn": "Bengali",
    "ru": "Russian",
    "pt": "Portuguese",
    "ur": "Urdu",
    "id": "Indonesian",
    "de": "German",
    "ja": "Japanese",
    "sw": "Swahili",
    "mr": "Marathi",
    "te": "Telugu",
    "tr": "Turkish",
    "ta": "Tamil",
    "vi": "Vietnamese",
    "ko": "Korean",
    "fa": "Persian (Farsi)",
    "it": "Italian",
    "th": "Thai",
    "gu": "Gujarati",
    "pl": "Polish",
    "uk": "Ukrainian",
    "ro": "Romanian",
    "nl": "Dutch",
    "el": "Greek",
    "cs": "Czech",
    "hu": "Hungarian",
    "sv": "Swedish",
    "he": "Hebrew",
    "da": "Danish",
    "fi": "Finnish",
    "no": "Norwegian",
    "sk": "Slovak",
    "bg": "Bulgarian",
    "hr": "Croatian",
    "sr": "Serbian",
    "sl": "Slovenian",
    "lt": "Lithuanian",
    "lv": "Latvian",
    "et": "Estonian",
    "ms": "Malay",
    "fil": "Filipino",
    "is": "Icelandic",
    "ga": "Irish",
    "mt": "Maltese",
    "sq": "Albanian",
    "mk": "Macedonian",
    "ka": "Georgian",
    "hy": "Armenian",
    "az": "Azerbaijani",
    "kk": "Kazakh",
    "uz": "Uzbek",
    "mn": "Mongolian",
}


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


class VocabularyCardStreamParser:
    """
    Parses the text stream produced by the LLM into complete vocabulary cards.

    The UI does not need half-filled snapshots, so the parser keeps partial state
    internally and emits a card only when the current block is complete.
    """

    def __init__(self) -> None:
        self._line_buffer = ""
        self._pending_fields: dict[str, str] = {}

    def feed(self, chunk: str) -> list[VocabularyCard]:
        completed_cards: list[VocabularyCard] = []
        if not chunk:
            return completed_cards

        self._line_buffer += chunk
        while True:
            newline_index = self._line_buffer.find("\n")
            if newline_index < 0:
                break

            line = self._line_buffer[:newline_index].rstrip("\r")
            self._line_buffer = self._line_buffer[newline_index + 1 :]
            completed_cards.extend(self._consume_line(line))

        return completed_cards

    def finalize(self) -> list[VocabularyCard]:
        completed_cards: list[VocabularyCard] = []
        if self._line_buffer.strip():
            completed_cards.extend(self._consume_line(self._line_buffer.rstrip("\r")))
        self._line_buffer = ""
        completed_cards.extend(self._flush_pending_card())
        return completed_cards

    def _consume_line(self, line: str) -> list[VocabularyCard]:
        stripped = line.strip()
        if not stripped:
            return self._flush_pending_card()

        field_name, separator, raw_value = stripped.partition(":")
        if not separator:
            return []

        field_name = field_name.strip().upper()
        if field_name not in CARD_FIELDS_SET:
            return []

        completed_cards: list[VocabularyCard] = []
        if field_name == "LEXEME" and self._pending_fields:
            # Some responses omit the blank line between cards, so a new lexeme is
            # a safe boundary for flushing the previous card before starting the next one.
            completed_cards.extend(self._flush_pending_card())

        self._pending_fields[field_name] = raw_value.strip()
        return completed_cards

    def _flush_pending_card(self) -> list[VocabularyCard]:
        if not self._pending_fields:
            return []

        missing_fields = [field for field in CARD_FIELDS if not self._pending_fields.get(field)]
        if missing_fields:
            logger.debug(
                "Skipping incomplete vocabulary card, missing fields: %s",
                ", ".join(missing_fields),
            )
            self._pending_fields = {}
            return []

        card = VocabularyCard(
            lexeme=self._pending_fields["LEXEME"],
            lexical_unit=self._pending_fields["LEXICAL_UNIT"],
            part_of_speech=self._pending_fields["PART_OF_SPEECH"],
            translation=self._pending_fields["TRANSLATION"],
            level=self._pending_fields["LEVEL"],
            transcription=self._pending_fields["TRANSCRIPTION"],
            meaning=self._pending_fields["MEANING"],
            example=self._pending_fields["EXAMPLE"],
        )
        self._pending_fields = {}
        return [card]


class VocabularyCardGenerator:
    def __init__(
        self,
        api_key: str,
        lesson_language: str,
        translation_language: str,
        model: str,
    ) -> None:
        self._text_client = OpenAITextClient(
            api_key=api_key,
            model=model,
            reasoning_effort=REASONING_EFFORT_MINIMAL,
            text_verbosity=TEXT_VERBOSITY_LOW,
        )

        prompt_path = Path("prompts") / lesson_language / "vocab_setup.txt"
        self._system_prompt = prompt_path.read_text(encoding="utf-8").format(
            language=LANGUAGE_MAP.get(translation_language, "English")
        )

    def generate_cards(self, query: str) -> list[VocabularyCard]:
        return list(self.stream_cards(query))

    def stream_cards(self, query: str) -> Iterator[VocabularyCard]:
        parser = VocabularyCardStreamParser()
        for text_delta in self._text_client.stream_text(
            system_prompt=self._system_prompt,
            user_text=query,
        ):
            yield from parser.feed(text_delta)

        yield from parser.finalize()

