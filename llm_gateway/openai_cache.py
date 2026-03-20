from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Iterable
from uuid import uuid4


DEFAULT_CACHE_NAMESPACE = "lexiforge-openai"
MAX_PROMPT_CACHE_KEY_LENGTH = 64


def _join_key_parts(parts: Iterable[str | None]) -> str:
    return "::".join(part.strip() for part in parts if part and part.strip())


def stable_cache_key(*parts: str | None, namespace: str = DEFAULT_CACHE_NAMESPACE) -> str:
    """
    Build a stable cache key for OpenAI Prompt Caching routing.

    The API does prompt caching automatically for repeated prefixes, but providing
    a stable ``prompt_cache_key`` improves cache hit routing for similar requests.
    """
    raw_value = _join_key_parts((namespace, *parts))
    digest = sha256(raw_value.encode("utf-8")).hexdigest()
    available_namespace_chars = MAX_PROMPT_CACHE_KEY_LENGTH - len(digest) - 1
    namespace_prefix = namespace[:available_namespace_chars] if available_namespace_chars > 0 else ""
    return f"{namespace_prefix}:{digest}" if namespace_prefix else digest


@dataclass(slots=True)
class PromptCacheConfig:
    """
    Request-level prompt caching configuration.

    Notes:
    - OpenAI prompt caching is automatic and only becomes billable/useful for long
      repeated prefixes (1024+ tokens).
    - ``retention="24h"`` enables extended prompt cache retention when desired.
    """

    enabled: bool = True
    namespace: str = DEFAULT_CACHE_NAMESPACE
    retention: str | None = None

    def build_request_options(self, *parts: str | None) -> dict[str, Any]:
        if not self.enabled:
            return {}

        options: dict[str, Any] = {
            "prompt_cache_key": stable_cache_key(*parts, namespace=self.namespace),
        }
        if self.retention:
            options["prompt_cache_retention"] = self.retention
        return options


@dataclass(slots=True)
class ConversationState:
    """
    Transport state for a chat session.

    ``previous_response_id`` is optional transport optimization. The chat wrapper
    can still rebuild the full message history when manual edits are introduced.
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
