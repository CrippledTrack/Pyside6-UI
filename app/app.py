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

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from .constants import VERSION as GUI_API_VERSION
from .services.logging_service import setup_logging
from .services.container import ServiceContainer
from .services.settings_service import SettingsService
from .ui.main_window import MainWindow
from .utils.console import apply_console_setting
from .utils.imports import get_platforms_constants

# Import platform constants using the utility function
constants = get_platforms_constants()
VERSION = constants.VERSION
VERSION_NAME = constants.VERSION_NAME

# Linux-specific checks
if platform.system().lower() == "linux":
    from .daemon import set_daemon_client
    from .utils.elevation_linux import start_daemon, stop_daemon
    from .utils.qt_dependencies_linux import ensure_qt_xcb_dependencies_installed


def run(argv: List[str]) -> int:
    """Application bootstrap. Mirrors previous behavior from main.py without changes."""
    # Check for daemon mode before GUI initialization
    if '--daemon' in argv and platform.system().lower() == 'linux':
        from .daemon.server import run_daemon
        return run_daemon(argv)
    
    # Check for dev mode flag - bypasses admin requirements for tab loading
    if '-dev' in argv or '--dev' in argv:
        from .utils.admin import set_dev_mode
        set_dev_mode(True)

    # Prevent multiple instances on Linux (check BEFORE any initialization)
    lock_file = None
    lock_file_path = None
    if platform.system().lower() == "linux":
        import fcntl
        lock_file_path = '/tmp/cyberpatriot-ui.lock'
        try:
            lock_file = open(lock_file_path, 'w')
            fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            lock_file.write(str(os.getpid()))
            lock_file.flush()
        except (IOError, OSError):
            # Another instance is running
            print("Another instance is already running.", file=sys.stderr)
            return 1
    
    # Apply console visibility setting based on SHOW_CONSOLE constant
    apply_console_setting()
    
    logger = setup_logging()
    logger.info(f"Starting {VERSION_NAME} v{VERSION} on {platform.system().lower()}")
    logger.info(f"GUI API Version: v{GUI_API_VERSION}")

    # Log dev mode status now that logging is configured
    if '-dev' in argv or '--dev' in argv:
        logger.warning("DEV MODE ENABLED - admin requirements bypassed, Dev menu available")

    # Initialize service container
    container = ServiceContainer()
    container.initialize_services()
    logger.info("Service container initialized")
    
    # Get settings service from container
    settings_service = container.get(SettingsService)
    logger.info("Settings service loaded")
    
    # Save current GUI version to settings for future reference
    settings_service.save_gui_version(GUI_API_VERSION)

    # On Linux, before creating QApplication, ensure Qt xcb system dependencies are present
    if platform.system().lower() == "linux":
        try:
            if not ensure_qt_xcb_dependencies_installed():
                logger.error(
                    "Required Qt xcb dependencies are missing and could not be installed automatically."
                )
                print(
                    "Missing Qt dependencies. Please install: "
                    "libxcb-cursor0 libxcb-xinerama0 libxcb-icccm4 libxcb-image0 "
                    "libxcb-keysyms1 libxcb-render-util0 libxkbcommon-x11-0 qtwayland5",
                    file=sys.stderr,
                )
                return 1
        except Exception as e:
            logger.error(f"Error while ensuring Qt dependencies: {e}")

    app = QApplication(argv)

    # Set the style to Fusion on Windows by default
    if platform.system().lower() == "windows":
        app.setStyle("Fusion")

    app.setFont(QFont("Segoe UI", 10))

    # Now that QApplication exists, register ThemeManager in the container
    # (ThemeManager requires QApplication for palette detection)
    from ..themes.theme_manager import ThemeManager
    theme_manager = ThemeManager(settings_service=settings_service)
    container.register_singleton(ThemeManager, theme_manager)
    logger.info("ThemeManager registered in container")

    # On Linux, start privileged daemon (optional - app can run without it)
    daemon_client = None
    if platform.system().lower() == "linux":
        from .services.daemon_service import DaemonService
        daemon_service = container.get(DaemonService)
        logger.info("Starting privileged daemon...")
        daemon_client = start_daemon()
        if not daemon_client or not daemon_client.is_connected():
            logger.warning("Failed to start privileged daemon. Some features requiring admin privileges will be disabled.")
            logger.warning("The application will continue in limited mode. Tabs requiring admin privileges will be disabled.")
            daemon_client = None
        else:
            # Store daemon client globally for utils to use
            set_daemon_client(daemon_client)
            logger.info("Privileged daemon started successfully")

    # Apply theme using saved preference
    saved_theme = settings_service.get_theme_preference()
    theme_manager.apply_auto_theme(saved_theme=saved_theme)

    # Create MainWindow with service container
    window = MainWindow(settings_service=settings_service, container=container)
    window.show()

    exit_code = app.exec()
    
    # Cleanup: Stop daemon on exit (if it was started)
    if platform.system().lower() == "linux" and daemon_client:
        logger.info("Stopping privileged daemon...")
        try:
            if daemon_client.is_connected():
                daemon_client.request('shutdown', {})
                daemon_client.disconnect()
        except Exception:
            # Ignore errors during cleanup - daemon may already be stopped
            pass
        stop_daemon()
    
    # Cleanup: Release lock file
    if lock_file:
        try:
            import fcntl
            fcntl.lockf(lock_file, fcntl.LOCK_UN)
            lock_file.close()
            if lock_file_path and os.path.exists(lock_file_path):
                os.unlink(lock_file_path)
        except Exception:
            # Ignore errors during cleanup - file may already be released
            pass
    
    logger.info(f"Application closed with code {exit_code}")
    return exit_code


__all__ = ['run']
