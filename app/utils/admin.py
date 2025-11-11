"""Utilities for determining admin requirements for plugins.

This module provides functions to check if admin privileges are required
for plugin operations on different platforms.
"""

from __future__ import annotations

import logging
import platform

logger = logging.getLogger(__name__)


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
    """
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


__all__ = ['needs_admin_for_plugin']


