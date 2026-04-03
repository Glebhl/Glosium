from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Iterator, Literal

from app.api_keys import get_api_keys_store

from ..cache import ConversationState, PromptCachingConfig
from ..model_spec import ModelSpec
from .base import ChatSessionProtocol
from .registry import register_provider


logger = logging.getLogger(__name__)

OPENAI_API_KEY_PATH = "openai/api_key"

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

ChatRole = Literal["user", "assistant"]


def build_input_message(role: str, content: str) -> dict[str, str]:
    return {"role": role, "content": content}


def extract_response_text(response: Any) -> str:
    if response is None:
        return ""

    if isinstance(response, str):
        return response

    text = getattr(response, "output_text", None)
    if isinstance(text, str) and text:
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
    if chunks:
        return "".join(chunks)

    fallback_text = getattr(response, "text", None)
    if isinstance(fallback_text, str) and fallback_text:
        return fallback_text

    model_dump = getattr(response, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        dumped_output = dumped.get("output", []) if isinstance(dumped, dict) else []
        for item in dumped_output:
            if item.get("type") != "message":
                continue
            for content in item.get("content", []) or []:
                content_type = content.get("type")
                if content_type == "output_text":
                    chunks.append(content.get("text", ""))
                elif content_type == "refusal":
                    chunks.append(content.get("refusal", ""))
        if chunks:
            return "".join(chunks)

    return ""


def ensure_response_text(response: Any) -> str:
    text = extract_response_text(response)
    if isinstance(text, str):
        return text
    return str(text)


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
    cache_candidate: bool,
) -> None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return

    input_details = getattr(usage, "input_tokens_details", None)
    logger.info(
        (
            "OpenAI usage: operation=%s model=%s cache_candidate=%s "
            "input_tokens=%s cached_tokens=%s output_tokens=%s total_tokens=%s"
        ),
        operation,
        model,
        cache_candidate,
        getattr(usage, "input_tokens", None),
        getattr(input_details, "cached_tokens", None) if input_details is not None else None,
        getattr(usage, "output_tokens", None),
        getattr(usage, "total_tokens", None),
    )


@dataclass(slots=True, frozen=True)
class PreparedRequest:
    payload: dict[str, Any]
    cache_candidate: bool


@dataclass(slots=True, frozen=True)
class ChatMessage:
    role: ChatRole
    content: str

    def to_input_item(self) -> dict[str, str]:
        return build_input_message(self.role, self.content)


class OpenAIProvider:
    provider_name = "openai"

    def __init__(
        self,
        *,
        model_spec: ModelSpec,
        stream: bool = False,
        cache_config: PromptCachingConfig | None = None,
        base_url: str | None = None,
        reasoning_effort: str | None = None,
        text_verbosity: str | None = None,
        service_tier: str | None = None,
        provider_options: dict[str, Any] | None = None,
    ) -> None:
        api_keys = get_api_keys_store()
        client_kwargs: dict[str, Any] = {"api_key": api_keys.get_value(OPENAI_API_KEY_PATH)}
        if base_url:
            client_kwargs["base_url"] = base_url
        if provider_options:
            client_kwargs.update(provider_options)

        self._client_kwargs = client_kwargs
        self._client: Any | None = None
        self.model_name = model_spec.model
        self.model_spec = str(model_spec)
        self.stream = stream
        self.cache_config = cache_config or PromptCachingConfig()
        self.reasoning_effort = reasoning_effort
        self.text_verbosity = text_verbosity
        self.service_tier = service_tier

    @property
    def _responses_api(self) -> Any:
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(**self._client_kwargs)
        return self._client.responses

    def generate_text(
        self,
        *,
        system_prompt: str | None,
        user_text: str,
        stream: bool | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> str | Iterator[str]:
        if self._resolve_stream(stream):
            return self.stream_text(
                system_prompt=system_prompt,
                user_text=user_text,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )

        response = self._create_response(
            instructions=system_prompt,
            input_items=[build_input_message("user", user_text)],
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            operation="generate_text",
        )
        response_text = ensure_response_text(response)
        if not isinstance(response_text, str):
            raise TypeError(
                f"generate_text() expected str after extraction, got {type(response_text).__name__}"
            )
        return response_text

    def stream_text(
        self,
        *,
        system_prompt: str | None,
        user_text: str,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> Iterator[str]:
        raw_stream, cache_candidate = self._stream_response(
            instructions=system_prompt,
            input_items=[build_input_message("user", user_text)],
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        return self._iterate_text_stream(
            raw_stream,
            operation="stream_text",
            cache_candidate=cache_candidate,
        )

    def create_chat(
        self,
        *,
        system_prompt: str | None = None,
        stream: bool | None = None,
        use_response_chain: bool = False,
    ) -> ChatSessionProtocol:
        return OpenAIChatSession(
            provider=self,
            system_prompt=system_prompt,
            stream=self.stream if stream is None else stream,
            use_response_chain=use_response_chain,
        )

    def build_request(
        self,
        *,
        instructions: str | None,
        input_items: list[dict[str, str]],
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        previous_response_id: str | None = None,
    ) -> PreparedRequest:
        request: dict[str, Any] = {
            "model": self.model_name,
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

        return PreparedRequest(
            payload=request,
            cache_candidate=self.cache_config.is_cache_candidate(
                instructions=instructions,
                input_items=input_items,
                previous_response_id=previous_response_id,
            ),
        )

    def _create_response(
        self,
        *,
        instructions: str | None,
        input_items: list[dict[str, str]],
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        previous_response_id: str | None = None,
        operation: str,
    ) -> Any:
        prepared = self.build_request(
            instructions=instructions,
            input_items=input_items,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            previous_response_id=previous_response_id,
        )
        response = self._responses_api.create(**prepared.payload)
        log_response_usage(
            response,
            model=self.model_spec,
            operation=operation,
            cache_candidate=prepared.cache_candidate,
        )
        return response

    def _stream_response(
        self,
        *,
        instructions: str | None,
        input_items: list[dict[str, str]],
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        previous_response_id: str | None = None,
    ) -> tuple[Any, bool]:
        prepared = self.build_request(
            instructions=instructions,
            input_items=input_items,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            previous_response_id=previous_response_id,
        )
        prepared.payload["stream"] = True
        return self._responses_api.create(**prepared.payload), prepared.cache_candidate

    def _iterate_text_stream(
        self,
        raw_stream: Any,
        *,
        operation: str,
        cache_candidate: bool,
    ) -> Iterator[str]:
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
                        model=self.model_spec,
                        operation=operation,
                        cache_candidate=cache_candidate,
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


class OpenAIChatSession:
    """
    In-memory chat session over OpenAI Responses API.

    By default the session rebuilds the full message history every turn. That is
    the safest way to keep a stable prefix for automatic prompt caching. If
    ``use_response_chain=True`` is enabled, the session can switch to
    ``previous_response_id`` once the conversation chain is stable.
    """

    def __init__(
        self,
        *,
        provider: OpenAIProvider,
        system_prompt: str | None = None,
        stream: bool = False,
        use_response_chain: bool = False,
    ) -> None:
        self._provider = provider
        self._system_prompt = system_prompt
        self._stream = stream
        self._use_response_chain = use_response_chain
        self._messages: list[ChatMessage] = []
        self._pending_messages: list[ChatMessage] = []
        self._state = ConversationState()

    @property
    def messages(self) -> tuple[ChatMessage, ...]:
        return tuple(self._messages)

    @property
    def system_prompt(self) -> str | None:
        return self._system_prompt

    def set_system_prompt(self, prompt: str | None) -> None:
        self._system_prompt = prompt

    def add_message(self, role: ChatRole, content: str) -> None:
        self._append_message(
            role=role,
            content=content,
            queue_for_request=True,
            invalidate_chain=True,
        )

    def ask(
        self,
        user_text: str,
        *,
        stream: bool | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> str | Iterator[str]:
        self._append_message(
            role="user",
            content=user_text,
            queue_for_request=True,
            invalidate_chain=False,
        )
        return self.create_response(
            stream=stream,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

    def create_response(
        self,
        *,
        stream: bool | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> str | Iterator[str]:
        if not self._pending_messages:
            raise ValueError("Chat session has no pending messages to send.")

        request_input, previous_response_id = self._resolve_request_context()
        use_stream = self._stream if stream is None else stream

        if use_stream:
            return self._stream_response(
                request_input=request_input,
                previous_response_id=previous_response_id,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )

        response = self._provider._create_response(
            instructions=self._system_prompt,
            input_items=request_input,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            previous_response_id=previous_response_id,
            operation="chat_response",
        )
        text = extract_response_text(response)
        self._finalize_response(
            assistant_text=text,
            response_id=getattr(response, "id", None),
        )
        return text

    def _append_message(
        self,
        *,
        role: ChatRole,
        content: str,
        queue_for_request: bool,
        invalidate_chain: bool,
    ) -> None:
        message = ChatMessage(role=role, content=content)
        self._messages.append(message)
        if queue_for_request:
            self._pending_messages.append(message)
        if invalidate_chain:
            self._state.invalidate_chain()

    def _resolve_request_context(self) -> tuple[list[dict[str, str]], str | None]:
        if (
            self._use_response_chain
            and self._state.chain_is_valid
            and self._state.previous_response_id
        ):
            return (
                [message.to_input_item() for message in self._pending_messages],
                self._state.previous_response_id,
            )

        return ([message.to_input_item() for message in self._messages], None)

    def _finalize_response(self, *, assistant_text: str, response_id: str | None) -> None:
        self._pending_messages.clear()
        self._append_message(
            role="assistant",
            content=assistant_text,
            queue_for_request=False,
            invalidate_chain=False,
        )
        if response_id:
            self._state.remember_response(response_id)

    def _stream_response(
        self,
        *,
        request_input: list[dict[str, str]],
        previous_response_id: str | None,
        temperature: float | None,
        max_output_tokens: int | None,
    ) -> Iterator[str]:
        raw_stream, cache_candidate = self._provider._stream_response(
            instructions=self._system_prompt,
            input_items=request_input,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            previous_response_id=previous_response_id,
        )

        def iterator() -> Iterator[str]:
            chunks: list[str] = []
            finalized_text: str | None = None
            response_id: str | None = None
            completed_response = None
            completed = False

            try:
                for event in raw_stream:
                    event_type = getattr(event, "type", "")
                    if event_type == "response.output_text.delta":
                        delta = getattr(event, "delta", "")
                        if delta:
                            chunks.append(delta)
                            yield delta
                    elif event_type == "response.output_text.done":
                        finalized_text = getattr(event, "text", "") or ""
                    elif event_type == "response.completed":
                        completed_response = getattr(event, "response", None)
                        response_id = getattr(completed_response, "id", None)
                        completed = True
                    elif event_type == "error":
                        raise RuntimeError(extract_stream_error(event))
            finally:
                close = getattr(raw_stream, "close", None)
                if callable(close):
                    close()

                if completed:
                    if completed_response is not None:
                        log_response_usage(
                            completed_response,
                            model=self._provider.model_spec,
                            operation="chat_stream_response",
                            cache_candidate=cache_candidate,
                        )
                    assistant_text = "".join(chunks) if chunks else (finalized_text or "")
                    self._finalize_response(
                        assistant_text=assistant_text,
                        response_id=response_id,
                    )

        return iterator()


def create_openai_provider(**kwargs: Any) -> OpenAIProvider:
    return OpenAIProvider(**kwargs)


register_provider("openai", create_openai_provider)
