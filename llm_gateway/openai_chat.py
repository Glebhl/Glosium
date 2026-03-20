from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Literal

from .openai_cache import ConversationState
from .openai_wrapper import (
    OpenAITextClient,
    build_input_message,
    extract_response_text,
    extract_stream_error,
    log_response_usage,
)


ChatRole = Literal["user", "assistant"]


@dataclass(slots=True, frozen=True)
class ChatMessage:
    role: ChatRole
    content: str

    def to_input_item(self) -> dict[str, str]:
        return build_input_message(self.role, self.content)


class OpenAIChatSession:
    """
    In-memory chat session over OpenAI Responses API.

    By default the class rebuilds the full message history every turn. That keeps
    the request prefix stable, which is useful for automatic prompt caching and
    makes future edit/remove operations easy to add.

    If ``use_response_chain=True`` is enabled, the class will use
    ``previous_response_id`` when possible to send smaller request payloads.
    """

    def __init__(
        self,
        *,
        client: OpenAITextClient,
        system_prompt: str | None = None,
        stream: bool = False,
        use_response_chain: bool = False,
    ) -> None:
        self._client = client
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
        cache_scope = self._build_cache_scope()
        use_stream = self._stream if stream is None else stream

        if use_stream:
            return self._stream_response(
                request_input=request_input,
                cache_scope=cache_scope,
                previous_response_id=previous_response_id,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )

        response = self._client.create_response(
            instructions=self._system_prompt,
            input_items=request_input,
            cache_scope=cache_scope,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            previous_response_id=previous_response_id,
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

    def _build_cache_scope(self) -> tuple[str, ...]:
        return (
            "chat",
            self._client.model,
            self._state.session_id,
            self._system_prompt or "",
        )

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
        cache_scope: tuple[str, ...],
        previous_response_id: str | None,
        temperature: float | None,
        max_output_tokens: int | None,
    ) -> Iterator[str]:
        raw_stream = self._client.stream_response(
            instructions=self._system_prompt,
            input_items=request_input,
            cache_scope=cache_scope,
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
                            model=self._client.model,
                            operation="chat_stream_response",
                        )
                    assistant_text = "".join(chunks) if chunks else (finalized_text or "")
                    self._finalize_response(
                        assistant_text=assistant_text,
                        response_id=response_id,
                    )

        return iterator()
