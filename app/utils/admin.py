"""Utilities for determining admin requirements for plugins.

This module provides functions to check if admin privileges are required
for plugin operations on different platforms.

Note: Dev mode state is now managed by DevModeService. The functions in
this module delegate to the service when available, or fall back to a
module-level flag for early bootstrap (before the container is ready).
Use set_dev_mode_service to wire the service once the container is ready.
"""

from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..services.dev_mode_service import DevModeService

# ---------------------------------------------------------------------------
# Backward-compatibility shim
# ---------------------------------------------------------------------------
# During early bootstrap (before the ServiceContainer is initialized) the
# caller (app.py) sets dev mode via set_dev_mode().  Once the container is
# ready, set_dev_mode_service() wires the DevModeService and all
# subsequent calls delegate there.

_dev_mode_service: Optional["DevModeService"] = None

# Fallback flag used *only* during early bootstrap, before the service exists.
_early_dev_mode: bool = False


def _get_service() -> Optional["DevModeService"]:
    """Return the DevModeService if it has been wired, else None."""
    return _dev_mode_service


def set_dev_mode_service(service: "DevModeService") -> None:
    """Explicitly set the DevModeService instance (called by container)."""
    global _dev_mode_service, _early_dev_mode
    _dev_mode_service = service
    # Transfer early flag
    if _early_dev_mode and not service.is_dev_mode():
        service.set_dev_mode(True)


def set_dev_mode(enabled: bool) -> None:
    """Set the dev mode flag.
    
    When dev mode is enabled, admin requirements for tab loading are bypassed.
    This allows testing the UI without elevated privileges.
    
    Args:
        enabled: True to enable dev mode, False to disable
    """
    global _early_dev_mode
    svc = _get_service()
    if svc is not None:
        svc.set_dev_mode(enabled)
    else:
        # Early bootstrap – store until the service is wired
        _early_dev_mode = enabled


def is_dev_mode() -> bool:
    """Check if dev mode is enabled.
    
    Returns:
        True if dev mode is enabled, False otherwise
    """
    svc = _get_service()
    if svc is not None:
        return svc.is_dev_mode()
    return _early_dev_mode


def set_show_all_platforms(enabled: bool) -> None:
    """Set the show all platforms flag (only effective in dev mode).
    
    When enabled, tabs from all platforms (Windows and Linux) are shown
    regardless of the current platform. This is useful for UI testing.
    
    Args:
        enabled: True to show all platform tabs, False to filter by current platform
    """
    svc = _get_service()
    if svc is not None:
        svc.set_show_all_platforms(enabled)
    else:
        logger.debug("set_show_all_platforms called before DevModeService is available")


def is_show_all_platforms() -> bool:
    """Check if show all platforms is enabled.
    
    Note: This only returns True if both dev mode AND show_all_platforms are enabled.
    
    Returns:
        True if showing all platform tabs, False otherwise
    """
    svc = _get_service()
    if svc is not None:
        return svc.is_show_all_platforms()
    return False


__all__ = [
    'set_dev_mode_service',
    'set_dev_mode',
    'is_dev_mode',
    'set_show_all_platforms',
    'is_show_all_platforms',
]
