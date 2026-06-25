"""
Application constants and configuration.

This module defines version information, platform support, and default
configuration values for the GUI application.
"""

from __future__ import annotations

import platform

# =============================================================================
# GUI Internal Variables (app_plugins will NOT override these)
# =============================================================================
GUI_API_VERSION = "5.3.0-dev-3"

# =============================================================================
# Version Information (can be overridden by app_plugins/constants.py)
# =============================================================================
VERSION = GUI_API_VERSION  # Intended to be used externally, if not defined externally, then it will default to the GUI API Version
VERSION_NAME = "Basic UI Application"

VERSION_INFO = {
    "version": VERSION,
    "name": VERSION_NAME,
    "description": VERSION_NAME,
}

# =============================================================================
# Configuration Defaults (can be overridden by app_plugins/constants.py)
# =============================================================================

# Admin elevation configuration
REQUIRE_ADMIN_BY_DEFAULT = False

# Logging configuration
LOGGING_ENABLED = True
LOG_TO_FILE = True

# Console configuration
SHOW_CONSOLE = False

# UI configuration
DEFAULT_QT_BINDING = ""  # If set, overrides the default binding (e.g., "pyside6" or "pyqt6")
NEW_UI_ENABLED_BY_DEFAULT = True
# Hide the Admin menu/button by default (can be overridden by app_plugins/constants.py)
HIDE_ADMIN_MENU_BY_DEFAULT = True

# Single plugin configuration (can be overridden by app_plugins/constants.py or launch variables)
SINGLE_PLUGIN_MODE = False
SINGLE_PLUGIN_NAME = ""

# Default theme override (can be overridden by app_plugins/constants.py, blank defaults to system dark/light check)
DEFAULT_THEME = ""

# Use pipe daemon instead of socket daemon on Linux (default is False for compatibility).
# Note: This sets the daemon type used at launch when REQUIRE_ADMIN_BY_DEFAULT is True.
# Otherwise, users can choose to activate either the legacy daemon or the pipe daemon if they want elevation after launch.
USE_PIPE_DAEMON = False

# =============================================================================
# GUI Internal (app_plugins will NOT override these)
# =============================================================================

# Platform detection - centralized for GUI components
CURRENT_PLATFORM = platform.system().lower()

__all__ = [
    # Version info
    'VERSION',
    'VERSION_NAME',
    'VERSION_INFO',
    # Configuration
    'REQUIRE_ADMIN_BY_DEFAULT',
    'LOGGING_ENABLED',
    'LOG_TO_FILE',
    'SHOW_CONSOLE',
    'DEFAULT_QT_BINDING',
    'NEW_UI_ENABLED_BY_DEFAULT',
    'HIDE_ADMIN_MENU_BY_DEFAULT',
    'SINGLE_PLUGIN_MODE',
    'SINGLE_PLUGIN_NAME',
    'DEFAULT_THEME',
    'USE_PIPE_DAEMON',
    # GUI internal
    'GUI_API_VERSION',
    'CURRENT_PLATFORM',
]
