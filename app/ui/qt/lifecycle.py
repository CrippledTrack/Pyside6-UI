"""Qt application lifecycle helpers (style, fonts, platform IDs)."""

from __future__ import annotations

import logging
import platform
import sys


logger = logging.getLogger(__name__)


def configure_qt_application(app, version_name: str, gui_api_version: str) -> None:
    """Configure Qt application style, fonts, and Windows AppUserModelID."""
    from .bindings import QFont

    sysname = platform.system().lower()

    # Use the built-in Fusion style on Windows and macOS for consistent theming.
    if sysname in ("windows", "darwin"):
        app.setStyle("Fusion")

    if sysname == "windows":
        try:
            import ctypes

            myappid = f"{version_name}.Scripts.GUI.{gui_api_version}"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception as e:
            print(f"Failed to set AppUserModelID: {e}", file=sys.stderr)

        # Only force Segoe UI on Windows; other platforms keep their
        # native default UI font for better integration.
        app.setFont(QFont("Segoe UI", 10))


__all__ = ["configure_qt_application"]
