"""
Application constants and configuration.

This module defines version information, platform support, and default
configuration values for the GUI application.
"""

from __future__ import annotations

# Version information
VERSION = "3.3.5-dev-architecture-1"
VERSION_NAME = "Basic UI Application"
SUPPORTED_PLATFORMS = ["Windows", "Linux"]

VERSION_INFO = {
    "version": VERSION,
    "name": VERSION_NAME,
    "supported_platforms": SUPPORTED_PLATFORMS,
    "description": "Basic UI Application",
}

# Admin elevation configuration (mirrors previous default behavior)
REQUIRE_ADMIN_BY_DEFAULT = False

# Logging configuration
# If False, disable all logging configuration and handlers
LOGGING_ENABLED = True
# If True, save logs to files in the logs directory (does not work with LOGGING_ENABLED = False)
LOG_TO_FILE = True

# Console configuration
SHOW_CONSOLE = False

# UI configuration
# Users can still toggle this via Settings -> Enable/Disable New UI
NEW_UI_ENABLED_BY_DEFAULT = True

__all__ = [
    'VERSION',
    'VERSION_NAME',
    'SUPPORTED_PLATFORMS',
    'VERSION_INFO',
    'REQUIRE_ADMIN_BY_DEFAULT',
    'LOGGING_ENABLED',
    'LOG_TO_FILE',
    'SHOW_CONSOLE',
    'NEW_UI_ENABLED_BY_DEFAULT',
]

