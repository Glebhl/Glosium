from __future__ import annotations

import functools
import inspect
import logging
import sys
import threading
from types import TracebackType
from typing import Any, Callable, TypeVar

try:
    from PySide6.QtCore import QtMsgType, qInstallMessageHandler
except ImportError:  # pragma: no cover - allows reuse outside Qt runtime
    QtMsgType = None
    qInstallMessageHandler = None

F = TypeVar("F", bound=Callable[..., Any])

_CALLBACK_CACHE_ATTR = "_logged_callback_cache"


def install_global_exception_logging(logger: logging.Logger | None = None) -> None:
    """Install global Python exception hooks that forward to logging."""
    active_logger = logger or logging.getLogger(__name__)

    def _log_unhandled_exception(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: TracebackType | None,
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            return
        active_logger.critical(
            "Unhandled exception reached the global excepthook",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    def _log_thread_exception(args: threading.ExceptHookArgs) -> None:
        if issubclass(args.exc_type, KeyboardInterrupt):
            return
        active_logger.critical(
            'Unhandled exception in thread "%s"',
            getattr(args.thread, "name", "<unknown>"),
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    def _log_unraisable(unraisable: sys.UnraisableHookArgs) -> None:
        active_logger.error(
            "Unraisable exception detected for object %r",
            unraisable.object,
            exc_info=(
                unraisable.exc_type,
                unraisable.exc_value,
                unraisable.exc_traceback,
            ),
        )

    sys.excepthook = _log_unhandled_exception
    threading.excepthook = _log_thread_exception
    sys.unraisablehook = _log_unraisable

    if qInstallMessageHandler is not None and QtMsgType is not None:
        def _qt_message_handler(msg_type, context, message) -> None:
            category = getattr(context, "category", "") or "<qt>"
            file_name = getattr(context, "file", None)
            line_number = getattr(context, "line", 0)
            location = f"{file_name}:{line_number}" if file_name else "<unknown>"

            if msg_type == QtMsgType.QtDebugMsg:
                level = logging.DEBUG
            elif msg_type == QtMsgType.QtInfoMsg:
                level = logging.INFO
            elif msg_type == QtMsgType.QtWarningMsg:
                level = logging.WARNING
            else:
                level = logging.ERROR

            active_logger.log(
                level,
                "Qt message [%s] at %s: %s",
                category,
                location,
                message,
            )

        qInstallMessageHandler(_qt_message_handler)


def make_logged_callback(
    callback: F,
    *,
    logger: logging.Logger | None = None,
    message: str | None = None,
    reraise: bool = False,
) -> F:
    """Wrap a callback so exceptions are always logged."""
    active_logger = logger or logging.getLogger(callback.__module__)
    callback_name = getattr(callback, "__qualname__", repr(callback))
    log_message = message or f"Unhandled exception in callback {callback_name}"
    signature = inspect.signature(callback)
    parameters = tuple(signature.parameters.values())
    accepts_varargs = any(
        parameter.kind == inspect.Parameter.VAR_POSITIONAL for parameter in parameters
    )
    positional_capacity = sum(
        parameter.kind
        in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
        for parameter in parameters
    )

    @functools.wraps(callback)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            positional_args = args if accepts_varargs else args[:positional_capacity]
            return callback(*positional_args, **kwargs)
        except Exception:  # noqa: BLE001
            active_logger.exception(log_message)
            if reraise:
                raise
            return None

    return wrapper  # type: ignore[return-value]


def get_logged_bound_method(
    instance: Any,
    method_name: str,
    *,
    logger: logging.Logger | None = None,
    message: str | None = None,
    reraise: bool = False,
) -> Callable[..., Any]:
    """Return a cached logged wrapper for an instance method."""
    cache = instance.__dict__.setdefault(_CALLBACK_CACHE_ATTR, {})
    cache_key = (method_name, reraise)

    if cache_key not in cache:
        bound_method = getattr(instance, method_name)
        cache[cache_key] = make_logged_callback(
            bound_method,
            logger=logger,
            message=message,
            reraise=reraise,
        )

    return cache[cache_key]
