"""Utilities for determining admin requirements for plugins.

This module provides functions to check if admin privileges are required
for plugin operations on different platforms.
"""

from __future__ import annotations

import logging
import platform
from typing import Optional, TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..services.settings_service import SettingsService

# Dev mode flag - when True, admin requirements are bypassed for tab loading
_dev_mode: bool = False

# Cross-platform tabs flag - when True, tabs from all platforms are shown (dev mode only)
_show_all_platforms: bool = False
_settings_service: Optional["SettingsService"] = None


def configure_settings_service(settings_service: "SettingsService") -> None:
    """Attach settings service for persisting dev/admin flags."""
    global _settings_service, _dev_mode, _show_all_platforms
    _settings_service = settings_service
    try:
        if not _dev_mode:
            _dev_mode = settings_service.get_dev_mode()
        if not _show_all_platforms:
            _show_all_platforms = settings_service.get_show_all_platforms()
        _persist_flags()
    except Exception as e:
        logger.debug("Failed to sync dev flags from settings: %s", e)


def _persist_flags() -> None:
    if not _settings_service:
        return
    _settings_service.save_dev_mode(_dev_mode)
    _settings_service.save_show_all_platforms(_show_all_platforms)


def set_dev_mode(enabled: bool) -> None:
    """Set the dev mode flag.
    
    When dev mode is enabled, admin requirements for tab loading are bypassed.
    This allows testing the UI without elevated privileges.
    
    Args:
        enabled: True to enable dev mode, False to disable
    """
    global _dev_mode
    _dev_mode = enabled
    if not enabled:
        _show_all_platforms = False
    _persist_flags()
    if enabled:
        logger.warning("Dev mode enabled - admin requirements bypassed for tab loading")


def is_dev_mode() -> bool:
    """Check if dev mode is enabled.
    
    Returns:
        True if dev mode is enabled, False otherwise
    """
    return _dev_mode


def set_show_all_platforms(enabled: bool) -> None:
    """Set the show all platforms flag (only effective in dev mode).
    
    When enabled, tabs from all platforms (Windows and Linux) are shown
    regardless of the current platform. This is useful for UI testing.
    
    Args:
        enabled: True to show all platform tabs, False to filter by current platform
    """
    global _show_all_platforms, _dev_mode
    if enabled and not _dev_mode:
        logger.info("Show all platforms ignored because dev mode is disabled")
        return
    _show_all_platforms = enabled
    _persist_flags()
    
    logger.warning(f"set_show_all_platforms({enabled}) called - dev_mode={_dev_mode}, module_id={id(__import__('sys').modules.get(__name__, 'unknown'))}")
    
    if enabled:
        logger.warning("Show all platforms enabled - Windows and Linux tabs will be shown")
    else:
        logger.info("Show all platforms disabled - filtering by current platform")


def is_show_all_platforms() -> bool:
    """Check if show all platforms is enabled.
    
    Note: This only returns True if both dev mode AND show_all_platforms are enabled.
    
    Returns:
        True if showing all platform tabs, False otherwise
    """
    result = _dev_mode and _show_all_platforms
    logger.debug(f"is_show_all_platforms() called: dev_mode={_dev_mode}, show_all={_show_all_platforms}, result={result}")
    return result


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
    if _dev_mode:
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
    'needs_admin_for_plugin',
    'set_dev_mode',
    'is_dev_mode',
    'set_show_all_platforms',
    'is_show_all_platforms',
]


