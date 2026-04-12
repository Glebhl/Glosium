import logging
import os
import sys
import threading
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FILE_PATH = Path("app.log")
LLM_USAGE_LOG_FILE_PATH = Path("llm_usage.log")
NOISY_LOGGER_LEVELS = {
    "httpx": logging.WARNING,
    "httpcore.http11": logging.WARNING,
    "httpcore.connection": logging.WARNING,
    "openai._base_client": logging.WARNING,
    "google_genai.models": logging.WARNING,
}

LOG_LEVEL_ENV_VAR = "GLOSIUM_LOG_LEVEL"
LOG_TO_FILE_ENV_VAR = "GLOSIUM_LOG_TO_FILE"
LLM_USAGE_ENABLED_ENV_VAR = "GLOSIUM_LLM_USAGE_ENABLED"


class TenthsMillisecondsFormatter(logging.Formatter):
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        timestamp = datetime.fromtimestamp(record.created)
        base = timestamp.strftime(datefmt or "%Y-%m-%d %H:%M:%S")
        # Keep one decimal place of the second, i.e. 10 ms precision.
        centiseconds = int(timestamp.microsecond / 10_000)
        return f"{base}.{centiseconds:02d}"


def resolve_log_level(level_name: str | None, default: int = logging.INFO) -> int:
    if not level_name:
        return default

    normalized = level_name.strip().upper()
    if normalized.isdigit():
        return int(normalized)

    resolved = logging.getLevelName(normalized)
    if isinstance(resolved, int):
        return resolved
    return default


def parse_env_flag(value: str | None, default: bool) -> bool:
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def read_logging_settings_from_env(*, env_loaded: bool) -> tuple[int, bool, bool]:
    if not env_loaded:
        return logging.INFO, False, False

    level = resolve_log_level(os.getenv(LOG_LEVEL_ENV_VAR), default=logging.INFO)
    log_to_file = parse_env_flag(os.getenv(LOG_TO_FILE_ENV_VAR), default=False)
    llm_usage_enabled = parse_env_flag(os.getenv(LLM_USAGE_ENABLED_ENV_VAR), default=True)
    return level, log_to_file, llm_usage_enabled


def _configure_library_loggers() -> None:
    for logger_name, level in NOISY_LOGGER_LEVELS.items():
        logging.getLogger(logger_name).setLevel(level)


def install_critical_error_logging() -> None:
    def _log_unhandled_exception(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback,
        *,
        source: str,
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logging.getLogger(source).critical(
            "Unhandled critical error",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    def _sys_excepthook(exc_type: type[BaseException], exc_value: BaseException, exc_traceback) -> None:
        _log_unhandled_exception(exc_type, exc_value, exc_traceback, source="app.unhandled")

    def _threading_excepthook(args: threading.ExceptHookArgs) -> None:
        _log_unhandled_exception(
            args.exc_type,
            args.exc_value,
            args.exc_traceback,
            source=f"app.unhandled.thread.{args.thread.name if args.thread else 'unknown'}",
        )

    def _asyncio_exception_handler(loop, context: dict[str, object]) -> None:
        logger = logging.getLogger("app.unhandled.asyncio")
        exception = context.get("exception")
        message = str(context.get("message", "Unhandled asyncio error"))

        if isinstance(exception, BaseException):
            logger.critical(message, exc_info=(type(exception), exception, exception.__traceback__))
            return

        logger.critical("%s | context=%s", message, context)

    sys.excepthook = _sys_excepthook
    threading.excepthook = _threading_excepthook

    try:
        import asyncio

        asyncio.get_event_loop_policy().get_event_loop().set_exception_handler(_asyncio_exception_handler)
    except RuntimeError:
        pass


def setup_logging(
    level: int = logging.INFO,
    log_to_file: bool = False,
    *,
    llm_usage_enabled: bool = True,
) -> None:
    fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = TenthsMillisecondsFormatter(fmt=fmt, datefmt=datefmt)

    root = logging.getLogger()
    root.setLevel(level)

    console_handlers = [
        handler
        for handler in root.handlers
        if isinstance(handler, logging.StreamHandler) and not isinstance(handler, RotatingFileHandler)
    ]
    if not console_handlers:
        console = logging.StreamHandler()
        root.addHandler(console)
        console_handlers = [console]

    for handler in console_handlers:
        handler.setLevel(level)
        handler.setFormatter(formatter)

    # Recreate file handlers on each startup so the log files are cleared and flags apply immediately.
    for handler in list(root.handlers):
        if isinstance(handler, RotatingFileHandler):
            root.removeHandler(handler)
            handler.close()

    if log_to_file:
        LOG_FILE_PATH.write_text("", encoding="utf-8")
        file_handler = RotatingFileHandler(
            filename=LOG_FILE_PATH,
            mode="w",
            maxBytes=5_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    llm_usage_logger = logging.getLogger("llm.usage")
    llm_usage_logger.setLevel(level)
    llm_usage_logger.propagate = False
    llm_usage_logger.disabled = not llm_usage_enabled
    for handler in list(llm_usage_logger.handlers):
        llm_usage_logger.removeHandler(handler)
        handler.close()

    if log_to_file and llm_usage_enabled:
        LLM_USAGE_LOG_FILE_PATH.write_text("", encoding="utf-8")
        llm_usage_handler = RotatingFileHandler(
            filename=LLM_USAGE_LOG_FILE_PATH,
            mode="w",
            maxBytes=5_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        llm_usage_handler.setLevel(level)
        llm_usage_handler.setFormatter(logging.Formatter("%(message)s"))
        llm_usage_logger.addHandler(llm_usage_handler)

    _configure_library_loggers()
    install_critical_error_logging()
