"""
Build metadata injected at packaging/build time.

When building with PyInstaller, a build step can generate
`GUI/app/_build_info_generated.py` to embed information about the build
environment (e.g., build distro).

At runtime, the UI can display these values (e.g., in About dialog).
"""

from __future__ import annotations

BUILD_DISTRO: str = "unknown"
BUILD_TIME_UTC: str = "unknown"

try:
    # Generated at build time (preferred).
    from ._build_info_generated import BUILD_DISTRO as BUILD_DISTRO  # type: ignore
    from ._build_info_generated import BUILD_TIME_UTC as BUILD_TIME_UTC  # type: ignore
except Exception:
    # Source runs / builds without generation step.
    pass

__all__ = ["BUILD_DISTRO", "BUILD_TIME_UTC"]

