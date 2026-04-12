from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from llm_gateway.types import LLMResponse, LLMTokenUsage
from models import LessonTaskResult, MacroPlanStep, VocabularyCard


def build_log_scope(*, trace_id: str | None = None, stage_id: str | None = None) -> str:
    parts: list[str] = []
    if trace_id:
        parts.append(f"lesson_session={trace_id}")
    if stage_id:
        parts.append(f"stage={stage_id}")
    if not parts:
        return ""
    return "[" + " ".join(parts) + "] "


def format_log_event(title: str, *lines: str) -> str:
    rendered = [title]
    for line in lines:
        if not line:
            continue
        for item in str(line).splitlines():
            rendered.append(f"  {item}")
    return "\n".join(rendered)


def summarize_prompt(prompt: str, *, path: str | Path | None = None) -> str:
    parts = [
        f"path={path}" if path is not None else "",
        f"lines={prompt.count(chr(10)) + 1 if prompt else 0}",
    ]
    return ", ".join(part for part in parts if part)


def summarize_cards(cards: list[VocabularyCard], *, max_items: int = 10) -> list[str]:
    lines = [f"count={len(cards)}"]
    for index, card in enumerate(cards[:max_items], start=1):
        lines.append(f"{index}. {card.lexeme} ({card.part_of_speech}) -> {card.translation}")
    remaining = len(cards) - max_items
    if remaining > 0:
        lines.append(f"... and {remaining} more")
    return lines


def summarize_goals(goals: list[str], *, max_items: int = 15) -> list[str]:
    lines = [f"count={len(goals)}"]
    for index, goal in enumerate(goals[:max_items], start=1):
        lines.append(f"{index}. {_short_text(goal, max_chars=140)}")
    remaining = len(goals) - max_items
    if remaining > 0:
        lines.append(f"... and {remaining} more")
    return lines


def summarize_history(history: list[LessonTaskResult], *, max_items: int = 10) -> list[str]:
    lines = [f"count={len(history)}"]
    for result in history[:max_items]:
        lines.append(summarize_task_result(result))
    remaining = len(history) - max_items
    if remaining > 0:
        lines.append(f"... and {remaining} more")
    return lines


def summarize_task_result(result: LessonTaskResult) -> str:
    payload = result.task_payload
    targets = payload.get("lesson_targets")
    targets_text = ", ".join(str(item) for item in targets) if isinstance(targets, list) and targets else "n/a"
    return (
        f"task#{result.task_index} {result.task_id} "
        f"(correct={result.is_correct}, skipped={result.skipped}, targets={targets_text}, "
        f"user_answer={_short_text(result.user_answer, max_chars=80) or '[empty]'})"
    )


def summarize_macro_step(step: MacroPlanStep) -> list[str]:
    return [
        f"exercise_id={step.exercise_id}",
        f"mode={step.mode}",
        f"description={_short_text(step.description, max_chars=180)}",
        f"targets={', '.join(card.lexeme for card in step.targets)}",
    ]


def summarize_task_payload(payload: dict[str, Any]) -> list[str]:
    task_id = str(payload.get("task_id") or "")
    targets = ", ".join(str(item) for item in payload.get("lesson_targets") or []) or "n/a"
    lines = [
        f"task_id={task_id}",
        f"targets={targets}",
        f"description={_short_text(str(payload.get('lesson_description') or ''), max_chars=180) or '[empty]'}",
    ]

    if task_id == "explanation":
        cards = payload.get("cards") or []
        lines.append(f"cards={len(cards)}")
        for index, card in enumerate(cards[:4], start=1):
            if isinstance(card, dict):
                lines.append(
                    f"card {index}: name={_short_text(str(card.get('name') or ''), max_chars=60)}, "
                    f"has_content={bool(str(card.get('content') or '').strip())}"
                )
        return lines

    if task_id == "filling":
        answers = payload.get("answers") or []
        keyboard = payload.get("keyboard") or []
        sentence = payload.get("sentence") or []
        lines.extend([
            f"blanks={len(answers)}",
            f"answers={', '.join(_short_text(str(answer), max_chars=30) for answer in answers[:5]) or 'n/a'}",
            f"keyboard_size={len(keyboard)}",
            f"sentence_parts={len(sentence)}",
            f"mode={payload.get('mode')}",
        ])
        return lines

    if task_id == "matching":
        pairs = payload.get("pairs") or []
        lines.append(f"pairs={len(pairs)}")
        for index, pair in enumerate(pairs[:4], start=1):
            if isinstance(pair, (list, tuple)) and len(pair) == 2:
                lines.append(
                    f"pair {index}: {_short_text(str(pair[0]), max_chars=30)} => "
                    f"{_short_text(str(pair[1]), max_chars=30)}"
                )
        return lines

    if task_id == "question":
        options = payload.get("options") or []
        lines.extend([
            f"question={_short_text(str(payload.get('question') or ''), max_chars=160)}",
            f"options={len(options)}",
            f"answer={payload.get('answer')}",
        ])
        return lines

    if task_id == "translation":
        answers = payload.get("answers") or []
        keyboard = payload.get("keyboard") or []
        lines.extend([
            f"answers={', '.join(_short_text(str(answer), max_chars=30) for answer in answers[:5]) or 'n/a'}",
            f"keyboard_size={len(keyboard)}",
            f"mode={payload.get('mode')}",
        ])
        return lines

    lines.append(f"keys={', '.join(sorted(payload.keys()))}")
    return lines


def summarize_llm_output(text: str) -> list[str]:
    parsed = _try_parse_embedded_json(text)
    lines: list[str] = []

    if isinstance(parsed, dict):
        lines.append(f"keys={', '.join(list(parsed.keys())[:10])}")
    elif isinstance(parsed, list):
        lines.append(f"items={len(parsed)}")
    elif not text.strip():
        lines.append("empty_response=true")

    return lines


def summarize_exception(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {_short_text(str(exc), max_chars=300)}"


def summarize_llm_response(response: LLMResponse | None, *, model_spec: str) -> list[str]:
    if response is None:
        return ["response metadata unavailable"]

    lines = [f"model={model_spec}"]
    if response.response_id:
        lines.append(f"response_id={response.response_id}")
    service_tier = response.metadata.get("service_tier")
    if service_tier:
        lines.append(f"service_tier={service_tier}")

    timings = response.timings
    if timings is not None:
        timing_parts: list[str] = []
        if timings.time_to_first_token_seconds is not None:
            timing_parts.append(f"first_visible_output={timings.time_to_first_token_seconds:.2f}s")
        if timings.stream_seconds is not None:
            timing_parts.append(f"visible_output_stream={timings.stream_seconds:.2f}s")
        if timings.total_seconds is not None:
            timing_parts.append(f"provider_total={timings.total_seconds:.2f}s")
        if timing_parts:
            lines.extend(timing_parts)

    lines.extend(summarize_token_usage(response.usage, model_spec=model_spec))
    return lines


def summarize_token_usage(usage: LLMTokenUsage | None, *, model_spec: str | None = None) -> list[str]:
    if usage is None:
        return ["tokens=unavailable"]

    lines = [
        "tokens="
        + ", ".join([
            f"input={usage.input_tokens if usage.input_tokens is not None else 'n/a'}",
            f"output={usage.output_tokens if usage.output_tokens is not None else 'n/a'}",
            f"total={usage.total_tokens if usage.total_tokens is not None else 'n/a'}",
        ])
    ]

    thinking_tokens = _extract_usage_detail(
        usage.details,
        "thoughts_token_count",
        "reasoning_tokens",
        "reasoning_token_count",
    )
    cached_tokens = _extract_usage_detail(
        usage.details,
        "cached_content_token_count",
        "cached_tokens",
        "cached_input_tokens",
    )
    if cached_tokens is None:
        cached_tokens = _extract_usage_detail(usage.details.get("input", {}), "cached_tokens", "cached_input_tokens")
    if thinking_tokens is None:
        thinking_tokens = _extract_usage_detail(usage.details.get("output", {}), "reasoning_tokens")

    lines.append(
        "thinking_tokens="
        + (str(thinking_tokens) if thinking_tokens is not None else "not_reported_by_provider")
    )
    if cached_tokens is not None:
        lines.append(f"cached_tokens={cached_tokens}")

    cost_estimate = estimate_usage_cost(model_spec=model_spec, usage=usage) if model_spec else None
    if cost_estimate is not None:
        lines.append(f"estimated_cost_usd={cost_estimate:.6f}")

    return lines


def estimate_text_tokens(text: str) -> int:
    compact = " ".join(text.split())
    if not compact:
        return 0
    return max(1, math.ceil(len(compact) / 4))


def estimate_usage_cost(*, model_spec: str | None, usage: LLMTokenUsage) -> float | None:
    if not model_spec or ":" not in model_spec:
        return None

    try:
        from app.settings import get_settings_store
    except ModuleNotFoundError:
        return None

    provider, model = model_spec.split(":", 1)
    settings = get_settings_store()
    pricing = settings.get_value(f"pricing/{provider}/{model}")

    input_rate = _read_float(pricing.get("input_per_1m_tokens"))
    output_rate = _read_float(pricing.get("output_per_1m_tokens"))
    cached_rate = _read_float(pricing.get("cached_input_per_1m_tokens"))
    thinking_rate = _read_float(pricing.get("thinking_per_1m_tokens"))

    input_tokens = usage.input_tokens or 0
    output_tokens = usage.output_tokens or 0
    cached_tokens = _extract_usage_detail(
        usage.details,
        "cached_content_token_count",
        "cached_tokens",
        "cached_input_tokens",
    )
    if cached_tokens is None:
        cached_tokens = _extract_usage_detail(usage.details.get("input", {}), "cached_tokens", "cached_input_tokens")
    thinking_tokens = _extract_usage_detail(
        usage.details,
        "thoughts_token_count",
        "reasoning_tokens",
        "reasoning_token_count",
    )
    if thinking_tokens is None:
        thinking_tokens = _extract_usage_detail(usage.details.get("output", {}), "reasoning_tokens")

    non_cached_input_tokens = max(0, input_tokens - (cached_tokens or 0))
    total_cost = 0.0
    has_cost_component = False

    if input_rate is not None:
        total_cost += (non_cached_input_tokens / 1_000_000) * input_rate
        has_cost_component = True
    if cached_rate is not None and cached_tokens:
        total_cost += (cached_tokens / 1_000_000) * cached_rate
        has_cost_component = True
    if output_rate is not None:
        total_cost += (output_tokens / 1_000_000) * output_rate
        has_cost_component = True
    if thinking_rate is not None and thinking_tokens:
        total_cost += (thinking_tokens / 1_000_000) * thinking_rate
        has_cost_component = True

    return total_cost if has_cost_component else None


def format_text_block(title: str, text: str, *, max_chars: int = 3000) -> str:
    clipped = clip_text(text, max_chars=max_chars)
    block = [title]
    for line in clipped.splitlines() or ["[empty]"]:
        block.append(f"    {line}")
    return "\n".join(block)


def clip_text(text: str, *, max_chars: int = 3000) -> str:
    normalized = text.replace("\r\n", "\n").strip()
    if len(normalized) <= max_chars:
        return normalized

    head = max_chars // 2
    tail = max_chars - head - 32
    return (
        normalized[:head].rstrip()
        + "\n    ... [truncated] ...\n"
        + normalized[-tail:].lstrip()
    )


def extract_json_candidate(text: str) -> str:
    normalized = text.strip()
    if not normalized:
        return ""

    object_start = normalized.find("{")
    object_end = normalized.rfind("}")
    if object_start >= 0 and object_end > object_start:
        return normalized[object_start : object_end + 1]
    return normalized


def format_parse_error_context(text: str, *, max_chars: int = 1200) -> list[str]:
    normalized = text.strip()
    if not normalized:
        return ["response was empty"]

    candidate = extract_json_candidate(normalized)
    lines = [
        f"response_chars={len(normalized)}",
        f"candidate_chars={len(candidate)}",
    ]

    try:
        json.loads(candidate)
        lines.append("candidate json.loads(...) succeeded")
    except json.JSONDecodeError as exc:
        lines.append(
            f"json_error={exc.msg} at line={exc.lineno}, column={exc.colno}, pos={exc.pos}"
        )
        lines.append(f"context={_error_excerpt(candidate, exc.pos)}")

    lines.append(format_text_block("LLM response excerpt:", normalized, max_chars=max_chars))
    if candidate != normalized:
        lines.append(format_text_block("Extracted JSON candidate:", candidate, max_chars=max_chars))
    return lines


def _fingerprint_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def _extract_usage_detail(details: Any, *keys: str) -> int | None:
    if not isinstance(details, dict):
        return None
    for key in keys:
        value = details.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return int(value)
    return None


def _read_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _short_text(text: str | None, *, max_chars: int) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3] + "..."


def _try_parse_embedded_json(text: str) -> Any | None:
    normalized = text.strip()
    if not normalized:
        return None

    candidates = [normalized]
    object_start = normalized.find("{")
    object_end = normalized.rfind("}")
    if object_start >= 0 and object_end > object_start:
        candidates.append(normalized[object_start : object_end + 1])

    array_start = normalized.find("[")
    array_end = normalized.rfind("]")
    if array_start >= 0 and array_end > array_start:
        candidates.append(normalized[array_start : array_end + 1])

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    return None


def _error_excerpt(text: str, position: int, *, radius: int = 120) -> str:
    start = max(0, position - radius)
    end = min(len(text), position + radius)
    excerpt = text[start:end].replace("\n", "\\n")
    if start > 0:
        excerpt = "..." + excerpt
    if end < len(text):
        excerpt = excerpt + "..."
    return excerpt
