from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4


@dataclass(slots=True)
class PromptCachingConfig:
    """
    Provider-agnostic prompt caching settings.

    For OpenAI the cache itself is automatic on the platform side. We do not send
    request-level cache keys here because that proved unreliable in practice for
    this project. Instead we keep request prefixes stable and use this config only
    for eligibility heuristics and future provider-specific extensions.
    """

    enabled: bool = True
    min_supported_tokens: int = 1024
    estimated_chars_per_token: int = 4

    def is_cache_candidate(
        self,
        *,
        instructions: str | None,
        input_items: list[dict[str, str]],
        previous_response_id: str | None = None,
    ) -> bool:
        if not self.enabled or previous_response_id:
            return False

        total_chars = len(instructions or "")
        total_chars += sum(len(item.get("content", "")) for item in input_items)
        return total_chars >= self.min_supported_tokens * self.estimated_chars_per_token


@dataclass(slots=True)
class ConversationState:
    """
    Transport state for a chat session.

    ``previous_response_id`` is an optional optimization. The session can still
    rebuild the full message history when we need a stable prompt prefix.
    """

    session_id: str = field(default_factory=lambda: uuid4().hex)
    previous_response_id: str | None = None
    chain_is_valid: bool = True

    def invalidate_chain(self) -> None:
        self.previous_response_id = None
        self.chain_is_valid = False

    def remember_response(self, response_id: str) -> None:
        self.previous_response_id = response_id
        self.chain_is_valid = True
