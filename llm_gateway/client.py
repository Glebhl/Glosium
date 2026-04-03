from __future__ import annotations

from typing import Any, Iterator

from .cache import PromptCachingConfig
from .model_spec import DEFAULT_PROVIDER, ModelSpec, parse_model_spec
from .providers import ensure_builtin_providers_registered
from .providers.base import ChatSessionProtocol, TextProviderProtocol
from .providers.registry import create_provider, get_registered_providers


class LLMTextClient:
    def __init__(
        self,
        *,
        model: str = "openai:gpt-5-mini",
        stream: bool = False,
        cache_config: PromptCachingConfig | None = None,
        base_url: str | None = None,
        reasoning_effort: str | None = None,
        text_verbosity: str | None = None,
        service_tier: str | None = None,
        provider_options: dict[str, Any] | None = None,
    ) -> None:
        ensure_builtin_providers_registered()

        self.model_spec: ModelSpec = parse_model_spec(model)
        self.model = str(self.model_spec)
        self.model_name = self.model_spec.model
        self.provider_name = self.model_spec.provider
        self.stream = stream
        self.cache_config = cache_config or PromptCachingConfig()
        self._provider: TextProviderProtocol = create_provider(
            model_spec=self.model_spec,
            stream=stream,
            cache_config=self.cache_config,
            base_url=base_url,
            reasoning_effort=reasoning_effort,
            text_verbosity=text_verbosity,
            service_tier=service_tier,
            provider_options=provider_options,
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
        return self._provider.generate_text(
            system_prompt=system_prompt,
            user_text=user_text,
            stream=stream,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

    def stream_text(
        self,
        *,
        system_prompt: str | None,
        user_text: str,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> Iterator[str]:
        return self._provider.stream_text(
            system_prompt=system_prompt,
            user_text=user_text,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

    def create_chat(
        self,
        *,
        system_prompt: str | None = None,
        stream: bool | None = None,
        use_response_chain: bool = False,
    ) -> ChatSessionProtocol:
        return self._provider.create_chat(
            system_prompt=system_prompt,
            stream=stream,
            use_response_chain=use_response_chain,
        )

    @staticmethod
    def available_providers() -> tuple[str, ...]:
        ensure_builtin_providers_registered()
        return get_registered_providers()


class OpenAITextClient(LLMTextClient):
    def __init__(self, *, model: str = "gpt-5-mini", **kwargs: Any) -> None:
        super().__init__(model=self._normalize_model(model), **kwargs)

    @staticmethod
    def _normalize_model(model: str) -> str:
        spec = parse_model_spec(model, default_provider=DEFAULT_PROVIDER)
        if spec.provider != DEFAULT_PROVIDER:
            raise ValueError(
                f"OpenAITextClient only supports the '{DEFAULT_PROVIDER}' provider, got {spec.provider!r}."
            )
        return str(spec)
