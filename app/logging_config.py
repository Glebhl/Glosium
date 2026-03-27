import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

LOG_FILE_PATH = Path("app.log")
NOISY_LOGGER_LEVELS = {
    "httpcore.http11": logging.WARNING,
    "httpcore.connection": logging.WARNING,
    "openai._base_client": logging.WARNING,
}


def _configure_library_loggers() -> None:
    for logger_name, level in NOISY_LOGGER_LEVELS.items():
        logging.getLogger(logger_name).setLevel(level)


def setup_logging(level: int = logging.INFO, log_to_file: bool = False) -> None:
    fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

    root = logging.getLogger()
    root.setLevel(level)

    if not any(isinstance(handler, logging.StreamHandler) and not isinstance(handler, RotatingFileHandler) for handler in root.handlers):
        console = logging.StreamHandler()
        console.setLevel(level)
        console.setFormatter(formatter)
        root.addHandler(console)

    if log_to_file:
        # Recreate the file handler on each startup so the log file is cleared.
        for handler in list(root.handlers):
            if isinstance(handler, RotatingFileHandler):
                root.removeHandler(handler)
                handler.close()

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

    _configure_library_loggers()
