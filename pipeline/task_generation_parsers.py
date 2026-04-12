from __future__ import annotations

import json
import random
from collections import Counter
from typing import Any, Iterable

from models.task_models import (
    ExplanationCard,
    ExplanationExercise,
    FillInTheBlankExercise,
    MatchingExercise,
    MultipleChoiceExercise,
    TranslationExercise,
)


def tokenize_for_word_bank(text: str) -> list[str]:
    """
    Splits a string into words for the word bank.

    Rules:
    - preserves letters of any alphabet
    - allows any non-whitespace characters inside words
    - removes non-letter characters at word boundaries
    - does not normalize case
    """
    tokens = []

    for chunk in text.split():
        start = 0
        end = len(chunk)

        while start < end and not chunk[start].isalpha():
            start += 1

        while end > start and not chunk[end - 1].isalpha():
            end -= 1

        if start < end:
            tokens.append(chunk[start:end])

    return tokens


def build_word_bank(strings: Iterable[str]) -> list[str]:
    """
    Builds a word bank from an array of strings.

    For each word, stores the maximum number of occurrences
    that appeared in any single string.
    """
    max_counts: Counter[str] = Counter()
    first_seen_order: dict[str, int] = {}
    order_index = 0

    for text in strings:
        tokens = tokenize_for_word_bank(text)
        line_counts = Counter(tokens)

        for token, count in line_counts.items():
            if token not in first_seen_order:
                first_seen_order[token] = order_index
                order_index += 1

            if count > max_counts[token]:
                max_counts[token] = count

    result = []
    for token, _ in sorted(first_seen_order.items(), key=lambda x: x[1]):
        result.extend([token] * max_counts[token])

    return result


def parse_fill_in_the_blank_exercise(text: str) -> FillInTheBlankExercise:
    payload = _load_json_object(text)
    raw_text = _require_string(payload, "paragraph")
    answers = _extract_answers_from_brackets(raw_text)
    distractors = tuple(_require_string_list(payload, "distractors"))

    if not answers:
        raise ValueError("Fill-in-the-blank exercise contains no answers.")

    keyboard = [*answers, *distractors]
    random.shuffle(keyboard)

    return FillInTheBlankExercise(
        task_id="filling",
        sentence=tuple(_split_text_into_sentence_parts(raw_text)),
        keyboard=tuple(keyboard),
        mode="word-bank",
        answers=tuple(answers),
        audio=False,
    )


def parse_explanation_exercise(text: str) -> ExplanationExercise:
    cards = _parse_explanation_cards_block(text)
    if cards is None:
        payload = _load_json_object(text)
        raw_cards = payload.get("cards")
        if not isinstance(raw_cards, list) or not raw_cards:
            raise ValueError("Explanation exercise contains no cards.")

        cards = []
        for raw_card in raw_cards:
            if not isinstance(raw_card, dict):
                raise ValueError("Explanation card must be a JSON object.")

            name = _require_string(raw_card, "name")
            content = _require_string(raw_card, "content")
            cards.append(ExplanationCard(name=name, content=content))

    return ExplanationExercise(
        task_id="explanation",
        cards=tuple(cards),
    )


def parse_matching_exercise(text: str) -> MatchingExercise:
    payload = _load_json_object(text)
    raw_pairs = payload.get("pairs")
    if not isinstance(raw_pairs, list) or not raw_pairs:
        raise ValueError("Matching exercise contains no pairs.")

    pairs: list[tuple[str, str]] = []
    for raw_pair in raw_pairs:
        if not isinstance(raw_pair, (list, tuple)) or len(raw_pair) != 2:
            raise ValueError("Each matching pair must be an array of two strings.")
        left, right = raw_pair
        pairs.append((_coerce_non_empty_string(left, "matching pair left"), _coerce_non_empty_string(right, "matching pair right")))

    return MatchingExercise(
        task_id="matching",
        pairs=tuple(pairs),
        answers=(),
        audio=False,
    )


def parse_multiple_choice_exercise(text: str) -> MultipleChoiceExercise:
    payload = _load_json_object(text)
    options = tuple(_require_string_list(payload, "options"))
    if not options:
        raise ValueError("Multiple-choice exercise contains no options.")

    answer_index = _parse_answer_index(payload.get("answer"), options)
    return MultipleChoiceExercise(
        task_id="question",
        question=_require_string(payload, "question"),
        paragraph=_require_string(payload, "passage"),
        options=options,
        answer=answer_index,
        audio=False,
    )


def parse_translation_exercise(text: str) -> TranslationExercise:
    payload = _load_json_object(text)
    answers = tuple(_require_string_list(payload, "answers"))
    distractors = tuple(_require_string_list(payload, "distractors"))

    keyboard = [*build_word_bank(answers), *distractors]
    random.shuffle(keyboard)

    return TranslationExercise(
        task_id="translation",
        sentence=_require_string(payload, "paragraph"),
        keyboard=tuple(keyboard),
        mode="word-bank",
        answers=answers,
        audio=False,
    )


def _load_json_object(text: str) -> dict[str, Any]:
    normalized = text.strip()
    if not normalized:
        raise ValueError("LLM response is empty.")

    candidates = [normalized]
    object_start = normalized.find("{")
    object_end = normalized.rfind("}")
    if object_start >= 0 and object_end > object_start:
        candidates.append(normalized[object_start : object_end + 1])

    best_error: json.JSONDecodeError | None = None
    best_candidate = normalized
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError as exc:
            if best_error is None or exc.pos < best_error.pos:
                best_error = exc
                best_candidate = candidate
            continue
        if isinstance(payload, dict):
            return payload

    if best_error is not None:
        context_start = max(0, best_error.pos - 120)
        context_end = min(len(best_candidate), best_error.pos + 120)
        context = best_candidate[context_start:context_end].replace("\n", "\\n")
        if context_start > 0:
            context = "..." + context
        if context_end < len(best_candidate):
            context = context + "..."
        raise ValueError(
            "LLM response is not a valid JSON object. "
            f"JSONDecodeError: {best_error.msg} at line={best_error.lineno}, column={best_error.colno}, pos={best_error.pos}. "
            f"Context: {context}"
        ) from best_error

    raise ValueError("LLM response is not a valid JSON object.")


def _parse_explanation_cards_block(text: str) -> list[ExplanationCard] | None:
    normalized = text.strip()
    if not normalized or "===CARD===" not in normalized:
        return None

    cards: list[ExplanationCard] = []
    chunks = normalized.split("===CARD===")
    for chunk in chunks:
        body = chunk.strip()
        if not body:
            continue

        end_marker = body.find("===END_CARD===")
        if end_marker >= 0:
            body = body[:end_marker].strip()

        lines = body.splitlines()
        if not lines:
            continue

        first_line = lines[0].strip()
        if not first_line.startswith("NAME:"):
            raise ValueError("Explanation card must start with 'NAME:'.")

        name = _coerce_non_empty_string(first_line[len("NAME:") :], "name")

        remaining = lines[1:]
        while remaining and not remaining[0].strip():
            remaining = remaining[1:]

        if not remaining or remaining[0].strip() != "HTML:":
            raise ValueError("Explanation card must contain an 'HTML:' section.")

        content = "\n".join(remaining[1:]).strip()
        if not content:
            raise ValueError("Explanation card HTML content is empty.")

        cards.append(ExplanationCard(name=name, content=content))

    return cards or None


def _require_string(payload: dict[str, Any], key: str) -> str:
    return _coerce_non_empty_string(payload.get(key), key)


def _coerce_non_empty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Field {label!r} must be a non-empty string.")
    return value.strip()


def _require_string_list(payload: dict[str, Any], key: str) -> list[str]:
    raw_value = payload.get(key)
    if not isinstance(raw_value, list):
        raise ValueError(f"Field {key!r} must be a JSON array.")

    values: list[str] = []
    for item in raw_value:
        values.append(_coerce_non_empty_string(item, key))
    return values


def _extract_answers_from_brackets(raw_value: str) -> list[str]:
    answers: list[str] = []
    cursor = 0

    while True:
        start = raw_value.find("[", cursor)
        if start < 0:
            break
        end = raw_value.find("]", start + 1)
        if end < 0:
            break

        answer = raw_value[start + 1 : end].strip()
        if answer:
            answers.append(answer)
        cursor = end + 1

    return answers


def _split_text_into_sentence_parts(raw_value: str) -> list[str]:
    parts: list[str] = []
    cursor = 0

    while True:
        start = raw_value.find("[", cursor)
        if start < 0:
            break
        end = raw_value.find("]", start + 1)
        if end < 0:
            break
        parts.append(raw_value[cursor:start])
        cursor = end + 1

    parts.append(raw_value[cursor:])
    return parts


def _parse_answer_index(raw_value: Any, options: tuple[str, ...]) -> int:
    if isinstance(raw_value, bool):
        raise ValueError("Multiple-choice answer must not be boolean.")

    if isinstance(raw_value, int):
        if 0 <= raw_value < len(options):
            return raw_value
        raise ValueError(f"Multiple-choice answer index is out of range: {raw_value}")

    if not isinstance(raw_value, str) or not raw_value.strip():
        raise ValueError("Multiple-choice answer is empty.")

    answer = raw_value.strip()
    if len(answer) == 1 and answer.isalpha():
        index = ord(answer.upper()) - ord("A")
        if 0 <= index < len(options):
            return index

    for index, option in enumerate(options):
        if option.strip() == answer:
            return index

    raise ValueError(f"Multiple-choice answer is not present in options: {raw_value!r}")
