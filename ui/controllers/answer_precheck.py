from __future__ import annotations

from itertools import product
from typing import Sequence

APOSTROPHE_VARIANTS = ("'", "\u2019", "`", "\u02bc")
LANGUAGE_CONTRACTION_RULES: dict[str, dict[str, tuple[str, ...]]] = {
    "en": {
        "n't": (" not",),
        "'re": (" are",),
        "'ve": (" have",),
        "'ll": (" will",),
        "'m": (" am",),
        "'d": (" would",),
        "'s": (" is", ""),
    },
}


def is_translation_answer_correct(
    *,
    user_answer: str,
    expected_answers: Sequence[str],
    language_code: str,
) -> bool:
    user_forms = build_normalized_answer_forms(
        user_answer,
        language_code=language_code,
    )
    return any(
        user_forms & build_normalized_answer_forms(
            expected_answer,
            language_code=language_code,
        )
        for expected_answer in expected_answers
    )


def is_filling_answer_correct(
    *,
    user_answers: Sequence[str],
    expected_answers: Sequence[str],
    language_code: str,
) -> bool:
    if len(user_answers) != len(expected_answers):
        return False

    return all(
        build_normalized_answer_forms(
            str(user_answer),
            language_code=language_code,
        )
        & build_normalized_answer_forms(
            str(expected_answer),
            language_code=language_code,
        )
        for user_answer, expected_answer in zip(user_answers, expected_answers)
    )


def build_normalized_answer_forms(
    text: str,
    *,
    language_code: str,
) -> set[str]:
    normalized_text = normalize_apostrophes(text)
    variants = {normalized_text}
    variants.update(expand_apostrophe_variants(normalized_text, language_code))

    normalized_forms: set[str] = set()
    for variant in variants:
        signature = alphabetic_signature(variant)
        if signature:
            normalized_forms.add(signature)

    return normalized_forms


def expand_apostrophe_variants(text: str, language_code: str) -> set[str]:
    rules = LANGUAGE_CONTRACTION_RULES.get((language_code or "").casefold(), {})
    if not rules:
        return set()

    token_variants: list[list[str]] = []
    for token in text.split():
        token_variants.append(expand_token_variants(token, rules))

    expanded_texts: set[str] = set()
    for variant_tokens in product(*token_variants):
        expanded_texts.add(" ".join(variant_tokens))

    return expanded_texts


def expand_token_variants(
    token: str,
    rules: dict[str, tuple[str, ...]],
) -> list[str]:
    token_casefold = token.casefold()
    variants = {token}

    for suffix, replacements in rules.items():
        if not token_casefold.endswith(suffix):
            continue

        token_stem = token[: len(token) - len(suffix)]
        for replacement in replacements:
            variants.add(f"{token_stem}{replacement}")

    return list(variants)


def normalize_apostrophes(text: str) -> str:
    normalized = text
    for apostrophe in APOSTROPHE_VARIANTS:
        normalized = normalized.replace(apostrophe, "'")
    return normalized


def alphabetic_signature(text: str) -> str:
    return "".join(character for character in text.casefold() if character.isalpha())
