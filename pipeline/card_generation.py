from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

from app.language_registry import get_language_display_name
from llm_gateway import OpenAITextClient
from llm_gateway.openai_wrapper import REASONING_EFFORT_NONE, TEXT_VERBOSITY_LOW, SERVICE_TIER_FLEX
from .card_models import VocabularyCard


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


class VocabularyCardStreamParser:
    """
    Parses the text stream produced by the LLM into complete vocabulary cards.

    The UI does not need half-filled snapshots, so the parser keeps partial state
    internally and emits a card only when the current block is complete.
    """

    def __init__(self) -> None:
        self._line_buffer = ""
        self._pending_fields: dict[str, str] = {}
        self._chunk_count = 0

    def feed(self, chunk: str) -> list[VocabularyCard]:
        completed_cards: list[VocabularyCard] = []
        if not chunk:
            logger.debug("Received empty chunk from vocabulary card stream.")
            return completed_cards

        self._chunk_count += 1
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
            logger.debug("Ignoring unknown field in stream: %s", field_name)
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
        logger.debug("Parsed vocabulary card for lexeme '%s'.", card.lexeme)
        return [card]


class VocabularyCardGenerator:
    def __init__(
        self,
        api_key: str,
        model: str,
        lesson_language: str,
        translation_language: str,
    ) -> None:
        self._text_client = OpenAITextClient(
            api_key=api_key,
            model=model,
            reasoning_effort=REASONING_EFFORT_NONE,
            text_verbosity=TEXT_VERBOSITY_LOW,
            service_tier=SERVICE_TIER_FLEX,
        )

        prompt_path = Path("prompts") / lesson_language / "vocabulary_card_generation.txt"
        logger.debug("Loading vocabulary card prompt from %s", prompt_path)
        self._system_prompt = prompt_path.read_text(encoding="utf-8").format(
            language=get_language_display_name(translation_language)
        )
        logger.debug(
            "Initialized VocabularyCardGenerator with model='%s', lesson_language='%s', translation_language='%s'.",
            model,
            lesson_language,
            translation_language,
        )

    def generate_cards(self, query: str) -> list[VocabularyCard]:
        cards = list(self.stream_cards(query))
        logger.debug("Generated %s vocabulary cards.", len(cards))
        return cards

    def stream_cards(self, query: str) -> Iterator[VocabularyCard]:
        parser = VocabularyCardStreamParser()
        emitted_count = 0
        for text_delta in self._text_client.stream_text(
            system_prompt=self._system_prompt,
            user_text=query,
        ):
            for card in parser.feed(text_delta):
                emitted_count += 1
                yield card

        for card in parser.finalize():
            emitted_count += 1
            yield card
