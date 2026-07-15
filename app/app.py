"""
Application entry point and bootstrap module.

This module handles application initialization, platform-specific setup,
daemon management, and the main application lifecycle.
"""

from __future__ import annotations

import platform
import sys
from typing import List

from .constants import GUI_API_VERSION
from .services.logging_service import setup_logging, set_dev_logging_override
from .utils.admin import set_dev_mode

def run(argv: List[str]) -> int:
    """Application bootstrap. Mirrors previous behavior from main.py without changes."""
    # Check for daemon or pipe mode before GUI initialization
    if ('--daemon' in argv or '--pipe' in argv) and platform.system().lower() == 'linux':
        from .daemon.server import run_daemon
        return run_daemon(argv)
    
    # PERF: Import get_platforms_constants inline instead of at module level.
    # This defers a ~130ms package resolution penalty until the run() method actually executes.
    from .utils.imports import get_platforms_constants
    constants = get_platforms_constants()
    VERSION = constants.VERSION
    VERSION_NAME = constants.VERSION_NAME
    
    # Configure Qt binding from constants or command line arguments
    qt_binding = getattr(constants, "DEFAULT_QT_BINDING", "")
    for arg in argv:
        if arg.startswith("--qt-binding="):
            qt_binding = arg.split("=", 1)[1].strip()
            break
            
    if qt_binding:
        import os
        os.environ.setdefault("QT_BINDING", qt_binding)
    
    # Check for dev mode flag or dev version - bypasses admin requirements for tab loading and enables dev logging
    dev_flag = ('-dev' in argv or '--dev' in argv)
    dev_version = '-dev' in str(VERSION)
    is_dev = dev_flag or dev_version
    if is_dev:
        set_dev_mode(True)
        set_dev_logging_override(True)

    from .services.app_lifecycle_service import AppLifecycleService
    app_lifecycle = AppLifecycleService()
    
    # Apply console visibility setting based on SHOW_CONSOLE constant
    from .utils.console import apply_console_setting
    apply_console_setting()
    
    logger = setup_logging()
    logger.info(f"Starting {VERSION_NAME} v{VERSION} on {platform.system().lower()}")
    logger.info(f"GUI API Version: v{GUI_API_VERSION}")

    # Log dev mode status now that logging is configured
    if is_dev:
        logger.warning("DEV MODE ENABLED - admin requirements bypassed, Dev menu available")

    # On Linux, ensure Qt system dependencies are present BEFORE anything
    # imports qt_bindings.  Many services (NotificationService, etc.)
    # import Qt at module level, so this must happen before the service
    # container is initialised.
    from .services.qt_deps_service import QtDepsService
    qt_deps_service = QtDepsService()
    deps_ok, deps_message = qt_deps_service.ensure_dependencies()
    if not deps_ok:
        logger.error(
            "Required Qt xcb dependencies are missing and could not be installed automatically."
        )
        if deps_message:
            print(deps_message, file=sys.stderr)
        return 1

    # Import Qt bindings AFTER the dependency check so missing native
    # libraries have a chance to be installed first.
    from .qt_bindings import QApplication
    from .ui.main_window import MainWindow

    # Initialize service container (safe now -- Qt libs are available)
    from .services.container import ServiceContainer, set_container
    container = ServiceContainer()
    container.initialize_services()
    set_container(container)
    logger.info("Service container initialized")
    
    # Get settings service from container
    from .services.interfaces import ISettingsService
    settings_service = container.get(ISettingsService)
    logger.info("Settings service loaded")
    
    # Save current GUI version to settings for future reference
    settings_service.save_gui_version(GUI_API_VERSION)

    app = QApplication(argv)

    # Register QObject-based services only after QApplication exists
    container.initialize_qt_services()

    # Initialize the QtEventDispatcher on the main thread to ensure proper thread affinity
    from ..plugin_system.registry import QtEventDispatcher
    QtEventDispatcher.get_instance()

    app_lifecycle.configure_qt_application(app, VERSION_NAME, GUI_API_VERSION)

    from .services.theme_init_service import ThemeInitService
    theme_init_service = ThemeInitService()
    theme_manager = theme_init_service.initialize(container, settings_service)

    from .services.daemon_lifecycle_service import DaemonLifecycleService
    daemon_lifecycle = DaemonLifecycleService()
    daemon_client = daemon_lifecycle.start_if_required(container)

    # Create MainWindow with service container
    window = MainWindow(settings_service=settings_service, container=container)
    window.show()

    exit_code = app.exec()
    
    # Cleanup: Stop daemon on exit (if it was started)
    daemon_lifecycle.shutdown(daemon_client)
    

    
    logger.info(f"Application closed with code {exit_code}")
    return exit_code


__all__ = ['run']
