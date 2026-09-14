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
GUI_API_VERSION = "6.0.0-rc-8"

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

# UI configuration — cross-backend (toolkit-neutral)
DEFAULT_UI_BACKEND = "qt"

# UI configuration — Qt backend only (ignored when DEFAULT_UI_BACKEND is not "qt")
DEFAULT_QT_BINDING = "pyside6"  # Prefer a single binding; avoids probing PySide6 then PyQt6
QT_NEW_UI_ENABLED_BY_DEFAULT = True  # theme manager "new UI" stylesheet toggle default

# Hide the Admin menu/button by default (can be overridden by app_plugins/constants.py)
HIDE_ADMIN_MENU_BY_DEFAULT = True

# Single plugin configuration (can be overridden by app_plugins/constants.py or launch variables)
SINGLE_PLUGIN_MODE = False
SINGLE_PLUGIN_NAME = ""

# Default theme override (can be overridden by app_plugins/constants.py, blank defaults to system dark/light check)
DEFAULT_THEME = ""

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
    'DEFAULT_UI_BACKEND',
    'DEFAULT_QT_BINDING',
    'QT_NEW_UI_ENABLED_BY_DEFAULT',
    'HIDE_ADMIN_MENU_BY_DEFAULT',
    'SINGLE_PLUGIN_MODE',
    'SINGLE_PLUGIN_NAME',
    'DEFAULT_THEME',
    # GUI internal
    'GUI_API_VERSION',
    'CURRENT_PLATFORM',
]
