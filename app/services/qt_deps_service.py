"""
Qt dependency validation service for Linux.
"""
from __future__ import annotations

import logging
import platform
from typing import Optional, Tuple

from ..utils.qt_dependencies_linux import APT_PACKAGES


logger = logging.getLogger(__name__)

_MISSING_DEPS_MESSAGE = (
    "Missing Qt dependencies. Please install with: "
    "sudo apt-get update && sudo apt-get install -y --no-install-recommends "
    + " ".join(APT_PACKAGES)
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
            logger.error(f"Error while ensuring Qt dependencies: {e}")

        return True, None


__all__ = ["QtDepsService"]
