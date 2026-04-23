from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator, Sequence
from typing import Any, Callable, Literal, TypedDict

from google import genai

from ..observability import complete_request_log, fail_request_log, start_request_log
from .base import BaseProvider
from ..types import LLMTimings, LLMMessage, LLMResponse, LLMTokenUsage

logger = logging.getLogger(__name__)

GOOGLE_API_KEY_PATH = "google/api_key"

GOOGLE_REASONING_EFFORT_MINIMAL = "minimal"
GOOGLE_REASONING_EFFORT_LOW = "low"
GOOGLE_REASONING_EFFORT_MEDIUM = "medium"
GOOGLE_REASONING_EFFORT_HIGH = "high"
GOOGLE_REASONING_EFFORTS = (
    GOOGLE_REASONING_EFFORT_MINIMAL,
    GOOGLE_REASONING_EFFORT_LOW,
    GOOGLE_REASONING_EFFORT_MEDIUM,
    GOOGLE_REASONING_EFFORT_HIGH,
)

GOOGLE_SERVICE_TIER_STANDARD = "standard"
GOOGLE_SERVICE_TIER_FLEX = "flex"
GOOGLE_SERVICE_TIER_PRIORITY = "priority"
GOOGLE_SERVICE_TIERS = (
    GOOGLE_SERVICE_TIER_STANDARD,
    GOOGLE_SERVICE_TIER_FLEX,
    GOOGLE_SERVICE_TIER_PRIORITY,
)

GoogleContentRole = Literal["user", "model"]
GoogleThinkingLevel = Literal["MINIMAL", "LOW", "MEDIUM", "HIGH"]


class GooglePart(TypedDict):
    text: str


class GoogleContent(TypedDict):
    role: GoogleContentRole
    parts: list[GooglePart]


class GoogleThinkingConfig(TypedDict):
    thinking_level: GoogleThinkingLevel


class GoogleGenerationConfig(TypedDict, total=False):
    system_instruction: str
    thinking_config: GoogleThinkingConfig
    service_tier: str
    temperature: float
    max_output_tokens: int
    should_return_http_response: bool


class GoogleProvider(BaseProvider):
    name = "google"

    def __init__(self) -> None:
        self._client: genai.Client | None = None

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
        client = self._setup_client(provider_options)

        config = self._build_generation_config(
            messages=messages,
            reasoning_effort=reasoning_effort,
            text_verbosity=text_verbosity,
            service_tier=service_tier,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            include_http_response=True,
        )
        contents = self._build_contents(messages)
        request_log = start_request_log(
            provider=self.name,
            model=model,
            messages=messages,
            reasoning_effort=reasoning_effort,
            text_verbosity=text_verbosity,
            service_tier=service_tier,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            provider_options=provider_options,
            stream=False,
        )

        started_at = time.perf_counter()
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
        except Exception as exc:
            fail_request_log(request_log, exc)
            raise

        response_text = self._extract_text(response)
        usage = self._build_usage(response)
        response_id = self._extract_response_id(response)

        actual_model = self._extract_response_model(response) or model
        llm_response = LLMResponse(
            text=response_text,
            response_id=response_id,
            usage=usage,
            timings=LLMTimings(total_seconds=time.perf_counter() - started_at),
            raw=response,
            metadata={
                "model": actual_model,
                "provider": self.name,
                "input_model": model,
                "output_model": actual_model,
                "service_tier": self._extract_service_tier(response, service_tier),
            },
        )
        complete_request_log(request_log, llm_response)
        return llm_response

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
        client = self._setup_client(provider_options)

        config = self._build_generation_config(
            messages=messages,
            reasoning_effort=reasoning_effort,
            text_verbosity=text_verbosity,
            service_tier=service_tier,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            include_http_response=False,
        )
        contents = self._build_contents(messages)
        request_log = start_request_log(
            provider=self.name,
            model=model,
            messages=messages,
            reasoning_effort=reasoning_effort,
            text_verbosity=text_verbosity,
            service_tier=service_tier,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            provider_options=provider_options,
            stream=True,
        )

        try:
            raw_stream = client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=config,
            )
        except Exception as exc:
            fail_request_log(request_log, exc)
            raise

        def iterator() -> Iterator[str]:
            started_at = time.perf_counter()
            first_delta_at: float | None = None
            chunks: list[str] = []
            last_chunk: Any | None = None
            failure: BaseException | None = None

            try:
                for chunk in raw_stream:
                    last_chunk = chunk
                    text = chunk.text or ""
                    if not text:
                        continue

                    if first_delta_at is None:
                        first_delta_at = time.perf_counter()
                        logger.debug(
                            "Received first Google delta after %.2fs",
                            first_delta_at - started_at,
                        )

                    chunks.append(text)
                    yield text
            except Exception as e:
                failure = RuntimeError(f"Google streaming request failed: {e}")
                raise failure from e
            finally:
                total_seconds = time.perf_counter() - started_at
                response = LLMResponse(
                    text="".join(chunks),
                    response_id=self._extract_response_id(last_chunk),
                    usage=self._build_usage(last_chunk),
                    timings=LLMTimings(
                        total_seconds=total_seconds,
                        time_to_first_token_seconds=(
                            first_delta_at - started_at if first_delta_at is not None else None
                        ),
                        stream_seconds=(
                            total_seconds - (first_delta_at - started_at)
                            if first_delta_at is not None
                            else None
                        ),
                    ),
                    raw=last_chunk,
                    metadata={
                        "model": self._extract_response_model(last_chunk) or model,
                        "provider": self.name,
                        "input_model": model,
                        "output_model": self._extract_response_model(last_chunk) or model,
                        "service_tier": self._extract_service_tier(last_chunk, service_tier),
                    },
                )
                if failure is not None:
                    fail_request_log(request_log, failure, response=response)
                    return
                if on_complete is not None:
                    on_complete(response)
                complete_request_log(request_log, response)
                logger.debug(
                    "Streaming response finished in %.2fs",
                    total_seconds,
                )

        return iterator()

    def _setup_client(self, provider_options: dict[str, Any] | None) -> genai.Client:
        if self._client is not None:
            return self._client

        from app.api_keys import get_api_keys_store

        api_key = get_api_keys_store().get_value(GOOGLE_API_KEY_PATH)
        if not api_key:
            raise RuntimeError("Google API key is missing.")

        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if provider_options:
            client_kwargs.update(provider_options)

        self._client = genai.Client(**client_kwargs)
        return self._client

    def _build_contents(self, messages: Sequence[LLMMessage]) -> list[GoogleContent]:
        contents: list[GoogleContent] = []

        for msg in messages:
            if msg.role == "system":
                continue

            role = "model" if msg.role == "assistant" else "user"
            contents.append(
                {
                    "role": role,
                    "parts": [{"text": msg.content}],
                }
            )

        return contents

    def _build_generation_config(
        self,
        *,
        messages: Sequence[LLMMessage],
        reasoning_effort: str | None,
        text_verbosity: str | None,
        service_tier: str | None,
        temperature: float | None,
        max_output_tokens: int | None,
        include_http_response: bool,
    ) -> GoogleGenerationConfig:
        system_instruction = self._extract_system_instruction(messages)
        thinking_config = self._build_thinking_config(reasoning_effort)
        normalized_service_tier = self._normalize_service_tier(service_tier)

        if text_verbosity:
            logger.debug(
                "Gemini API has no native verbosity parameter; text_verbosity=%s is accepted but ignored.",
                text_verbosity,
            )

        config: GoogleGenerationConfig = {
            "should_return_http_response": include_http_response,
        }
        if system_instruction is not None:
            config["system_instruction"] = system_instruction
        if thinking_config is not None:
            config["thinking_config"] = thinking_config
        if normalized_service_tier is not None:
            config["service_tier"] = normalized_service_tier
        if temperature is not None:
            config["temperature"] = temperature
        if max_output_tokens is not None:
            config["max_output_tokens"] = max_output_tokens

        return config

    @staticmethod
    def _extract_system_instruction(
        messages: Sequence[LLMMessage],
    ) -> str | None:
        system_parts = [msg.content for msg in messages if msg.role == "system"]
        if not system_parts:
            return None
        return "\n\n".join(system_parts)

    @staticmethod
    def _build_thinking_config(
        reasoning_effort: str | None,
    ) -> GoogleThinkingConfig | None:
        thinking_level = GoogleProvider._map_reasoning_effort_to_thinking_level(
            reasoning_effort
        )
        if thinking_level is None:
            return None

        return {"thinking_level": thinking_level}

    @staticmethod
    def _map_reasoning_effort_to_thinking_level(
        reasoning_effort: str | None,
    ) -> GoogleThinkingLevel | None:
        if reasoning_effort is None:
            return None

        normalized = reasoning_effort.strip().lower()
        mapping = {
            GOOGLE_REASONING_EFFORT_MINIMAL: "MINIMAL",
            GOOGLE_REASONING_EFFORT_LOW: "LOW",
            GOOGLE_REASONING_EFFORT_MEDIUM: "MEDIUM",
            GOOGLE_REASONING_EFFORT_HIGH: "HIGH",
        }

        try:
            return mapping[normalized]
        except KeyError as e:
            raise ValueError(
                f"Unsupported Google reasoning_effort: {reasoning_effort!r}. "
                f"Expected one of: {', '.join(GOOGLE_REASONING_EFFORTS)}."
            ) from e

    @staticmethod
    def _normalize_service_tier(service_tier: str | None) -> str | None:
        if service_tier is None:
            return None

        normalized = service_tier.strip().lower()
        allowed = set(GOOGLE_SERVICE_TIERS)

        if normalized not in allowed:
            raise ValueError(
                f"Unsupported Google service_tier: {service_tier!r}. "
                f"Expected one of: {', '.join(GOOGLE_SERVICE_TIERS)}."
            )

        return normalized

    @staticmethod
    def _extract_service_tier(response: Any, requested: str | None) -> str | None:
        sdk_http_response = getattr(response, "sdk_http_response", None)
        if not sdk_http_response:
            return requested

        headers = getattr(sdk_http_response, "headers", None)
        if not headers:
            return requested

        actual = headers.get("x-gemini-service-tier")
        return actual or requested

    @staticmethod
    def _extract_text(response: Any) -> str:
        text = getattr(response, "text", None)
        if isinstance(text, str) and text:
            return text

        for candidate in getattr(response, "candidates", None) or []:
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", None) or []:
                part_text = getattr(part, "text", None)
                if isinstance(part_text, str) and part_text:
                    return part_text

        payload = GoogleProvider._extract_http_payload(response)
        if not isinstance(payload, dict):
            return ""

        for candidate in payload.get("candidates") or []:
            content = candidate.get("content") if isinstance(candidate, dict) else None
            if not isinstance(content, dict):
                continue
            for part in content.get("parts") or []:
                if not isinstance(part, dict):
                    continue
                part_text = part.get("text")
                if isinstance(part_text, str) and part_text:
                    return part_text

        return ""

    @staticmethod
    def _extract_response_id(response: Any) -> str | None:
        response_id = getattr(response, "response_id", None)
        if isinstance(response_id, str) and response_id:
            return response_id

        payload = GoogleProvider._extract_http_payload(response)
        if not isinstance(payload, dict):
            return None

        extracted = payload.get("responseId")
        return extracted if isinstance(extracted, str) and extracted else None

    @staticmethod
    def _extract_response_model(response: Any) -> str | None:
        model_version = getattr(response, "model_version", None)
        if isinstance(model_version, str) and model_version:
            return model_version

        payload = GoogleProvider._extract_http_payload(response)
        if not isinstance(payload, dict):
            return None

        extracted = payload.get("modelVersion")
        return extracted if isinstance(extracted, str) and extracted else None

    @staticmethod
    def _build_usage(response: Any) -> LLMTokenUsage | None:
        usage_info = getattr(response, "usage_metadata", None)
        if usage_info is None:
            payload = GoogleProvider._extract_http_payload(response)
            usage_info = payload.get("usageMetadata") if isinstance(payload, dict) else None

        if not usage_info:
            return None

        input_tokens = GoogleProvider._read_usage_value(
            usage_info,
            "prompt_token_count",
            "promptTokenCount",
        )
        output_tokens = GoogleProvider._read_usage_value(
            usage_info,
            "candidates_token_count",
            "candidatesTokenCount",
        )

        # fallback to the more generic response token counter if that's what the endpoint returned
        if output_tokens is None:
            output_tokens = GoogleProvider._read_usage_value(
                usage_info,
                "response_token_count",
                "responseTokenCount",
            )

        total_tokens = GoogleProvider._read_usage_value(
            usage_info,
            "total_token_count",
            "totalTokenCount",
        )

        return LLMTokenUsage(
            input_tokens=input_tokens or 0,
            output_tokens=output_tokens or 0,
            total_tokens=total_tokens or ((input_tokens or 0) + (output_tokens or 0)),
            details={
                "thoughts_token_count": GoogleProvider._read_usage_value(
                    usage_info,
                    "thoughts_token_count",
                    "thoughtsTokenCount",
                ),
                "cached_content_token_count": GoogleProvider._read_usage_value(
                    usage_info,
                    "cached_content_token_count",
                    "cachedContentTokenCount",
                ),
                "traffic_type": GoogleProvider._read_usage_value(
                    usage_info,
                    "traffic_type",
                    "trafficType",
                ),
            },
        )

    @staticmethod
    def _read_usage_value(usage_info: Any, attr_name: str, payload_key: str) -> Any:
        if isinstance(usage_info, dict):
            return usage_info.get(payload_key)
        return getattr(usage_info, attr_name, None)

    @staticmethod
    def _extract_http_payload(response: Any) -> dict[str, Any] | None:
        sdk_http_response = getattr(response, "sdk_http_response", None)
        if sdk_http_response is None:
            return None

        body = getattr(sdk_http_response, "body", None)
        if not isinstance(body, str) or not body.strip():
            return None

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            logger.warning("Failed to decode Google sdk_http_response body as JSON.")
            return None

        return payload if isinstance(payload, dict) else None
