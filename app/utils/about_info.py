"""
About dialog information helpers.

This module centralizes About-dialog content generation and dialog creation,
keeping `ui/main_window.py` focused on window behavior.
"""

from __future__ import annotations

import datetime
import platform
import sys
from typing import Optional


def _read_linux_pretty_name() -> Optional[str]:
    try:
        with open("/etc/os-release", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"')
                if k == "PRETTY_NAME":
                    return v or None
    except Exception:
        return None
    return None


def _format_build_time(raw: str) -> str:
    """Turn an ISO 8601 UTC timestamp into a friendly string.

    ``"2026-02-11T12:30:00Z"`` -> ``"Feb 11, 2026 at 12:30 PM UTC"``
    Falls back to *raw* if parsing fails.
    """
    try:
        dt = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y at %I:%M %p UTC").replace(" 0", " ")
    except Exception:
        return raw


def _build_distro_line(platform_name: str) -> str:
    """Build distro/time line for About dialog. Only shown when running from a frozen binary."""
    try:
        from .admin import is_dev_mode
        from ..build_info import BUILD_DISTRO, BUILD_TIME_UTC

        if not getattr(sys, "frozen", False):
            return ""
        if not is_dev_mode():
            return ""

        # On Windows, show build time only (avoid redundant Platform/Distro lines).
        if str(platform_name).lower() == "windows":
            if BUILD_TIME_UTC and BUILD_TIME_UTC != "unknown":
                return f"<p><b>Build time:</b> {_format_build_time(BUILD_TIME_UTC)}</p>"
            return ""

        if BUILD_DISTRO and BUILD_DISTRO != "unknown":
            if BUILD_TIME_UTC and BUILD_TIME_UTC != "unknown":
                return f"<p><b>Build distro:</b> {BUILD_DISTRO} <small>({_format_build_time(BUILD_TIME_UTC)})</small></p>"
            return f"<p><b>Build distro:</b> {BUILD_DISTRO}</p>"
    except Exception:
        pass
    return ""


def _python_version_line() -> str:
    """Return a Python version line, only visible in dev mode."""
    try:
        from .admin import is_dev_mode

        if not is_dev_mode():
            return ""

        version = platform.python_version()
        impl = platform.python_implementation()
        arch = platform.machine() or "unknown"
        return f"<p><b>Python:</b> {impl} {version} ({arch})</p>"
    except Exception:
        pass
    return ""

def create_about_dialog(
    parent,
    *,
    app_name: str,
    gui_api_version: str,
    platform_name: str,
    app_version: Optional[str] = None,
):
    """Create a configured non-modal About QMessageBox (not shown).

    Kept here to keep `main_window.py` focused on UI wiring.
    """
    from ..qt_bindings import QtCore, QtWidgets

    msg = QtWidgets.QMessageBox(parent)
    msg.setWindowTitle(f"About {app_name}")
    msg.setText(build_about_info(
        app_name=app_name,
        app_version=app_version,
        gui_api_version=gui_api_version,
        platform_name=platform_name,
    ))
    msg.setTextFormat(QtCore.Qt.TextFormat.RichText)
    msg.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Close)
    msg.setWindowModality(QtCore.Qt.WindowModality.NonModal)
    msg.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
    return msg


def build_about_info(
    *,
    app_name: str,
    gui_api_version: str,
    platform_name: str,
    app_version: Optional[str] = None,
) -> str:
    """Build rich-text (Qt) for the About dialog."""
    # Import here to avoid UI modules importing Qt binding shims too early.
    try:
        from ..qt_bindings import get_binding_name

        binding_name = get_binding_name()
    except Exception:
        binding_name = "pyside6"

    version_line = f"<p><b>Version:</b> {app_version}</p>" if app_version else ""
    binding_line = (
        f"<p><b>Qt Binding:</b> {binding_name}</p>"
        if binding_name != "pyside6"
        else ""
    )

    distro_line = ""
    if str(platform_name).lower() == "linux":
        pretty = _read_linux_pretty_name()
        if pretty:
            distro_line = f"<p><b>Distro:</b> {pretty}</p>"

    build_distro_line = _build_distro_line(str(platform_name))
    python_line = _python_version_line()

    return (
        f"<h2>{app_name}</h2>"
        f"{version_line}"
        f"<p><b>GUI API Version:</b> {gui_api_version}</p>"
        f"<p><b>Platform:</b> {str(platform_name).title()}</p>"
        f"{distro_line}"
        f"{build_distro_line}"
        f"{python_line}"
        f"{binding_line}"
    )


__all__ = ["build_about_info", "create_about_dialog"]

