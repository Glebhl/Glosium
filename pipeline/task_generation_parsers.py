from __future__ import annotations

import re
import random
from collections import Counter
from typing import Iterable

from models.task_generation_models import (
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
    sections = _collect_sections(text)
    raw_text = _require_section(sections, "PARAGRAPH")
    answers = re.findall(r"\[([^\[\]]*)\]", raw_text)
    distractors = tuple(_parse_list(_require_section(sections, "DISTRACTORS")))

    if not answers:
        raise ValueError("Fill-in-the-blank exercise contains no answers.")
    
    keyboard = [*answers, *distractors]
    random.shuffle(keyboard)

    return FillInTheBlankExercise(
        task_id="filling",
        sentence=tuple(_split_text_into_sentence_parts(raw_text)),
        keyboard=tuple(keyboard),
        mode="word-bank",
        answers=answers,
        audio=False,
    )


def parse_matching_exercise(text: str) -> MatchingExercise:
    pairs = tuple(_parse_matching_pairs(_require_section(_collect_sections(text), "COLUMNS")))
    if not pairs:
        raise ValueError("Matching exercise contains no pairs.")
    return MatchingExercise(
        task_id="matching",
        pairs=pairs,
        answers=(),
        audio=False,
    )


def parse_multiple_choice_exercise(text: str) -> MultipleChoiceExercise:
    sections = _collect_sections(text)
    options = tuple(_parse_options(_require_section(sections, "OPTIONS")))
    if not options:
        raise ValueError("Multiple-choice exercise contains no options.")

    answer_index = _parse_answer_index(_require_section(sections, "ANSWER"), options)
    return MultipleChoiceExercise(
        task_id="question",
        question=_require_section(sections, "QUESTION"),
        paragraph=_require_section(sections, "PASSAGE"),
        options=options,
        answer=answer_index,
        audio=False,
    )


def parse_translation_exercise(text: str) -> TranslationExercise:
    sections = _collect_sections(text)
    answers = tuple(_parse_list(_require_section(sections, "ANSWERS")))
    distractors = tuple(_parse_list(_require_section(sections, "DISTRACTORS")))

    keyboard = [*build_word_bank(answers), *distractors]
    random.shuffle(keyboard)

    return TranslationExercise(
        task_id="translation",
        sentence=_require_section(sections, "PARAGRAPH"),
        keyboard=tuple(keyboard),
        mode="word-bank",
        answers=answers,
        audio=False,
    )


SECTION_HEADER_RE = re.compile(
    r"^(PARAGRAPH|ANSWERS|DISTRACTORS|PASSAGE|QUESTION|OPTIONS|ANSWER|COLUMNS|TYPING_LANGUAGE):[ \t]*(.*)$",
    re.MULTILINE,
)
OPTION_LINE_RE = re.compile(r"^[A-Z]\.\s*(.+)$")
BLANK_RE = re.compile(r"\[([^\[\]]+)\]")


def _collect_sections(text: str) -> dict[str, str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    matches = list(SECTION_HEADER_RE.finditer(normalized))
    if not matches:
        raise ValueError("No recognizable sections found in LLM response.")

    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        name = match.group(1).upper()
        inline_value = match.group(2).strip()
        value_start = match.end()
        value_end = matches[index + 1].start() if index + 1 < len(matches) else len(normalized)
        trailing_value = normalized[value_start:value_end].strip()

        if inline_value and trailing_value:
            value = f"{inline_value}\n{trailing_value}"
        else:
            value = inline_value or trailing_value

        sections[name] = value.strip()

    return sections


def _require_section(sections: dict[str, str], name: str) -> str:
    value = _optional_section(sections, name)
    if not value:
        raise ValueError(f"Missing required section: {name}")
    return value


def _optional_section(sections: dict[str, str], name: str) -> str:
    return sections.get(name.upper(), "").strip()


def _parse_matching_pairs(raw_value: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for raw_line in raw_value.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        separator = " / " if " / " in line else "/"
        if separator not in line:
            raise ValueError(f"Invalid matching pair line: {raw_line!r}")

        left, right = line.split(separator, maxsplit=1)
        pairs.append((left.strip(), right.strip()))

    return pairs


def _parse_options(raw_value: str) -> list[str]:
    return [
        match.group(1).strip()
        for line in raw_value.splitlines()
        if (match := OPTION_LINE_RE.match(line.strip()))
    ]


def _parse_list(raw_value: str) -> list[str]:
    value = raw_value.strip()
    if not value:
        return []

    bullet_items = [
        stripped[1:].strip()
        for line in value.splitlines()
        if (stripped := line.strip()).startswith("-")
    ]
    if bullet_items:
        return [item for item in bullet_items if item]

    if "\n" in value:
        return [line.strip() for line in value.splitlines() if line.strip()]

    return [item.strip() for item in value.split(",") if item.strip()]


def _split_text_into_sentence_parts(raw_value: str) -> list[str]:
    parts: list[str] = []
    cursor = 0

    for match in BLANK_RE.finditer(raw_value):
        parts.append(raw_value[cursor:match.start()])
        cursor = match.end()

    parts.append(raw_value[cursor:])
    return parts


def _parse_answer_index(raw_value: str, options: tuple[str, ...]) -> int:
    answer = raw_value.strip()
    if not answer:
        raise ValueError("Multiple-choice exercise answer is empty.")

    if len(answer) == 1 and answer.isalpha():
        index = ord(answer.upper()) - ord("A")
        if 0 <= index < len(options):
            return index

    for index, option in enumerate(options):
        if option.strip() == answer:
            return index

    raise ValueError(f"Multiple-choice answer is not present in options: {raw_value!r}")
