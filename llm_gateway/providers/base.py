from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence
from typing import Any, Callable

from ..types import LLMMessage, LLMResponse


class BaseProvider(ABC):
    name: str

    @abstractmethod
    def request_response(
        self,
        *,
        messages: Sequence[LLMMessage],
        model: str,
        reasoning_effort: str | None = None,
        text_verbosity: str | None = None,
        service_tier: str | None = None,
        provider_options: dict[str, Any] | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> LLMResponse:
        raise NotImplementedError

    @abstractmethod
    def stream_response(
        self,
        *,
        messages: Sequence[LLMMessage],
        model: str,
        reasoning_effort: str | None = None,
        text_verbosity: str | None = None,
        service_tier: str | None = None,
        provider_options: dict[str, Any] | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        on_complete: Callable[[LLMResponse], None] | None = None,
    ) -> Iterator[str]:
        raise NotImplementedError
