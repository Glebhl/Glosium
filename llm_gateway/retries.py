from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from typing import TypeVar


logger = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES = {503}
_MAX_RETRIES = 5
_BASE_DELAY_SECONDS = 0.5
_MAX_DELAY_SECONDS = 5.0

ResponseT = TypeVar("ResponseT")


def request_with_retry(
    operation: Callable[[], ResponseT],
    *,
    provider: str,
    model: str,
    operation_name: str,
) -> ResponseT:
    attempt = 0
    while True:
        try:
            return operation()
        except Exception as exc:  # noqa: BLE001
            if not _should_retry_exception(exc) or attempt >= _MAX_RETRIES:
                raise
            attempt += 1
            _sleep_before_retry(
                attempt=attempt,
                provider=provider,
                model=model,
                operation_name=operation_name,
                exc=exc,
            )


def stream_with_retry(
    iterator_factory: Callable[[], Iterator[str]],
    *,
    provider: str,
    model: str,
    operation_name: str,
) -> Iterator[str]:
    def iterator() -> Iterator[str]:
        attempt = 0
        while True:
            saw_output = False
            try:
                for chunk in iterator_factory():
                    if chunk:
                        saw_output = True
                    yield chunk
                return
            except Exception as exc:  # noqa: BLE001
                if saw_output or not _should_retry_exception(exc) or attempt >= _MAX_RETRIES:
                    raise
                attempt += 1
                _sleep_before_retry(
                    attempt=attempt,
                    provider=provider,
                    model=model,
                    operation_name=operation_name,
                    exc=exc,
                )

    return iterator()


def _should_retry_exception(exc: BaseException) -> bool:
    return _extract_status_code(exc) in _RETRYABLE_STATUS_CODES


def _extract_status_code(exc: BaseException) -> int | None:
    for candidate_exc in _iter_exception_chain(exc):
        status_code = _extract_status_code_single(candidate_exc)
        if status_code is not None:
            return status_code
    return None


def _extract_status_code_single(exc: BaseException) -> int | None:
    candidates = [
        getattr(exc, "status_code", None),
        getattr(exc, "status", None),
        getattr(exc, "code", None),
    ]

    response = getattr(exc, "response", None)
    if response is not None:
        candidates.extend([
            getattr(response, "status_code", None),
            getattr(response, "status", None),
        ])

    for candidate in candidates:
        if isinstance(candidate, bool):
            continue
        if isinstance(candidate, int):
            return candidate
        if isinstance(candidate, str) and candidate.isdigit():
            return int(candidate)

    message = str(exc)
    if "503" in message:
        return 503
    return None


def _iter_exception_chain(exc: BaseException):
    current: BaseException | None = exc
    seen_ids: set[int] = set()
    while current is not None and id(current) not in seen_ids:
        seen_ids.add(id(current))
        yield current
        next_exc = getattr(current, "__cause__", None)
        if next_exc is None:
            next_exc = getattr(current, "__context__", None)
        current = next_exc


def _sleep_before_retry(
    *,
    attempt: int,
    provider: str,
    model: str,
    operation_name: str,
    exc: BaseException,
) -> None:
    delay_seconds = min(_BASE_DELAY_SECONDS * (2 ** (attempt - 1)), _MAX_DELAY_SECONDS)
    logger.warning(
        "Retrying %s for %s:%s after transient 503 (%s/%s) in %.1fs: %s",
        operation_name,
        provider,
        model,
        attempt,
        _MAX_RETRIES,
        delay_seconds,
        exc,
    )
    time.sleep(delay_seconds)
