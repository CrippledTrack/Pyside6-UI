from __future__ import annotations

import logging
import os
import sys
import threading
import traceback
import warnings
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler

from ..utils.imports import get_platforms_constants

# Import platform constants using the utility function
constants = get_platforms_constants()
LOGGING_ENABLED = constants.LOGGING_ENABLED
LOG_TO_FILE = constants.LOG_TO_FILE

SAVE_LOGS_TO_FILE = LOG_TO_FILE
MAX_LOG_SIZE = 5 * 1024 * 1024  # 5MB
MAX_LOG_FILES = 5


class CustomFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "threadName"):
            record.threadName = "MainThread"
        elif record.threadName and record.threadName.startswith("Dummy-"):
            # Replace Qt internal thread names with more descriptive names
            # This handles cases where Qt creates internal threads with "Dummy-X" names
            current_thread = threading.current_thread()
            if hasattr(current_thread, 'objectName') and current_thread.objectName():
                record.threadName = current_thread.objectName()
            else:
                # Create a meaningful name based on the logger context
                logger_name = getattr(record, 'name', '')
                if 'plugin' in logger_name.lower():
                    record.threadName = "PluginLoader"
                elif 'main_window' in logger_name.lower():
                    record.threadName = "MainWindow"
                elif 'tab' in logger_name.lower():
                    record.threadName = "TabWorker"
                else:
                    record.threadName = "BackgroundWorker"
        
        if not hasattr(record, "process"):
            record.process = os.getpid()
        if record.exc_info:
            record.exc_text = "".join(traceback.format_exception(*record.exc_info))
        else:
            record.exc_text = ""
        return super().format(record)


def _configure_handlers(root_logger: logging.Logger) -> None:
    # Remove any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    formatter = CustomFormatter(
        "%(asctime)s - %(levelname)s - [%(threadName)s] - %(name)s - %(message)s"
        "%(exc_text)s"
    )

    if SAVE_LOGS_TO_FILE:
        from ..utils.paths import logs_dir
        log_dir = logs_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"app_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        file_handler = RotatingFileHandler(
            log_file, maxBytes=MAX_LOG_SIZE, backupCount=MAX_LOG_FILES, encoding="utf-8"
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)


def setup_logging() -> logging.Logger:
    """Configure logging with rotation and proper error handling.

    Matches the behavior previously implemented in main.py.
    """
    try:
        if not LOGGING_ENABLED:
            # Minimal no-op configuration to avoid noisy handlers
            logging.getLogger().handlers.clear()
            logging.getLogger().addHandler(logging.NullHandler())
            logger = logging.getLogger(__name__)
            logger.disabled = True
            return logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)

        _configure_handlers(root_logger)

        # Configure Python's built-in warnings
        logging.captureWarnings(True)

        def handle_exception(exc_type, exc_value, exc_traceback):  # type: ignore[no-redef]
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
            root_logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
            root_logger.error(
                "Exception Type: %s\nException Value: %s\nTraceback:\n%s",
                exc_type.__name__,
                str(exc_value),
                "".join(traceback.format_tb(exc_traceback)),
            )

        sys.excepthook = handle_exception

        def handle_warning(message, category, filename, lineno, file=None, line=None):
            root_logger.warning(
                f"Warning: {category.__name__}: {message}",
                extra={"filename": filename, "lineno": lineno, "line": line},
            )

        warnings.showwarning = handle_warning  # type: ignore[assignment]

        logger = logging.getLogger(__name__)
        logger.info("Logging configured successfully")
        return logger
    except Exception as e:  # pragma: no cover - fallback path
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s%(exc_info)s")
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to configure logging: {str(e)}")
        return logger
