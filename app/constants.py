"""
Application constants and configuration.

This module defines version information, platform support, and default
configuration values for the GUI application.
"""

from __future__ import annotations

import platform

# =============================================================================
# Version Information (can be overridden by app_plugins/constants.py)
# =============================================================================
VERSION = "4.0.0-dev-1"
VERSION_NAME = "Basic UI Application"

VERSION_INFO = {
    "version": VERSION,
    "name": VERSION_NAME,
    "description": "Basic UI Application",
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
NEW_UI_ENABLED_BY_DEFAULT = True

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
    'NEW_UI_ENABLED_BY_DEFAULT',
    # GUI internal
    'CURRENT_PLATFORM',
]
