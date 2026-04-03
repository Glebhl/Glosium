from __future__ import annotations

from dataclasses import dataclass


DEFAULT_PROVIDER = "openai"


@dataclass(frozen=True, slots=True)
class ModelSpec:
    provider: str
    model: str

    def __str__(self) -> str:
        return f"{self.provider}:{self.model}"


def parse_model_spec(
    value: str | None,
    *,
    default_provider: str = DEFAULT_PROVIDER,
) -> ModelSpec:
    normalized = (value or "").strip()
    if not normalized:
        raise ValueError("Model name must not be empty.")

    if ":" not in normalized:
        return ModelSpec(provider=default_provider, model=normalized)

    provider, model = normalized.split(":", 1)
    provider = provider.strip()
    model = model.strip()
    if not provider or not model:
        raise ValueError(
            "Model must use the format 'provider:model', for example 'openai:gpt-5'."
        )

    return ModelSpec(provider=provider, model=model)
