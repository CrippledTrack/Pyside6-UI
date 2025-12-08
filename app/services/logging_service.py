from __future__ import annotations

import logging
import os
import sys
import threading
import traceback
import warnings
from datetime import datetime
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler

from ..utils.imports import get_platforms_constants
from ..utils.admin import is_dev_mode

# Import platform constants using the utility function
constants = get_platforms_constants()
LOGGING_ENABLED = constants.LOGGING_ENABLED
LOG_TO_FILE = constants.LOG_TO_FILE

SAVE_LOGS_TO_FILE = LOG_TO_FILE
MAX_LOG_SIZE = 5 * 1024 * 1024  # 5MB
MAX_LOG_FILES = 6
LOG_FORMAT = "%(asctime)s - %(levelname)s - [%(threadName)s] - %(name)s - %(message)s%(exc_text)s"

ANSI_RESET = "\033[0m"
LEVEL_COLOR_MAP = {
    logging.DEBUG: "\033[36m",     # Cyan
    logging.INFO: "\033[32m",      # Green
    logging.WARNING: "\033[33m",   # Yellow
    logging.ERROR: "\033[31m",     # Red
    logging.CRITICAL: "\033[35m",  # Magenta
}
THREAD_COLOR = "\033[94m"  # Bright blue
DAEMON_THREAD_COLOR = "\033[95m"  # Bright magenta
LOGGER_COLOR_MAP = [
    ("GUI.", "\033[96m"),             # Bright cyan
    ("platforms.", "\033[92m"),       # Bright green
    ("app_plugins.", "\033[92m"),     # Bright green
]
DAEMON_LOGGER_PREFIXES = [
    "GUI.app.daemon",
    "daemon",
]

_dev_logging_override: Optional[bool] = None


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
            exc_lines = traceback.format_exception(*record.exc_info)
            record.exc_text = "\n" + "".join(exc_lines)
            # Clear exc_info to prevent parent formatter from also processing it
            record.exc_info = None
        else:
            record.exc_text = ""
        return super().format(record)


def _prune_old_logs(log_dir: Path, keep: int) -> None:
    """Remove oldest log files beyond the retention limit."""
    try:
        log_files = sorted(
            (path for path in log_dir.glob("app_*.log") if path.is_file()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        for old_file in log_files[keep:]:
            try:
                old_file.unlink()
            except Exception:
                logging.getLogger(__name__).debug("Failed to remove log file %s", old_file, exc_info=True)
    except Exception:
        logging.getLogger(__name__).debug("Error while pruning old log files", exc_info=True)


def _enable_windows_ansi_support() -> None:
    """Enable ANSI processing on Windows consoles if needed."""
    if os.name != "nt":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        # If enabling ANSI support fails, silently continue without color.
        pass


def _supports_color(stream) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    try:
        return hasattr(stream, "isatty") and stream.isatty()
    except Exception:
        return False


class ColorFormatter(CustomFormatter):
    def __init__(self, fmt: str):
        super().__init__(fmt)

    def format(self, record: logging.LogRecord) -> str:
        color = LEVEL_COLOR_MAP.get(record.levelno)
        if not color:
            return super().format(record)

        original_levelname = record.levelname
        original_threadname = record.threadName
        original_logger_name = record.name
        
        record.levelname = f"{color}{original_levelname}{ANSI_RESET}"
        
        # Always use normal thread color
        record.threadName = f"{THREAD_COLOR}{original_threadname}{ANSI_RESET}"
        
        # Check if this is a daemon logger (by logger name prefix)
        is_daemon_logger = any(original_logger_name.startswith(prefix) for prefix in DAEMON_LOGGER_PREFIXES)
        
        if is_daemon_logger:
            # Color daemon logger name in bright magenta
            record.name = f"{DAEMON_THREAD_COLOR}{original_logger_name}{ANSI_RESET}"
        else:
            # Use normal logger color mapping
            for prefix, color_code in LOGGER_COLOR_MAP:
                if original_logger_name.startswith(prefix):
                    record.name = f"{color_code}{original_logger_name}{ANSI_RESET}"
                    break
        try:
            formatted = super().format(record)
        finally:
            record.levelname = original_levelname
            record.threadName = original_threadname
            record.name = original_logger_name
        return formatted


def set_dev_logging_override(enabled: bool) -> None:
    """Force dev logging behavior (DEBUG level) when True. Call before setup_logging."""
    global _dev_logging_override
    _dev_logging_override = enabled


def _configure_handlers(root_logger: logging.Logger, level: int) -> None:
    # Remove any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    base_formatter = CustomFormatter(LOG_FORMAT)

    if SAVE_LOGS_TO_FILE:
        from ..utils.paths import logs_dir
        log_dir = logs_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"app_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        file_handler = RotatingFileHandler(
            log_file, maxBytes=MAX_LOG_SIZE, backupCount=MAX_LOG_FILES, encoding="utf-8"
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(base_formatter)
        root_logger.addHandler(file_handler)
        _prune_old_logs(log_dir, MAX_LOG_FILES)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    stream = console_handler.stream
    if _supports_color(stream):
        _enable_windows_ansi_support()
        console_handler.setFormatter(ColorFormatter(LOG_FORMAT))
    else:
        console_handler.setFormatter(base_formatter)
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
        # Auto-enable DEBUG logging for dev builds:
        # - dev mode flag enabled (set via CLI -dev or version detection in app.py)
        is_dev = (_dev_logging_override is True) or is_dev_mode()
        base_level = logging.DEBUG if is_dev else logging.INFO
        root_logger.setLevel(base_level)

        _configure_handlers(root_logger, base_level)

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


__all__ = ['setup_logging']
