import logging
import re
from dataclasses import dataclass
from pathlib import Path

from app.language_registry import get_language_display_name
from dev_fixtures import DevFixtureSettings
from llm_gateway import OpenAITextClient
from llm_gateway.openai_wrapper import REASONING_EFFORT_MEDIUM, TEXT_VERBOSITY_MEDIUM, SERVICE_TIER_FLEX

from .card_models import VocabularyCard

logger = logging.getLogger(__name__)
FIELD_RE = re.compile(r"^(STEP_ID|DESCRIPTION|EXERCISE_ID|MODE|TARGETS):[ \t]*(.*)$", re.MULTILINE)
TARGET_ID_RE = re.compile(r"^[A-Za-z](\d+)$")


@dataclass(frozen=True)
class MacroPlanStep:
    description: str
    exercise_id: str
    mode: str
    targets: list[VocabularyCard]


class MacroPlanner:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        lesson_language: str,
        translation_language: str,
        lerner_level: str,
    ):
        self._translation_language = translation_language
        self._lerner_level = lerner_level
        logger.debug(
            "Initializing MacroPlanner with model=%s, lesson_language=%s, translation_language=%s, learner_level=%s",
            model,
            lesson_language,
            translation_language,
            lerner_level,
        )
        self._dev_fixtures = DevFixtureSettings.from_env()
        self._text_client = OpenAITextClient(
            api_key=api_key,
            model=model,
            reasoning_effort=REASONING_EFFORT_MEDIUM,
            text_verbosity=TEXT_VERBOSITY_MEDIUM,
            service_tier=SERVICE_TIER_FLEX,
        )

        prompt_path = Path("prompts") / lesson_language / "lesson_macro_planning.txt"
        self._system_prompt = prompt_path.read_text(encoding="utf-8")
        logger.debug("Loaded macro planning system prompt from %s", prompt_path)

    def generate_plan(
        self,
        *,
        cards: list[VocabularyCard],
        user_request: str | None = None,
    ) -> list[MacroPlanStep]:
        logger.debug(
            "Generating macro plan for %d cards%s",
            len(cards),
            " with" if user_request else " without" + " user request",
        )
        payload = self._build_user_prompt(
            translation_language=get_language_display_name(self._translation_language),
            lerner_level=self._lerner_level,
            user_request=user_request,
            learning_units=cards,
        )

        if self._dev_fixtures.use_macro_plan_fixture:
            macro_plan = self._dev_fixtures.load_macro_plan_text()
            logger.info("Using macro plan fixture from %s", self._dev_fixtures.macro_plan_path)
        else:
            macro_plan = self._text_client.generate_text(
                system_prompt=self._system_prompt,
                user_text=payload,
            )

        plan = self._parse_macro_plan(macro_plan, cards)
        return plan

    def _build_user_prompt(
        self,
        *,
        translation_language: str,
        lerner_level: str,
        learning_units: list[VocabularyCard],
        user_request: str | None = None
    ) -> str:
        """
        Builds a plain-text input prompt for the macro lesson planner.
        """

        lines: list[str] = []

        lines.append(f"LERNER_LANGUAGE: {translation_language}")
        lines.append("")

        lines.append(f"LERNER_LEVEL: {lerner_level}")
        lines.append("")

        if user_request:
            lines.append("USER_REQUEST:")
            lines.append(user_request)
            lines.append("")

        lines.append("LEARNING_UNITS:")
        for index, unit in enumerate(learning_units, start=1):
            base = (
                f"U{index} | lexeme | "
                f"{unit.lexeme} | {unit.meaning} "
                f"{unit.part_of_speech} | {unit.translation}"
            )

            lines.append(base)

        prompt = "\n".join(lines)
        return prompt

    def _parse_macro_plan(self, raw_text: str, cards: list[VocabularyCard]) -> list[MacroPlanStep]:
        normalized = raw_text.replace("\r\n", "\n").replace("\r", "\n").strip()
        sections = self._collect_step_sections(normalized)
        return [self._build_step(section, cards) for section in sections]

    def _collect_step_sections(self, text: str) -> list[dict[str, str]]:
        matches = list(FIELD_RE.finditer(text))
        if not matches:
            logger.error("No recognizable macro plan fields found in LLM response")
            raise ValueError("No recognizable macro plan fields found in LLM response.")

        steps: list[dict[str, str]] = []
        current_step: dict[str, str] = {}

        for index, match in enumerate(matches):
            field_name = match.group(1).upper()
            inline_value = match.group(2).strip()
            value_start = match.end()
            value_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            trailing_value = text[value_start:value_end].strip()

            if inline_value and trailing_value:
                value = f"{inline_value}\n{trailing_value}"
            else:
                value = inline_value or trailing_value

            if field_name == "STEP_ID" and current_step:
                steps.append(current_step)
                current_step = {}

            current_step[field_name] = value.strip()

        if current_step:
            steps.append(current_step)

        logger.debug("Parsed %d raw macro plan steps", len(steps))
        return steps

    def _build_step(self, raw_step: dict[str, str], cards: list[VocabularyCard]) -> MacroPlanStep:
        step = MacroPlanStep(
            description=self._require_field(raw_step, "DESCRIPTION"),
            exercise_id=self._require_field(raw_step, "EXERCISE_ID"),
            mode=self._require_field(raw_step, "MODE"),
            targets=self._parse_targets(self._require_field(raw_step, "TARGETS"), cards),
        )
        return step

    def _require_field(self, step: dict[str, str], field_name: str) -> str:
        value = step.get(field_name, "").strip()
        if not value:
            logger.error("Macro plan step is missing required field %s", field_name)
            raise ValueError(f"Missing required macro plan field: {field_name}")
        return value

    def _parse_targets(self, raw_targets: str, cards: list[VocabularyCard]) -> list[VocabularyCard]:
        parsed_targets: list[VocabularyCard] = []

        for raw_target in raw_targets.split(","):
            target = raw_target.strip()
            if not target:
                continue

            match = TARGET_ID_RE.match(target)
            if not match:
                logger.error("Invalid macro plan target identifier: %r", target)
                raise ValueError(f"Invalid target identifier in macro plan: {target!r}")

            card_index = int(match.group(1)) - 1
            if card_index < 0 or card_index >= len(cards):
                logger.error(
                    "Macro plan target %r is out of range for %d cards",
                    target,
                    len(cards),
                )
                raise ValueError(f"Macro plan target is out of range: {target!r}")

            parsed_targets.append(cards[card_index])

        if not parsed_targets:
            logger.error("Macro plan step contains no valid targets")
            raise ValueError("Macro plan step contains no targets.")

        return parsed_targets
