"""
About dialog information helpers.

Toolkit-neutral field gathering plus HTML/text formatters for Qt and TUI.
"""

from __future__ import annotations

import datetime
import platform
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


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


@dataclass
class AboutFields:
    """Structured About content shared by Qt and TUI."""

    app_name: str
    gui_api_version: str
    platform_name: str
    app_version: Optional[str] = None
    distro: Optional[str] = None
    build_distro: Optional[str] = None
    build_time: Optional[str] = None
    python: Optional[str] = None
    git_commit: Optional[str] = None
    ui_backend_label: Optional[str] = None
    detail_rows: List[Tuple[str, str]] = field(default_factory=list)


def get_about_fields(
    *,
    app_name: str,
    gui_api_version: str,
    platform_name: str,
    app_version: Optional[str] = None,
    ui_backend_label: Optional[str] = None,
) -> AboutFields:
    """Gather About dialog fields without toolkit imports."""
    from .display_utils import _format_platform_name

    pretty_platform = _format_platform_name(platform_name)
    rows: List[Tuple[str, str]] = []

    if app_version:
        rows.append(("Version", app_version))
    rows.append(("GUI API Version", gui_api_version))
    rows.append(("Platform", pretty_platform))

    distro: Optional[str] = None
    if str(platform_name).lower() == "linux":
        distro = _read_linux_pretty_name()
        if distro:
            rows.append(("Distro", distro))

    build_distro: Optional[str] = None
    build_time: Optional[str] = None
    python_line: Optional[str] = None
    git_commit: Optional[str] = None

    try:
        from .admin import is_dev_mode
        dev_mode = bool(is_dev_mode())
    except Exception:
        dev_mode = False

    if dev_mode:
        try:
            from ..build_info import BUILD_DISTRO, BUILD_TIME_UTC, GIT_COMMIT

            if getattr(sys, "frozen", False):
                if BUILD_DISTRO and BUILD_DISTRO != "unknown":
                    build_distro = BUILD_DISTRO
                    rows.append(("Build Distro", BUILD_DISTRO))
                if BUILD_TIME_UTC and BUILD_TIME_UTC != "unknown":
                    build_time = _format_build_time(BUILD_TIME_UTC)
                    rows.append(("Build Time", build_time))

            if GIT_COMMIT and GIT_COMMIT != "unknown":
                is_dirty = GIT_COMMIT.endswith("-dirty")
                base_commit = GIT_COMMIT[:-6] if is_dirty else GIT_COMMIT
                if len(base_commit) == 40:
                    base_commit = base_commit[:8]
                git_commit = f"{base_commit}-dirty" if is_dirty else base_commit
                rows.append(("Git Commit", git_commit))

            python_line = (
                f"{platform.python_implementation()} "
                f"{platform.python_version()} "
                f"({platform.machine() or 'unknown'})"
            )
            rows.append(("Python", python_line))
        except Exception:
            pass

    if ui_backend_label:
        # Skip redundant default Qt binding label
        if ui_backend_label.lower() not in ("pyside6",):
            rows.append(("UI Backend", ui_backend_label))

    return AboutFields(
        app_name=app_name,
        gui_api_version=gui_api_version,
        platform_name=pretty_platform,
        app_version=app_version,
        distro=distro,
        build_distro=build_distro,
        build_time=build_time,
        python=python_line,
        git_commit=git_commit,
        ui_backend_label=ui_backend_label,
        detail_rows=rows,
    )


def format_about_html(fields: AboutFields) -> str:
    """Format About fields as Qt rich-text HTML."""
    lines = [f"<h2>{fields.app_name}</h2>"]
    for label, value in fields.detail_rows:
        lines.append(f"<p><b>{label}:</b> {value}</p>")
    return "".join(lines)


def format_about_text(fields: AboutFields) -> str:
    """Format About fields as plain text for TUI / clipboard."""
    lines = [fields.app_name, ""]
    for label, value in fields.detail_rows:
        lines.append(f"{label}: {value}")
    return "\n".join(lines).rstrip() + "\n"


def build_about_info(
    *,
    app_name: str,
    gui_api_version: str,
    platform_name: str,
    app_version: Optional[str] = None,
    ui_backend_label: Optional[str] = None,
) -> str:
    """Build rich-text HTML for the About dialog (no toolkit imports).

    Prefer ``get_about_fields`` + ``format_about_html`` / ``format_about_text``.
    Pass ``ui_backend_label`` from the UI layer when a binding name is needed.
    """
    fields = get_about_fields(
        app_name=app_name,
        gui_api_version=gui_api_version,
        platform_name=platform_name,
        app_version=app_version,
        ui_backend_label=ui_backend_label,
    )
    return format_about_html(fields)


__all__ = [
    "AboutFields",
    "get_about_fields",
    "format_about_html",
    "format_about_text",
    "build_about_info",
    "_read_linux_pretty_name",
    "_format_build_time",
]
