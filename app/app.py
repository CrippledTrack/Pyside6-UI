from __future__ import annotations

import sys
from typing import List
import platform

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont

from .services.logging_service import setup_logging
from .services.settings_service import load_settings as load_settings_service
from ..themes.theme_manager import ThemeManager
from .ui.main_window import MainWindow
from .utils.console import apply_console_setting
# Import GUI version first before it gets overridden by platforms
from .constants import VERSION as GUI_API_VERSION
# Try to import from platforms first, fallback to ui app constants
try:
    from platforms.constants import VERSION, VERSION_NAME
except ImportError:
    try:
        # If running from ui directory, try parent directory
        import sys
        import os
        parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        from platforms.constants import VERSION, VERSION_NAME
    except ImportError:
        from .constants import VERSION, VERSION_NAME

# Linux-specific checks
if platform.system().lower() == "linux":
    from .utils.qt_dependencies_linux import ensure_qt_xcb_dependencies_installed
    from .utils.elevation_linux import start_daemon, stop_daemon
    from .daemon import set_daemon_client


def run(argv: List[str]) -> int:
    """Application bootstrap. Mirrors previous behavior from main.py without changes."""
    # Check for daemon mode before GUI initialization
    if '--daemon' in argv and platform.system().lower() == 'linux':
        from .daemon.server import run_daemon
        return run_daemon()
    
    # Apply console visibility setting based on SHOW_CONSOLE constant
    apply_console_setting()
    
    logger = setup_logging()
    logger.info(f"Starting {VERSION_NAME} v{VERSION} on {platform.system().lower()}")
    logger.info(f"GUI API Version: v{GUI_API_VERSION}")

    # Load settings service
    settings_service = load_settings_service()
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

    # Global style and font retained
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))

    # On Linux, start privileged daemon
    daemon_client = None
    if platform.system().lower() == "linux":
        logger.info("Starting privileged daemon...")
        daemon_client = start_daemon()
        if not daemon_client or not daemon_client.is_connected():
            logger.error("Failed to start privileged daemon. Administrator privileges required.")
            from PySide6.QtWidgets import QMessageBox
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle("Administrator Privileges Required")
            msg.setText("This application requires administrator privileges to function properly.")
            msg.setInformativeText("The application will now exit.")
            msg.exec()
            return 1
        
        # Store daemon client globally for utils to use
        set_daemon_client(daemon_client)
        logger.info("Privileged daemon started successfully")

    # Apply theme using ThemeManager with saved preference
    theme_manager = ThemeManager(settings_service=settings_service)
    saved_theme = settings_service.get_theme_preference()
    theme_manager.apply_auto_theme(saved_theme=saved_theme)

    window = MainWindow(theme_manager, settings_service=settings_service)
    window.show()

    exit_code = app.exec()
    
    # Cleanup: Stop daemon on exit
    if platform.system().lower() == "linux" and daemon_client:
        logger.info("Stopping privileged daemon...")
        try:
            daemon_client.request('shutdown', {})
            daemon_client.disconnect()
        except:
            pass
        stop_daemon()
    
    logger.info(f"Application closed with code {exit_code}")
    return exit_code


