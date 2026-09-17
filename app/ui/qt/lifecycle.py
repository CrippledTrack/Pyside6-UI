"""Qt application lifecycle helpers (style, platform IDs)."""

from __future__ import annotations

import logging
import platform
import sys
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)


def resolve_window_icon_path() -> Optional[Path]:
    """Resolve the host-supplied application icon, if any.

    Hosts opt in by setting ``WINDOW_ICON_PATH`` in their constants; the
    framework ships no icon of its own. Relative paths resolve against the
    application base directory rather than the working directory, which is
    ``/`` for a bundle launched from Finder.
    """
    from ...utils.imports import get_platforms_constants
    from ...utils.paths import get_base_path

    raw = str(getattr(get_platforms_constants(), "WINDOW_ICON_PATH", "") or "").strip()
    if not raw:
        return None

    path = Path(raw)
    if not path.is_absolute():
        path = get_base_path() / path
    if not path.is_file():
        logger.warning(f"WINDOW_ICON_PATH does not point at a file: {path}")
        return None
    return path


def configure_qt_application(app, version_name: str, gui_api_version: str) -> None:
    """Configure Qt application identity, style and Windows AppUserModelID."""
    sysname = platform.system().lower()

    # Without a name, the macOS menu-bar application menu and its Quit/About
    # items are labelled "Python". Also used for Wayland/X11 app identity.
    app.setApplicationName(version_name)
    app.setApplicationDisplayName(version_name)

    icon_path = resolve_window_icon_path()
    if icon_path is not None:
        try:
            from .bindings import QIcon

            app.setWindowIcon(QIcon(str(icon_path)))
        except Exception as e:
            logger.warning(f"Failed to set window icon from {icon_path}: {e}")

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


__all__ = ["configure_qt_application"]
