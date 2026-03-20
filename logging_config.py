import logging
from logging.handlers import RotatingFileHandler


NOISY_LOGGERS = (
    "openai",
    "httpx",
    "httpcore",
)


def _configure_external_loggers() -> None:
    for logger_name in NOISY_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def setup_logging(level: int = logging.INFO) -> None:
    fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    root = logging.getLogger()
    root.setLevel(level)
    _configure_external_loggers()

    if root.handlers:
        return

    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))

    file_handler = RotatingFileHandler(
        filename="app.log",
        maxBytes=5_000_000,   # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))

    root.addHandler(console)
    root.addHandler(file_handler)
