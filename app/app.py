"""
Application entry point and bootstrap module.

This module handles application initialization, platform-specific setup,
daemon management, and the main application lifecycle.
"""

from __future__ import annotations

import os
import platform
import sys
from typing import List

from .constants import GUI_API_VERSION
from .services.logging_service import setup_logging, set_dev_logging_override
from .utils.admin import set_dev_mode


def run(argv: List[str]) -> int:
    """Application bootstrap."""
    if ('--daemon' in argv or '--pipe' in argv) and platform.system().lower() == 'linux':
        from .daemon.server import run_daemon
        return run_daemon(argv)

    from .utils.imports import get_platforms_constants
    constants = get_platforms_constants()
    VERSION = constants.VERSION
    VERSION_NAME = constants.VERSION_NAME

    qt_binding = getattr(constants, "DEFAULT_QT_BINDING", "") or ""
    for arg in argv:
        if arg.startswith("--qt-binding="):
            qt_binding = arg.split("=", 1)[1].strip()
            break

    if not qt_binding:
        # Host constants often leave this blank; GUI default avoids dual binding probes.
        from .constants import DEFAULT_QT_BINDING as _gui_qt_binding
        qt_binding = _gui_qt_binding or "pyside6"

    if qt_binding:
        os.environ.setdefault("QT_BINDING", qt_binding)

    dev_flag = ('-dev' in argv or '--dev' in argv)
    dev_version = '-dev' in str(VERSION)
    is_dev = dev_flag or dev_version
    if is_dev:
        set_dev_mode(True)
        set_dev_logging_override(True)

    from .utils.console import apply_console_setting
    apply_console_setting()

    logger = setup_logging()
    logger.info(f"Starting {VERSION_NAME} v{VERSION} on {platform.system().lower()}")
    logger.info(f"GUI API Version: v{GUI_API_VERSION}")

    if is_dev:
        logger.warning("DEV MODE ENABLED - admin requirements bypassed, Dev menu available")

    from .services.container import ServiceContainer
    container = ServiceContainer()
    container.initialize_services()
    logger.info("Service container initialized")

    from .ui.registry import get_ui_backend, resolve_ui_backend_name
    from .ui.active_backend import set_active_ui_backend_id

    backend_name = resolve_ui_backend_name(argv)
    set_active_ui_backend_id(backend_name)
    backend = get_ui_backend(backend_name)(container, argv, VERSION_NAME)
    return backend.run()


__all__ = ['run']
