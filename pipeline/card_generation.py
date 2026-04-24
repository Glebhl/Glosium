from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from app.settings import get_settings_store
from app.language_registry import get_language_display_name
from llm_gateway import LLMTextClient
from models import VocabularyCard


logger = logging.getLogger(__name__)

CARD_JSON_FIELDS = (
    "lexeme",
    "lexical_unit",
    "part_of_speech",
    "level",
    "transcription",
    "translation",
    "meaning",
    "meaning_english",
    "example",
)
CARD_JSON_FIELD_SET = set(CARD_JSON_FIELDS)


class VocabularyCardStreamParser:
    """
    Parses the text stream produced by the LLM into complete vocabulary cards.

    Supports both JSON Lines (one card object per line) and regular JSON arrays.
    The parser emits cards as soon as each full JSON object becomes available.
    """

    def __init__(self) -> None:
        self._buffer = ""
        self._decoder = json.JSONDecoder()

    def feed(self, chunk: str) -> list[VocabularyCard]:
        completed_cards: list[VocabularyCard] = []
        if not chunk:
            logger.debug("Received empty chunk from vocabulary card stream.")
            return completed_cards

        self._buffer += chunk
        completed_cards.extend(self._consume_available(final=False))
        return completed_cards

    def finalize(self) -> list[VocabularyCard]:
        completed_cards: list[VocabularyCard] = []
        completed_cards.extend(self._consume_available(final=True))
        trailing = self._buffer.strip()
        self._buffer = ""
        if trailing:
            raise ValueError("Vocabulary card response ended with incomplete JSON content.")
        return completed_cards

    def _consume_available(self, *, final: bool) -> list[VocabularyCard]:
        completed_cards: list[VocabularyCard] = []

        while True:
            self._discard_prefix_tokens()
            if not self._buffer:
                break

            if self._buffer.startswith("```"):
                if not self._discard_code_fence(final=final):
                    break
                continue

            if self._buffer[0] != "{":
                if final:
                    raise ValueError(
                        f"Vocabulary card response must contain JSON objects, got: {self._buffer[:40]!r}"
                    )
                break

            try:
                payload, end_index = self._decoder.raw_decode(self._buffer)
            except json.JSONDecodeError:
                if final:
                    raise ValueError("Vocabulary card response is not valid JSON.") from None
                break

            self._buffer = self._buffer[end_index:]
            completed_cards.extend(self._coerce_cards(payload))

        return completed_cards

    def _discard_prefix_tokens(self) -> None:
        while self._buffer:
            stripped = self._buffer.lstrip()
            if stripped is not self._buffer:
                self._buffer = stripped
                continue

            if self._buffer[:1] in {"[", "]", ","}:
                self._buffer = self._buffer[1:]
                continue

            break

    def _discard_code_fence(self, *, final: bool) -> bool:
        newline_index = self._buffer.find("\n")
        if newline_index < 0:
            if final:
                self._buffer = ""
                return True
            return False

        self._buffer = self._buffer[newline_index + 1 :]
        return True

    def _coerce_cards(self, payload: Any) -> list[VocabularyCard]:
        if isinstance(payload, dict):
            return [self._build_card(payload)]
        if isinstance(payload, list):
            cards: list[VocabularyCard] = []
            for item in payload:
                if not isinstance(item, dict):
                    raise ValueError("Each vocabulary card must be a JSON object.")
                cards.append(self._build_card(item))
            return cards
        raise ValueError("Vocabulary card response must contain JSON objects.")

    def _build_card(self, payload: dict[str, Any]) -> VocabularyCard:
        normalized = self._normalize_payload(payload)
        missing_fields = [field for field in CARD_JSON_FIELDS if not normalized.get(field)]
        if missing_fields:
            raise ValueError(
                "Vocabulary card JSON object is missing required fields: "
                + ", ".join(missing_fields)
            )

        card = VocabularyCard(
            lexeme=normalized["lexeme"],
            lexical_unit=normalized["lexical_unit"],
            part_of_speech=normalized["part_of_speech"],
            translation=normalized["translation"],
            level=normalized["level"],
            transcription=normalized["transcription"],
            meaning=normalized["meaning"],
            meaning_english=normalized["meaning_english"],
            example=normalized["example"],
        )
        logger.debug(
            "Parsed vocabulary card: lexeme=%r, lexical_unit=%r, part_of_speech=%r, "
            "translation=%r, level=%r, transcription=%r, meaning=%r, "
            "meaning_english=%r, example=%r",
            card.lexeme,
            card.lexical_unit,
            card.part_of_speech,
            card.translation,
            card.level,
            card.transcription,
            card.meaning,
            card.meaning_english,
            card.example,
        )
        return card

    def _normalize_payload(self, payload: dict[str, Any]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for raw_key, raw_value in payload.items():
            if not isinstance(raw_key, str):
                continue

            key = raw_key.strip().lower()
            if key not in CARD_JSON_FIELD_SET:
                continue

            if not isinstance(raw_value, str) or not raw_value.strip():
                raise ValueError(f"Vocabulary card field {raw_key!r} must be a non-empty string.")
            normalized[key] = raw_value.strip()

        return normalized


class VocabularyCardGenerator:
    def __init__(
        self,
        lesson_language: str,
        learner_language: str,
    ) -> None:
        self._learner_language = learner_language
        settings = get_settings_store()
        self._text_client = LLMTextClient(
            model=settings.get_value("models/card_generation"),
            reasoning_effort=settings.get_value("pipeline/card_generation/reasoning_effort"),
            text_verbosity=settings.get_value("pipeline/card_generation/text_verbosity"),
            service_tier=settings.get_value("pipeline/card_generation/service_tier"),
        )

        prompt_path = Path("prompts") / lesson_language / "vocabulary_card_generation.txt"
        logger.debug("Loading vocabulary card prompt from %s", prompt_path)
        self._system_prompt = prompt_path.read_text(encoding="utf-8")
        logger.debug(
            "Initialized VocabularyCardGenerator with lesson_language='%s', learner_language='%s'.",
            lesson_language,
            learner_language,
        )

    def generate_cards(self, query: str) -> list[VocabularyCard]:
        cards = list(self.stream_cards(query))
        logger.debug("Generated %s vocabulary cards.", len(cards))
        return cards

    def stream_cards(self, query: str) -> Iterator[VocabularyCard]:
        parser = VocabularyCardStreamParser()
        emitted_count = 0
        user_prompt = self._build_user_prompt(query)
        for text_delta in self._text_client.stream_text(
            system_prompt=self._system_prompt,
            user_text=user_prompt,
        ):
            for card in parser.feed(text_delta):
                emitted_count += 1
                yield card

        for card in parser.finalize():
            emitted_count += 1
            yield card

    def _build_user_prompt(self, query: str) -> str:
        learner_language = get_language_display_name(self._learner_language) or self._learner_language
        lines = [
            "LEARNER_LANGUAGE: " + learner_language,
            "REQUEST:",
            (query or "").strip(),
        ]
        return "\n".join(lines)
