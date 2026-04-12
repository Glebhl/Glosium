from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any, Callable

from .model_spec import ModelSpec
from .providers.registry import get_provider, get_registered_providers
from .retries import request_with_retry, stream_with_retry
from .types import LLMMessage, LLMResponse


class TextProviderProtocol:
    """Common provider-aware text client over registered provider instances."""

    def __init__(
        self,
        *,
        model_spec: ModelSpec,
        stream: bool = False,
        reasoning_effort: str | None = None,
        text_verbosity: str | None = None,
        service_tier: str | None = None,
        provider_options: dict[str, Any] | None = None,
    ) -> None:
        self._parsed_model_spec = model_spec
        self._provider = get_provider(model_spec.provider)
        self.provider_name = model_spec.provider
        self.model_name = model_spec.model
        self.model_spec = str(model_spec)
        self.stream = stream
        self.reasoning_effort = reasoning_effort
        self.text_verbosity = text_verbosity
        self.service_tier = service_tier
        self.provider_options = provider_options or {}

    def request_response(
        self,
        *,
        messages: Sequence[LLMMessage],
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> LLMResponse:
        return request_with_retry(
            lambda: self._provider.request_response(
                messages=list(messages),
                model=self.model_name,
                reasoning_effort=self.reasoning_effort,
                text_verbosity=self.text_verbosity,
                service_tier=self.service_tier,
                provider_options=self.provider_options,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            ),
            provider=self.provider_name,
            model=self.model_name,
            operation_name="request_response",
        )

    def generate_response(
        self,
        *,
        system_prompt: str | None,
        user_text: str,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> LLMResponse:
        return self.request_response(
            messages=self._build_messages(system_prompt=system_prompt, user_text=user_text),
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

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
        return self.generate_response(
            system_prompt=system_prompt,
            user_text=user_text,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        ).text

    def stream_text(
        self,
        *,
        system_prompt: str | None,
        user_text: str,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        on_complete: Callable[[LLMResponse], None] | None = None,
    ) -> Iterator[str]:
        return stream_with_retry(
            lambda: self._provider.stream_response(
                messages=self._build_messages(system_prompt=system_prompt, user_text=user_text),
                model=self.model_name,
                reasoning_effort=self.reasoning_effort,
                text_verbosity=self.text_verbosity,
                service_tier=self.service_tier,
                provider_options=self.provider_options,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                on_complete=on_complete,
            ),
            provider=self.provider_name,
            model=self.model_name,
            operation_name="stream_response",
        )

    def create_chat(
        self,
        *,
        system_prompt: str | None = None,
        stream: bool | None = None,
        use_response_chain: bool = False,
    ) -> ChatSessionProtocol:
        return ChatSessionProtocol(
            provider=self,
            system_prompt=system_prompt,
            stream=self.stream if stream is None else stream,
            use_response_chain=use_response_chain,
        )

    @staticmethod
    def available_providers() -> tuple[str, ...]:
        return get_registered_providers()

    @staticmethod
    def _build_messages(*, system_prompt: str | None, user_text: str) -> list[LLMMessage]:
        messages: list[LLMMessage] = []
        if system_prompt:
            messages.append(LLMMessage(role="system", content=system_prompt))
        messages.append(LLMMessage(role="user", content=user_text))
        return messages

    @staticmethod
    def _iterate_response_text(text: str) -> Iterator[str]:
        def iterator() -> Iterator[str]:
            if text:
                yield text

        return iterator()

    def _resolve_stream(self, stream: bool | None) -> bool:
        if stream is None:
            return self.stream
        return stream


class ChatSessionProtocol:
    """
    Common in-memory chat session that always sends full message history.

    ``use_response_chain`` is accepted for API compatibility and intentionally
    ignored: provider sessions are now stateless and transport-agnostic.
    """

    def __init__(
        self,
        *,
        provider: TextProviderProtocol,
        system_prompt: str | None = None,
        stream: bool = False,
        use_response_chain: bool = False,
    ) -> None:
        self._provider = provider
        self._system_prompt = system_prompt
        self._stream = stream
        self._use_response_chain = use_response_chain
        self._messages: list[LLMMessage] = []
        self._pending_messages: list[LLMMessage] = []
        self._last_response: LLMResponse | None = None

    @property
    def messages(self) -> tuple[LLMMessage, ...]:
        return tuple(self._messages)

    @property
    def system_prompt(self) -> str | None:
        return self._system_prompt

    @property
    def last_response(self) -> LLMResponse | None:
        return self._last_response

    def set_system_prompt(self, prompt: str | None) -> None:
        self._system_prompt = prompt

    def add_message(self, role: str, content: str) -> None:
        message = LLMMessage(role=role, content=content)
        self._messages.append(message)
        self._pending_messages.append(message)

    def ask(
        self,
        user_text: str,
        *,
        stream: bool | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> str | Iterator[str]:
        self.add_message("user", user_text)
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

        if self._resolve_stream(stream):
            return self._stream_response(
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )

        response = self._provider.request_response(
            messages=self._build_request_messages(),
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

        self._finalize_response(response)
        return response.text

    def _build_request_messages(self) -> list[LLMMessage]:
        messages: list[LLMMessage] = []
        if self._system_prompt:
            messages.append(LLMMessage(role="system", content=self._system_prompt))
        messages.extend(self._messages)
        return messages

    def _finalize_response(self, response: LLMResponse) -> None:
        self._pending_messages.clear()
        self._last_response = response
        self._messages.append(LLMMessage(role="assistant", content=response.text))

    def _stream_response(
        self,
        *,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> Iterator[str]:
        chunks: list[str] = []

        def iterator() -> Iterator[str]:
            try:
                for delta in self._provider._provider.stream_response(
                    messages=self._build_request_messages(),
                    model=self._provider.model_name,
                    reasoning_effort=self._provider.reasoning_effort,
                    text_verbosity=self._provider.text_verbosity,
                    service_tier=self._provider.service_tier,
                    provider_options=self._provider.provider_options,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                ):
                    if delta:
                        chunks.append(delta)
                        yield delta
            finally:
                response = LLMResponse(
                    text="".join(chunks),
                    metadata={
                        "model": self._provider.model_name,
                        "provider": self._provider.provider_name,
                    },
                )
                self._finalize_response(response)

        return iterator()

    def _resolve_stream(self, stream: bool | None) -> bool:
        if stream is None:
            return self._stream
        return stream
