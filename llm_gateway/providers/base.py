from __future__ import annotations

from typing import Iterator, Protocol, runtime_checkable


@runtime_checkable
class ChatSessionProtocol(Protocol):
    def add_message(self, role: str, content: str) -> None: ...

    def ask(
        self,
        user_text: str,
        *,
        stream: bool | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> str | Iterator[str]: ...

    def create_response(
        self,
        *,
        stream: bool | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> str | Iterator[str]: ...


@runtime_checkable
class TextProviderProtocol(Protocol):
    provider_name: str
    model_name: str
    model_spec: str

    def generate_text(
        self,
        *,
        system_prompt: str | None,
        user_text: str,
        stream: bool | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> str | Iterator[str]: ...

    def stream_text(
        self,
        *,
        system_prompt: str | None,
        user_text: str,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> Iterator[str]: ...

    def create_chat(
        self,
        *,
        system_prompt: str | None = None,
        stream: bool | None = None,
        use_response_chain: bool = False,
    ) -> ChatSessionProtocol: ...
