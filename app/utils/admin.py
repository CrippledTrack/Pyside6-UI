"""Utilities for determining admin requirements for plugins.

This module provides functions to check if admin privileges are required
for plugin operations on different platforms.

Note: Dev mode state is now managed by DevModeService. The functions in
this module delegate to the service when available, or fall back to a
module-level flag for early bootstrap (before the container is ready).
"""

from __future__ import annotations

import logging
import platform
from typing import Optional, TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..services.settings_service import SettingsService
    from ..services.dev_mode_service import DevModeService

# ---------------------------------------------------------------------------
# Backward-compatibility shim
# ---------------------------------------------------------------------------
# During early bootstrap (before the ServiceContainer is initialized) the
# caller (app.py) sets dev mode via set_dev_mode().  Once the container is
# ready, configure_settings_service() wires the DevModeService and all
# subsequent calls delegate there.

_dev_mode_service: Optional["DevModeService"] = None

# Fallback flag used *only* during early bootstrap, before the service exists.
_early_dev_mode: bool = False


def _get_service() -> Optional["DevModeService"]:
    """Return the DevModeService if it has been wired, else None."""
    return _dev_mode_service


def configure_settings_service(settings_service: "SettingsService") -> None:
    """Attach settings service for persisting dev/admin flags.

    This also creates the DevModeService if it hasn't been wired yet,
    transferring any early-bootstrap dev mode flag into the service.
    """
    global _dev_mode_service, _early_dev_mode
    if _dev_mode_service is None:
        from ..services.dev_mode_service import DevModeService
        _dev_mode_service = DevModeService()
    # Transfer any early flag that was set before the service existed
    if _early_dev_mode and not _dev_mode_service.is_dev_mode():
        _dev_mode_service.set_dev_mode(True)
    _dev_mode_service.configure_settings_service(settings_service)


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
        if enabled:
            logger.warning("Dev mode enabled - admin requirements bypassed for tab loading")


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


def needs_admin_for_plugin(is_windows: bool, requires_admin: bool, is_admin: bool) -> bool:
    """Determine whether admin privileges are required for a plugin tab creation.
    
    Args:
        is_windows: True if running on Windows, False otherwise
        requires_admin: True if the plugin requires admin privileges
        is_admin: True if the application is currently running with admin privileges
        
    Returns:
        True if admin privileges are required, False otherwise
        
    Note:
        On Windows: admin is required if plugin requires it and app is not running as admin.
        On Linux: admin is required if plugin requires it and daemon is not available.
        In dev mode: admin requirements are always bypassed.
    """
    # Dev mode bypasses all admin requirements for tab loading
    if is_dev_mode():
        return False
    
    if not requires_admin:
        return False
    
    if is_windows:
        return requires_admin and not is_admin
    
    # Linux: check daemon availability
    if platform.system().lower() == "linux":
        try:
            from GUI.app.daemon import is_daemon_available
            return not is_daemon_available()
        except Exception:
            # If daemon module not available, assume admin required
            return True
    
    return False


__all__ = [
    'configure_settings_service',
    'set_dev_mode_service',
    'needs_admin_for_plugin',
    'set_dev_mode',
    'is_dev_mode',
    'set_show_all_platforms',
    'is_show_all_platforms',
]
