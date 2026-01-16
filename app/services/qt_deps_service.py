"""
Qt dependency validation service for Linux.
"""
from __future__ import annotations

import logging
import platform
from typing import Optional, Tuple


logger = logging.getLogger(__name__)

_MISSING_DEPS_MESSAGE = (
    "Missing Qt dependencies. Please install: "
    "libxcb-cursor0 libxcb-xinerama0 libxcb-icccm4 libxcb-image0 "
    "libxcb-keysyms1 libxcb-render-util0 libxkbcommon-x11-0 qtwayland5"
)


class QtDepsService:
    """Ensure required Qt system dependencies are present."""

    def ensure_dependencies(self) -> Tuple[bool, Optional[str]]:
        if platform.system().lower() != "linux":
            return True, None

        try:
            from ..utils.qt_dependencies_linux import ensure_qt_xcb_dependencies_installed

            if not ensure_qt_xcb_dependencies_installed():
                logger.error("Required Qt xcb dependencies are missing.")
                return False, _MISSING_DEPS_MESSAGE
        except Exception as e:
            logger.error("Error while ensuring Qt dependencies: %s", e)

        return True, None


__all__ = ["QtDepsService"]
