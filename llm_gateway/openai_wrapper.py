from __future__ import annotations

import logging
import time
from typing import Any, Iterable, Iterator

from openai import OpenAI

from .openai_cache import PromptCacheConfig


logger = logging.getLogger(__name__)

REASONING_EFFORT_NONE = "none"
REASONING_EFFORT_MINIMAL = "minimal"
REASONING_EFFORT_LOW = "low"
REASONING_EFFORT_MEDIUM = "medium"
REASONING_EFFORT_HIGH = "high"
REASONING_EFFORT_XHIGH = "xhigh"
REASONING_EFFORTS = (
    REASONING_EFFORT_NONE,
    REASONING_EFFORT_MINIMAL,
    REASONING_EFFORT_LOW,
    REASONING_EFFORT_MEDIUM,
    REASONING_EFFORT_HIGH,
    REASONING_EFFORT_XHIGH,
)

TEXT_VERBOSITY_LOW = "low"
TEXT_VERBOSITY_MEDIUM = "medium"
TEXT_VERBOSITY_HIGH = "high"
TEXT_VERBOSITIES = (
    TEXT_VERBOSITY_LOW,
    TEXT_VERBOSITY_MEDIUM,
    TEXT_VERBOSITY_HIGH,
)

SERVICE_TIER_AUTO = "auto"
SERVICE_TIER_FLEX = "flex"
SERVICE_TIERS = (
    SERVICE_TIER_AUTO,
    SERVICE_TIER_FLEX,
)


def build_input_message(role: str, content: str) -> dict[str, str]:
    return {"role": role, "content": content}


def extract_response_text(response: Any) -> str:
    text = getattr(response, "output_text", None)
    if text:
        return text

    chunks: list[str] = []
    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", None) != "message":
            continue
        for content in getattr(item, "content", []) or []:
            content_type = getattr(content, "type", None)
            if content_type == "output_text":
                chunks.append(getattr(content, "text", ""))
            elif content_type == "refusal":
                chunks.append(getattr(content, "refusal", ""))
    return "".join(chunks)


def extract_stream_error(event: Any) -> str:
    error = getattr(event, "error", None)
    if error is not None:
        return getattr(error, "message", None) or str(error)
    return "OpenAI streaming request failed."


def log_response_usage(
    response: Any,
    *,
    model: str,
    operation: str,
    prompt_cache_key: str | None = None,
) -> None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return

    input_details = getattr(usage, "input_tokens_details", None)
    logger.info(
        "OpenAI usage: operation=%s model=%s prompt_cache_key=%s input_tokens=%s cached_tokens=%s output_tokens=%s total_tokens=%s",
        operation,
        model,
        prompt_cache_key,
        getattr(usage, "input_tokens", None),
        getattr(input_details, "cached_tokens", None) if input_details is not None else None,
        getattr(usage, "output_tokens", None),
        getattr(usage, "total_tokens", None),
    )


class OpenAITextClient:
    """
    Thin convenience wrapper around OpenAI Responses API.

    Usage:
        client = OpenAITextClient()
        text = client.generate_text(
            system_prompt="You are a concise assistant.",
            user_text="Hello!",
        )
    """

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "gpt-5-mini",
        stream: bool = False,
        cache_config: PromptCacheConfig | None = None,
        base_url: str | None = None,
        reasoning_effort: str | None = None,
        text_verbosity: str | None = None,
        service_tier: str | None = None,
    ) -> None:
        client_kwargs: dict[str, Any] = {}
        client_kwargs["api_key"] = api_key
        if base_url:
            client_kwargs["base_url"] = base_url

        self._client = OpenAI(**client_kwargs)
        self.model = model
        self.stream = stream
        self.cache_config = cache_config or PromptCacheConfig()
        self.reasoning_effort = reasoning_effort
        self.text_verbosity = text_verbosity
        self.service_tier = service_tier

    def generate_text(
        self,
        *,
        system_prompt: str | None,
        user_text: str,
        stream: bool | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> str | Iterator[str]:
        request = self.build_request(
            instructions=system_prompt,
            input_items=[build_input_message("user", user_text)],
            cache_scope=("single-shot", self.model, system_prompt or ""),
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

        if self._resolve_stream(stream):
            return self._stream_text(request)

        response = self._client.responses.create(**request)
        log_response_usage(
            response,
            model=self.model,
            operation="generate_text",
            prompt_cache_key=request.get("prompt_cache_key"),
        )
        return extract_response_text(response)

    def stream_text(
        self,
        *,
        system_prompt: str | None,
        user_text: str,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> Iterator[str]:
        request = self.build_request(
            instructions=system_prompt,
            input_items=[build_input_message("user", user_text)],
            cache_scope=("single-shot", self.model, system_prompt or ""),
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        return self._stream_text(request)

    def create_chat(
        self,
        *,
        system_prompt: str | None = None,
        stream: bool | None = None,
        use_response_chain: bool = False,
    ) -> "OpenAIChatSession":
        from .openai_chat import OpenAIChatSession

        return OpenAIChatSession(
            client=self,
            system_prompt=system_prompt,
            stream=self.stream if stream is None else stream,
            use_response_chain=use_response_chain,
        )

    def build_request(
        self,
        *,
        instructions: str | None,
        input_items: list[dict[str, str]],
        cache_scope: Iterable[str | None],
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        previous_response_id: str | None = None,
    ) -> dict[str, Any]:
        request: dict[str, Any] = {
            "model": self.model,
            "input": input_items,
        }
        if instructions:
            request["instructions"] = instructions
        if temperature is not None:
            request["temperature"] = temperature
        if max_output_tokens is not None:
            request["max_output_tokens"] = max_output_tokens
        if previous_response_id:
            request["previous_response_id"] = previous_response_id
        if self.reasoning_effort:
            request["reasoning"] = {"effort": self.reasoning_effort}
        if self.text_verbosity:
            request["text"] = {"verbosity": self.text_verbosity}
        if self.service_tier:
            request["service_tier"] = self.service_tier

        request.update(self.cache_config.build_request_options(*cache_scope))
        return request

    def stream_response(
        self,
        *,
        instructions: str | None,
        input_items: list[dict[str, str]],
        cache_scope: Iterable[str | None],
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        previous_response_id: str | None = None,
    ) -> Any:
        request = self.build_request(
            instructions=instructions,
            input_items=input_items,
            cache_scope=cache_scope,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            previous_response_id=previous_response_id,
        )
        request["stream"] = True
        return self._client.responses.create(**request)

    def create_response(
        self,
        *,
        instructions: str | None,
        input_items: list[dict[str, str]],
        cache_scope: Iterable[str | None],
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        previous_response_id: str | None = None,
    ) -> Any:
        request = self.build_request(
            instructions=instructions,
            input_items=input_items,
            cache_scope=cache_scope,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            previous_response_id=previous_response_id,
        )
        response = self._client.responses.create(**request)
        log_response_usage(
            response,
            model=self.model,
            operation="create_response",
            prompt_cache_key=request.get("prompt_cache_key"),
        )
        return response

    def _stream_text(self, request: dict[str, Any]) -> Iterator[str]:
        raw_stream = self._client.responses.create(**request, stream=True)

        def iterator() -> Iterator[str]:
            started_at = time.perf_counter()
            first_delta_at: float | None = None
            completed_response: Any | None = None
            try:
                for event in raw_stream:
                    event_type = getattr(event, "type", "")
                    if event_type == "response.output_text.delta":
                        delta = getattr(event, "delta", "")
                        if delta:
                            if first_delta_at is None:
                                first_delta_at = time.perf_counter()
                                logger.debug(
                                    "Received first response delta after %.2fs",
                                    first_delta_at - started_at,
                                )
                            yield delta
                    elif event_type == "response.completed":
                        completed_response = getattr(event, "response", None)
                    elif event_type == "error":
                        raise RuntimeError(extract_stream_error(event))
            finally:
                close = getattr(raw_stream, "close", None)
                if callable(close):
                    close()
                if completed_response is not None:
                    log_response_usage(
                        completed_response,
                        model=self.model,
                        operation="stream_text",
                        prompt_cache_key=request.get("prompt_cache_key"),
                    )
                logger.debug(
                    "Streaming response finished in %.2fs",
                    time.perf_counter() - started_at,
                )

        return iterator()

    def _resolve_stream(self, stream: bool | None) -> bool:
        if stream is None:
            return self.stream
        return stream
