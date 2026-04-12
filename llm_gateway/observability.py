from __future__ import annotations

import inspect
import logging
import time
import uuid
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .types import LLMMessage, LLMResponse

logger = logging.getLogger("llm.usage")


def start_request_log(
    *,
    provider: str,
    model: str,
    messages: Sequence[LLMMessage],
    reasoning_effort: str | None,
    text_verbosity: str | None,
    service_tier: str | None,
    temperature: float | None,
    max_output_tokens: int | None,
    provider_options: dict[str, Any] | None,
    stream: bool,
) -> dict[str, Any]:
    request_id = uuid.uuid4().hex[:12]
    started_at_monotonic = time.perf_counter()
    context = {
        "request_id": request_id,
        "provider": provider,
        "model": model,
        "model_spec": f"{provider}:{model}",
        "stream": stream,
        "origin": _detect_request_origin(),
        "request": {
            "reasoning_effort": reasoning_effort,
            "text_verbosity": text_verbosity,
            "service_tier": service_tier,
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
            "provider_option_keys": sorted((provider_options or {}).keys()),
            "messages": _summarize_messages(messages),
        },
        "_started_at_monotonic": started_at_monotonic,
    }
    _emit(
        "request_started",
        context,
        extra={
            "request_started_at": _utc_now(),
        },
    )
    return context


def complete_request_log(context: dict[str, Any], response: LLMResponse) -> None:
    elapsed_seconds = _elapsed_seconds(context)
    usage = response.usage
    timings = response.timings
    cost_amount, cost_reason = _describe_usage_cost(
        model_spec=context.get("model_spec"),
        usage=usage,
    )
    _emit(
        "request_completed",
        context,
        extra={
            "request_completed_at": _utc_now(),
            "elapsed_seconds": elapsed_seconds,
            "response": {
                "response_id": response.response_id,
                "input_model": response.metadata.get("input_model") or context.get("model_spec"),
                "output_model": response.metadata.get("output_model") or response.metadata.get("model"),
                "output_chars": len(response.text or ""),
                "output_estimated_tokens": _estimate_text_tokens(response.text or ""),
                "metadata": _sanitize_dict(response.metadata),
                "timings": {
                    "total_seconds": timings.total_seconds if timings is not None else None,
                    "time_to_first_token_seconds": (
                        timings.time_to_first_token_seconds if timings is not None else None
                    ),
                    "stream_seconds": timings.stream_seconds if timings is not None else None,
                },
                "usage": {
                    "input_tokens": usage.input_tokens if usage is not None else None,
                    "output_tokens": usage.output_tokens if usage is not None else None,
                    "total_tokens": usage.total_tokens if usage is not None else None,
                    "thinking_tokens": _extract_usage_detail(
                        usage.details if usage is not None else {},
                        "thoughts_token_count",
                        "reasoning_tokens",
                        "reasoning_token_count",
                    ),
                    "cached_input_tokens": _extract_cached_tokens(usage.details if usage is not None else {}),
                    "details": _sanitize_dict(usage.details if usage is not None else {}),
                    "estimated_cost_usd": cost_amount,
                    "estimated_cost_reason": cost_reason,
                },
            },
        },
    )


def fail_request_log(
    context: dict[str, Any],
    exc: BaseException,
    *,
    response: LLMResponse | None = None,
) -> None:
    elapsed_seconds = _elapsed_seconds(context)
    response_payload: dict[str, Any] | None = None
    if response is not None:
        timings = response.timings
        response_payload = {
            "response_id": response.response_id,
            "output_chars": len(response.text or ""),
            "metadata": _sanitize_dict(response.metadata),
            "timings": {
                "total_seconds": timings.total_seconds if timings is not None else None,
                "time_to_first_token_seconds": (
                    timings.time_to_first_token_seconds if timings is not None else None
                ),
                "stream_seconds": timings.stream_seconds if timings is not None else None,
            },
            "usage": {
                "input_tokens": response.usage.input_tokens if response.usage is not None else None,
                "output_tokens": response.usage.output_tokens if response.usage is not None else None,
                "total_tokens": response.usage.total_tokens if response.usage is not None else None,
                "details": _sanitize_dict(response.usage.details) if response.usage is not None else {},
            },
        }

    _emit(
        "request_failed",
        context,
        extra={
            "request_failed_at": _utc_now(),
            "elapsed_seconds": elapsed_seconds,
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
            },
            "partial_response": response_payload,
        },
        level=logging.ERROR,
    )


def _emit(
    event: str,
    context: dict[str, Any],
    *,
    extra: dict[str, Any],
    level: int = logging.INFO,
) -> None:
    logger.log(level, _render_event(event, context, extra))


def _render_event(event: str, context: dict[str, Any], extra: dict[str, Any]) -> str:
    request = context.get("request") or {}
    messages = request.get("messages") or {}
    origin = context.get("origin") or {}
    lines = [
        (
            f"LLM {event} | id={context.get('request_id')} | model={context.get('model_spec')} "
            f"| stream={_format_bool(context.get('stream'))}"
        ),
        (
            f"when={_first_present(extra, 'request_started_at', 'request_completed_at', 'request_failed_at')} "
            f"| origin={_format_origin(origin)}"
        ),
        (
            "request: "
            f"reasoning={request.get('reasoning_effort') or 'default'}, "
            f"verbosity={request.get('text_verbosity') or 'default'}, "
            f"service_tier={request.get('service_tier') or 'default'}, "
            f"temperature={_format_optional(request.get('temperature'))}, "
            f"max_output_tokens={_format_optional(request.get('max_output_tokens'))}"
        ),
    ]

    provider_option_keys = request.get("provider_option_keys") or []
    if provider_option_keys:
        lines.append(f"provider_options: {', '.join(str(item) for item in provider_option_keys)}")

    lines.append(
        "messages: "
        f"count={messages.get('count', 0)}, "
        f"chars={messages.get('chars_total', 0)}, "
        f"est_tokens={messages.get('estimated_tokens_total', 0)}, "
        f"roles={_format_role_map(messages.get('count_by_role') or {})}"
    )
    for item in messages.get("items") or []:
        lines.append(
            "  "
            f"#{item.get('index')} {item.get('role')}: "
            f"chars={item.get('chars')}, est_tokens={item.get('estimated_tokens')}, fp={item.get('sha1_prefix')}"
        )

    if event == "request_completed":
        response = extra.get("response") or {}
        timings = response.get("timings") or {}
        usage = response.get("usage") or {}
        lines.append(
            "response: "
            f"id={response.get('response_id') or 'n/a'}, "
            f"chars={response.get('output_chars', 0)}, "
            f"est_tokens={response.get('output_estimated_tokens', 0)}, "
            f"elapsed={_format_seconds(extra.get('elapsed_seconds'))}"
        )
        lines.append(
            "models: "
            f"input_model={response.get('input_model') or context.get('model_spec') or 'n/a'}, "
            f"output_model={response.get('output_model') or response.get('input_model') or context.get('model_spec') or 'n/a'}"
        )
        lines.append(
            "timings: "
            f"provider_total={_format_seconds(timings.get('total_seconds'))}, "
            f"first_token={_format_seconds(timings.get('time_to_first_token_seconds'))}, "
            f"stream={_format_seconds(timings.get('stream_seconds'))}"
        )
        lines.append(
            "usage: "
            f"input={_format_optional(usage.get('input_tokens'))}, "
            f"output={_format_optional(usage.get('output_tokens'))}, "
            f"total={_format_optional(usage.get('total_tokens'))}, "
            f"thinking={_format_optional(usage.get('thinking_tokens'))}, "
            f"cached_input={_format_optional(usage.get('cached_input_tokens'))}"
        )
        lines.append(
            "cost: "
            + _format_cost_with_reason(
                usage.get("estimated_cost_usd"),
                usage.get("estimated_cost_reason"),
            )
        )
        metadata = _compact_mapping(response.get("metadata") or {})
        if metadata:
            lines.append(f"response_meta: {metadata}")
        usage_details = _compact_mapping(usage.get("details") or {})
        lines.append(f"usage_details: {usage_details or 'not_reported_by_provider'}")

    elif event == "request_failed":
        error = extra.get("error") or {}
        lines.append(
            "error: "
            f"{error.get('type') or 'UnknownError'}: {error.get('message') or '[empty]'} "
            f"| elapsed={_format_seconds(extra.get('elapsed_seconds'))}"
        )
        partial_response = extra.get("partial_response") or {}
        if partial_response:
            partial_usage = partial_response.get("usage") or {}
            partial_timings = partial_response.get("timings") or {}
            lines.append(
                "partial_response: "
                f"id={partial_response.get('response_id') or 'n/a'}, "
                f"chars={partial_response.get('output_chars', 0)}, "
                f"input={_format_optional(partial_usage.get('input_tokens'))}, "
                f"output={_format_optional(partial_usage.get('output_tokens'))}, "
                f"total={_format_optional(partial_usage.get('total_tokens'))}, "
                f"provider_total={_format_seconds(partial_timings.get('total_seconds'))}"
            )
            partial_usage_details = _compact_mapping(partial_usage.get("details") or {})
            if partial_usage_details:
                lines.append(f"partial_usage_details: {partial_usage_details}")

    return "\n".join(lines) + "\n"


def _detect_request_origin() -> dict[str, Any]:
    frame = inspect.currentframe()
    try:
        current = frame.f_back if frame is not None else None
        while current is not None:
            module_name = current.f_globals.get("__name__", "")
            if not module_name.startswith("llm_gateway"):
                filename = current.f_code.co_filename
                return {
                    "module": module_name,
                    "function": current.f_code.co_name,
                    "file": Path(filename).name if filename else None,
                    "line": current.f_lineno,
                }
            current = current.f_back
    finally:
        del frame

    return {
        "module": None,
        "function": None,
        "file": None,
        "line": None,
    }


def _summarize_messages(messages: Sequence[LLMMessage]) -> dict[str, Any]:
    per_message: list[dict[str, Any]] = []
    totals_by_role: dict[str, int] = {}
    chars_by_role: dict[str, int] = {}
    tokens_by_role: dict[str, int] = {}

    for index, message in enumerate(messages, start=1):
        text = message.content or ""
        estimated_tokens = _estimate_text_tokens(text)
        per_message.append({
            "index": index,
            "role": message.role,
            "chars": len(text),
            "estimated_tokens": estimated_tokens,
            "sha1_prefix": _fingerprint(text),
        })
        totals_by_role[message.role] = totals_by_role.get(message.role, 0) + 1
        chars_by_role[message.role] = chars_by_role.get(message.role, 0) + len(text)
        tokens_by_role[message.role] = tokens_by_role.get(message.role, 0) + estimated_tokens

    return {
        "count": len(messages),
        "chars_total": sum(item["chars"] for item in per_message),
        "estimated_tokens_total": sum(item["estimated_tokens"] for item in per_message),
        "count_by_role": totals_by_role,
        "chars_by_role": chars_by_role,
        "estimated_tokens_by_role": tokens_by_role,
        "items": per_message,
    }


def _estimate_text_tokens(text: str) -> int:
    compact = " ".join(text.split())
    if not compact:
        return 0
    return max(1, (len(compact) + 3) // 4)


def _fingerprint(text: str) -> str:
    import hashlib

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


def _extract_cached_tokens(details: Any) -> int | None:
    cached_tokens = _extract_usage_detail(
        details,
        "cached_content_token_count",
        "cached_tokens",
        "cached_input_tokens",
    )
    if cached_tokens is not None:
        return cached_tokens
    if isinstance(details, dict):
        return _extract_usage_detail(details.get("input", {}), "cached_tokens", "cached_input_tokens")
    return None


def _describe_usage_cost(*, model_spec: str | None, usage: Any) -> tuple[float | None, str | None]:
    if usage is None:
        return None, "provider did not report token usage"
    if not model_spec or ":" not in model_spec:
        return None, "model spec is missing"

    try:
        from app.settings import get_settings_store
    except ModuleNotFoundError:
        return None, "settings module is unavailable"

    provider, model = model_spec.split(":", 1)
    pricing = get_settings_store().get_value(f"pricing/{provider}/{model}")
    if not isinstance(pricing, dict):
        return None, f"no pricing config for {model_spec}"

    input_rate = _read_float(pricing.get("input_per_1m_tokens"))
    output_rate = _read_float(pricing.get("output_per_1m_tokens"))
    cached_rate = _read_float(pricing.get("cached_input_per_1m_tokens"))
    thinking_rate = _read_float(pricing.get("thinking_per_1m_tokens"))

    input_tokens = usage.input_tokens or 0
    output_tokens = usage.output_tokens or 0
    cached_tokens = _extract_cached_tokens(usage.details)
    thinking_tokens = _extract_usage_detail(
        usage.details,
        "thoughts_token_count",
        "reasoning_tokens",
        "reasoning_token_count",
    )
    if thinking_tokens is None and isinstance(usage.details, dict):
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

    if not has_cost_component:
        return None, f"pricing config for {model_spec} has no usable rates"
    return total_cost, None


def _read_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _sanitize_dict(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _sanitize_dict(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_dict(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _compact_mapping(value: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, item in value.items():
        if item in (None, "", [], {}, ()):
            continue
        if isinstance(item, dict):
            nested = _compact_mapping(item)
            if nested:
                parts.append(f"{key}={{ {nested} }}")
            continue
        parts.append(f"{key}={item}")
    return ", ".join(parts)


def _elapsed_seconds(context: dict[str, Any]) -> float:
    started_at_monotonic = context.get("_started_at_monotonic")
    if not isinstance(started_at_monotonic, (int, float)):
        return 0.0
    return time.perf_counter() - float(started_at_monotonic)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _format_optional(value: Any) -> str:
    return "n/a" if value is None else str(value)


def _format_seconds(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, (int, float)):
        return f"{float(value):.2f}s"
    return str(value)


def _format_cost(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, (int, float)):
        return f"{float(value):.6f}"
    return str(value)


def _format_cost_with_reason(value: Any, reason: Any) -> str:
    if value is not None:
        return f"usd={_format_cost(value)}"
    if reason:
        return f"unavailable ({reason})"
    return "unavailable"


def _format_bool(value: Any) -> str:
    return "yes" if value else "no"


def _format_origin(origin: dict[str, Any]) -> str:
    module = origin.get("module") or "unknown"
    function = origin.get("function") or "unknown"
    file_name = origin.get("file") or "unknown"
    line = origin.get("line") or "?"
    return f"{module}.{function} ({file_name}:{line})"


def _format_role_map(value: dict[str, Any]) -> str:
    if not value:
        return "n/a"
    return ", ".join(f"{key}={item}" for key, item in sorted(value.items()))


def _first_present(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload.get(key)
    return None
