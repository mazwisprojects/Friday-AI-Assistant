"""
Centralized logging configuration for F.R.I.D.A.Y.

Usage:
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Message: %s", value)
"""

import logging
import logging.handlers
import os
import sys
import builtins
from pathlib import Path


_ORIGINAL_PRINT = builtins.print


def _capture_legacy_prints() -> None:
    """Route legacy application prints through the configured logger."""
    if os.getenv("FRIDAY_CAPTURE_PRINTS", "1").lower() in {"0", "false", "no", "off"}:
        return
    if getattr(builtins.print, "_friday_logger_bridge", False):
        return

    def logged_print(*values, **kwargs):
        # File-directed output is commonly a protocol or a test fixture.
        if kwargs.get("file") is not None:
            return _ORIGINAL_PRINT(*values, **kwargs)

        message = kwargs.get("sep", " ").join(str(value) for value in values)
        if not message:
            return

        lowered = message.lower()
        if any(marker in lowered for marker in ("error", "exception", "[err]", "critical")):
            level = logging.ERROR
        elif any(marker in lowered for marker in ("warning", "warn", "[warn]", "[!")):
            level = logging.WARNING
        elif "debug" in lowered:
            level = logging.DEBUG
        else:
            level = logging.INFO
        logging.getLogger("legacy.print").log(level, "%s", message)

    logged_print._friday_logger_bridge = True
    builtins.print = logged_print


def setup_logging(
    log_level: str = None,
    log_file: str = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
) -> None:
    """
    Configure logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
                  Defaults to FRIDAY_LOG_LEVEL env var or INFO.
        log_file: Path to log file. Defaults to logs/friday.log in project root.
        max_bytes: Maximum size of each log file before rotation.
        backup_count: Number of backup log files to keep.
    """
    # Determine log level
    level_name = log_level or os.getenv("FRIDAY_LOG_LEVEL", "INFO")
    level = getattr(logging, level_name.upper(), logging.INFO)

    # Determine log file path
    if log_file is None:
        root_dir = Path(__file__).resolve().parent.parent
        log_dir = root_dir / "logs"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / "friday.log"
    else:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)

    # Create formatters
    detailed_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    simple_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates on re-initialization
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler (stdout for INFO and below, stderr for WARNING+)
    class _LevelFilter(logging.Filter):
        def __init__(self, max_level: int):
            super().__init__()
            self.max_level = max_level

        def filter(self, record: logging.LogRecord) -> bool:
            return record.levelno <= self.max_level

    console_out = logging.StreamHandler(sys.stdout)
    console_out.setLevel(logging.DEBUG)
    console_out.addFilter(_LevelFilter(logging.INFO))
    console_out.setFormatter(simple_formatter)
    root_logger.addHandler(console_out)

    console_err = logging.StreamHandler(sys.stderr)
    console_err.setLevel(logging.WARNING)
    console_err.setFormatter(detailed_formatter)
    root_logger.addHandler(console_err)

    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        filename=str(log_file),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(file_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("socketio").setLevel(logging.WARNING)
    logging.getLogger("engineio").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)

    # Make unexpected failures visible in the same rotating log as normal events.
    def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        root_logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = handle_uncaught_exception
    _capture_legacy_prints()


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.

    Args:
        name: Logger name, typically __name__.

    Returns:
        Configured logger instance.
    """
    return logging.getLogger(name)
