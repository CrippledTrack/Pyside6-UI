from __future__ import annotations

# Version information
VERSION = "3.0.0"
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

