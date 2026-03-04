"""
Application entry point and bootstrap module.

This module handles application initialization, platform-specific setup,
daemon management, and the main application lifecycle.
"""

from __future__ import annotations

import platform
import sys
from typing import List

from .constants import VERSION as GUI_API_VERSION
from .services.logging_service import setup_logging, set_dev_logging_override
from .services.app_lifecycle_service import AppLifecycleService
from .services.container import ServiceContainer
from .services.daemon_lifecycle_service import DaemonLifecycleService
from .services.qt_deps_service import QtDepsService
from .services.settings_service import SettingsService
from .services.theme_init_service import ThemeInitService
from .utils.console import apply_console_setting
from .utils.admin import set_dev_mode
from .utils.imports import get_platforms_constants
from ..plugin_system.import_aliases import install_import_aliases

# Import platform constants using the utility function
constants = get_platforms_constants()
VERSION = constants.VERSION
VERSION_NAME = constants.VERSION_NAME

def run(argv: List[str]) -> int:
    """Application bootstrap. Mirrors previous behavior from main.py without changes."""
    # Check for daemon mode before GUI initialization
    if '--daemon' in argv and platform.system().lower() == 'linux':
        from .daemon.server import run_daemon
        return run_daemon(argv)
    
    # Check for dev mode flag or dev version - bypasses admin requirements for tab loading and enables dev logging
    dev_flag = ('-dev' in argv or '--dev' in argv)
    dev_version = ('-dev' in str(VERSION)) or ('-dev' in str(GUI_API_VERSION))
    is_dev = dev_flag or dev_version
    if is_dev:
        set_dev_mode(True)
        set_dev_logging_override(True)

    app_lifecycle = AppLifecycleService()
    if not app_lifecycle.acquire_single_instance_lock():
        print("Another instance is already running.", file=sys.stderr)
        return 1
    
    # Apply console visibility setting based on SHOW_CONSOLE constant
    apply_console_setting()
    
    logger = setup_logging()
    logger.info(f"Starting {VERSION_NAME} v{VERSION} on {platform.system().lower()}")
    logger.info(f"GUI API Version: v{GUI_API_VERSION}")

    # Install legacy import aliases used by some plugin modules (best-effort).
    installed_aliases = install_import_aliases()
    if installed_aliases:
        logger.debug(f"Installed plugin import aliases: {installed_aliases}")

    # Log dev mode status now that logging is configured
    if is_dev:
        logger.warning("DEV MODE ENABLED - admin requirements bypassed, Dev menu available")

    # On Linux, ensure Qt system dependencies are present BEFORE anything
    # imports qt_bindings.  Many services (NotificationService, etc.)
    # import Qt at module level, so this must happen before the service
    # container is initialised.
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
    container = ServiceContainer()
    container.initialize_services()
    logger.info("Service container initialized")
    
    # Get settings service from container
    settings_service = container.get(SettingsService)
    logger.info("Settings service loaded")
    
    # Save current GUI version to settings for future reference
    settings_service.save_gui_version(GUI_API_VERSION)

    app = QApplication(argv)

    app_lifecycle.configure_qt_application(app, VERSION_NAME, GUI_API_VERSION)

    theme_init_service = ThemeInitService()
    theme_manager = theme_init_service.initialize(container, settings_service)

    daemon_lifecycle = DaemonLifecycleService()
    daemon_client = daemon_lifecycle.start_if_required(container)

    # Create MainWindow with service container
    window = MainWindow(settings_service=settings_service, container=container)
    window.show()

    exit_code = app.exec()
    
    # Cleanup: Stop daemon on exit (if it was started)
    daemon_lifecycle.shutdown(daemon_client)
    
    # Cleanup: Release lock file
    app_lifecycle.release_single_instance_lock()
    
    logger.info(f"Application closed with code {exit_code}")
    return exit_code


__all__ = ['run']
