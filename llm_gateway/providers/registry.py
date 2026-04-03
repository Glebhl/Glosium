from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..cache import PromptCachingConfig
from ..model_spec import ModelSpec
from .base import TextProviderProtocol


ProviderFactory = Callable[..., TextProviderProtocol]

_PROVIDERS: dict[str, ProviderFactory] = {}


def register_provider(name: str, factory: ProviderFactory) -> None:
    _PROVIDERS[name.strip().lower()] = factory


def create_provider(
    *,
    model_spec: ModelSpec,
    stream: bool,
    cache_config: PromptCachingConfig,
    base_url: str | None = None,
    reasoning_effort: str | None = None,
    text_verbosity: str | None = None,
    service_tier: str | None = None,
    provider_options: dict[str, Any] | None = None,
) -> TextProviderProtocol:
    provider_name = model_spec.provider.lower()
    try:
        factory = _PROVIDERS[provider_name]
    except KeyError as exc:
        available = ", ".join(sorted(_PROVIDERS)) or "none"
        raise ValueError(
            f"Unknown LLM provider {model_spec.provider!r}. Available providers: {available}."
        ) from exc

    return factory(
        model_spec=model_spec,
        stream=stream,
        cache_config=cache_config,
        base_url=base_url,
        reasoning_effort=reasoning_effort,
        text_verbosity=text_verbosity,
        service_tier=service_tier,
        provider_options=provider_options or {},
    )


def get_registered_providers() -> tuple[str, ...]:
    return tuple(sorted(_PROVIDERS))
