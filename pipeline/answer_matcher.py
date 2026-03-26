from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from llm_gateway import OpenAITextClient
from llm_gateway.openai_wrapper import (
    REASONING_EFFORT_LOW,
    TEXT_VERBOSITY_LOW,
)

CORRECT = "correct"
MISTAKE = "mistake"
MINOR_MISTAKE = "minor"


@dataclass(frozen=True)
class AnswerMatchResult:
    evaluation: str
    correct_answer: str | None = None


class AnswerMatcher:
    def __init__(
            self,
            *,
            api_key: str,
            model: str,
            lesson_language: str,
        ) -> None:
        self._text_client = OpenAITextClient(
            api_key=api_key,
            model=model,
            reasoning_effort=REASONING_EFFORT_LOW,
            text_verbosity=TEXT_VERBOSITY_LOW,
            # service_tier=SERVICE_TIER_FLEX,
        )

        prompt_dir = Path("prompts") / lesson_language
        self._translation_system_prompt = (
            prompt_dir / "translation_answer_check.txt"
        ).read_text(encoding="utf-8")
        self._filling_system_prompt = (
            prompt_dir / "filling_answer_check.txt"
        ).read_text(encoding="utf-8")
    
    def evaluate_text_answer(
        self,
        original_text: str,
        user_answer: str,
    ) -> AnswerMatchResult:
        response = self._generate_evaluation(
            system_prompt=self._translation_system_prompt,
            user_text=self._build_translation_user_prompt(
                original_text=original_text,
                user_answer=user_answer,
            ),
        )

        return AnswerMatchResult(
            evaluation=response,
            correct_answer=None,
        )

    def evaluate_filling_answer(
        self,
        sentence_parts: Sequence[str],
        expected_answers: Sequence[str],
        user_answers: Sequence[str],
    ) -> AnswerMatchResult:
        normalized_user_answers = [str(answer) for answer in user_answers]
        normalized_expected_answers = [str(answer) for answer in expected_answers]

        if len(normalized_user_answers) != len(normalized_expected_answers):
            return AnswerMatchResult(
                evaluation=MISTAKE,
                correct_answer=None,
            )

        response = self._generate_evaluation(
            system_prompt=self._filling_system_prompt,
            user_text=self._build_filling_user_prompt(
                sentence_parts=sentence_parts,
                expected_answers=normalized_expected_answers,
                user_answers=normalized_user_answers,
            ),
        )

        return AnswerMatchResult(
            evaluation=response,
            correct_answer=None,
        )

    def _generate_evaluation(
        self,
        *,
        system_prompt: str,
        user_text: str,
    ) -> str:
        response = self._text_client.generate_text(
            system_prompt=system_prompt,
            user_text=user_text,
        )
        return response.strip().lower()

    def _build_translation_user_prompt(
        self,
        original_text: str,
        user_answer: str,
    ) -> str:
        """
        Builds a plain-text input prompt for translation answer evaluation.
        """
        lines: list[str] = []

        lines.append(f"SENTENCE: {original_text}")
        lines.append(f"USER_ANSWER: {user_answer}")

        return "\n".join(lines)

    def _build_filling_user_prompt(
        self,
        sentence_parts: Sequence[str],
        expected_answers: Sequence[str],
        user_answers: Sequence[str],
    ) -> str:
        """
        Builds a plain-text input prompt for fill-in-the-blank answer evaluation.
        """
        lines: list[str] = []

        lines.append(
            f"SENTENCE_TEMPLATE: {self._build_blank_sentence_template(sentence_parts)}"
        )
        lines.append("EXPECTED_ANSWERS:")
        lines.extend(
            f"{index}. {answer}"
            for index, answer in enumerate(expected_answers, start=1)
        )
        lines.append("USER_ANSWERS:")
        lines.extend(
            f"{index}. {answer}"
            for index, answer in enumerate(user_answers, start=1)
        )

        print("\n\n\n", "\n".join(lines), "\n\n\n")

        return "\n".join(lines)

    @staticmethod
    def _build_blank_sentence_template(sentence_parts: Sequence[str]) -> str:
        chunks: list[str] = []

        for index, part in enumerate(sentence_parts):
            chunks.append(part)
            if index != len(sentence_parts) - 1:
                chunks.append(f"[BLANK {index + 1}]")

        return "".join(chunks)
