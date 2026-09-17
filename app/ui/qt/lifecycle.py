"""Qt application lifecycle helpers (style, platform IDs)."""

from __future__ import annotations

import logging
import os
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


def resolve_style_name(sysname: str, requested: Optional[str] = None) -> Optional[str]:
    """Return the Qt style to force, or ``None`` to keep the platform default.

    Windows gets Fusion, since the native Windows style ignores much of what the
    builtin themes ask for. macOS keeps its own style: the platform default there
    already draws native controls. Note that the light/dark themes ship ~20 KB of
    QSS, which overrides most of that painting, so the fully native look also
    needs the ``Default`` theme.

    ``GUI_QT_STYLE`` overrides the choice on any platform, which is how you
    compare styles without a rebuild.
    """
    override = os.environ.get("GUI_QT_STYLE", "") if requested is None else requested
    override = (override or "").strip()
    if override:
        return override
    return "Fusion" if sysname == "windows" else None


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

    style_name = resolve_style_name(sysname)
    if style_name and not app.setStyle(style_name):
        logger.warning(f"Qt style is unavailable, keeping the platform default: {style_name}")

    if sysname == "windows":
        try:
            import ctypes

            myappid = f"{version_name}.Scripts.GUI.{gui_api_version}"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception as e:
            print(f"Failed to set AppUserModelID: {e}", file=sys.stderr)


__all__ = ["configure_qt_application", "resolve_style_name"]
