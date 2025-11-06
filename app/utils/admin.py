from __future__ import annotations
import platform


def needs_admin_for_plugin(is_windows: bool, requires_admin: bool, is_admin: bool) -> bool:
    """Predicate to decide whether admin is required for a plugin tab creation.
    
    On Windows: admin is required if plugin requires it and app is not running as admin
    On Linux: admin is required if plugin requires it and daemon is not available
    """
    if not requires_admin:
        return False
    
    if is_windows:
        return bool(is_windows and requires_admin and not is_admin)
    
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


