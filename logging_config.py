import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler


NOISY_LOGGERS = (
    "openai",
    "httpx",
    "httpcore",
)
LOG_FILE_PATH = Path(__file__).resolve().parent / "app.log"


def _configure_external_loggers() -> None:
    for logger_name in NOISY_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def setup_logging(level: int = logging.INFO, log_to_file: bool = False) -> None:
    fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

    root = logging.getLogger()
    root.setLevel(level)
    _configure_external_loggers()

    if not any(isinstance(handler, logging.StreamHandler) and not isinstance(handler, RotatingFileHandler) for handler in root.handlers):
        console = logging.StreamHandler()
        console.setLevel(level)
        console.setFormatter(formatter)
        root.addHandler(console)

    has_file_handler = any(isinstance(handler, RotatingFileHandler) for handler in root.handlers)
    if log_to_file and not has_file_handler:
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
