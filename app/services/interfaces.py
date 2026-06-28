"""
Service interfaces/protocols for dependency injection.

This module defines protocols (interfaces) for all services to enable
dependency injection and improve testability.
"""

from __future__ import annotations

from typing import Protocol, Optional, Dict, Any, List, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from ..qt_bindings import QWidget
    from .settings_service import WindowGeometry


class IAdminService(Protocol):
    """Protocol for admin/elevation service."""
    
    def is_admin(self) -> bool:
        """Check if the application is running with admin privileges."""
        ...
    
    def get_sudo_status(self) -> Optional[Dict[str, Any]]:
        """Get Linux sudo status information."""
        ...
    
    def prompt_for_admin_operation(
        self,
        operation_description: str,
        parent_widget: Optional["QWidget"] = None
    ) -> bool:
        """Prompt user for admin operation and check if admin is available."""
        ...
    
    def restart_as_admin(self) -> tuple[bool, Optional[str]]:
        """Restart the application with administrator/root privileges."""
        ...

    def needs_admin_for_plugin(self, requires_admin: bool) -> bool:
        """Determine whether admin privileges are required for a plugin."""
        ...


class IDaemonService(Protocol):
    """Protocol for daemon management service."""
    
    def is_available(self) -> bool:
        """Check if the daemon is available and connected."""
        ...
    
    def is_running(self) -> bool:
        """Check if the daemon process is running."""
        ...
    
    def start(self) -> tuple[bool, Optional[str]]:
        """Start the privileged daemon."""
        ...
    
    def register_refresh_callback(self, callback: Callable[[], None]) -> None:
        """Register a callback to be called when daemon becomes available."""
        ...
    
    def unregister_refresh_callback(self, callback: Callable[[], None]) -> None:
        """Unregister a refresh callback."""
        ...
    
    def get_status_message(self) -> str:
        """Get a human-readable status message about the daemon."""
        ...


class ISettingsService(Protocol):
    """Protocol for settings service."""
    
    def get_settings(self) -> Any:
        """Get current settings."""
        ...
    
    def save_theme_preference(self, theme_name: str) -> None:
        """Save theme preference."""
        ...
    
    def get_theme_preference(self) -> str:
        """Get saved theme preference."""
        ...
    
    def save_disabled_plugins(self, plugin_names: List[str]) -> None:
        """Save user-disabled plugin names."""
        ...
    
    def get_disabled_plugins(self) -> List[str]:
        """Get saved user-disabled plugin names."""
        ...
    
    def save_window_geometry(self, x: int, y: int, width: int, height: int) -> None:
        """Save window geometry."""
        ...
    
    def get_window_geometry(self) -> "WindowGeometry":
        """Get saved window geometry."""
        ...
    
    def get_logging_enabled(self) -> bool:
        """Get logging enabled setting."""
        ...
    
    def get_log_to_file(self) -> bool:
        """Get log to file setting."""
        ...
    
    def save_ui_preferences(self, show_tooltips: bool) -> None:
        """Save UI preferences."""
        ...
    
    def get_show_tooltips(self) -> bool:
        """Get show tooltips setting."""
        ...
    
    def save_shortcuts_enabled(self, enabled: bool) -> None:
        """Save shortcuts enabled setting."""
        ...
    
    def get_shortcuts_enabled(self) -> bool:
        """Get shortcuts enabled setting."""
        ...
    
    def save_toast_settings(self, enabled: bool, duration: int) -> None:
        """Save toast notification settings."""
        ...
    
    def get_toast_notifications_enabled(self) -> bool:
        """Get toast notifications enabled setting."""
        ...
    
    def get_toast_duration(self) -> int:
        """Get toast duration setting."""
        ...
    
    def save_gui_version(self, version: str) -> None:
        """Save GUI version to settings."""
        ...
    
    def get_gui_version(self) -> str:
        """Get saved GUI version."""
        ...
    
    def save_plugin_settings(self, plugin_name: str, settings: Dict[str, Any]) -> None:
        """Save settings for a specific plugin."""
        ...
    
    def get_plugin_settings(self, plugin_name: str) -> Dict[str, Any]:
        """Get settings for a specific plugin."""
        ...


class INotificationService(Protocol):
    """Protocol for notification service."""
    
    notification_added: Any
    unread_count_changed: Any
    
    def add_notification(self, message: str, type: Any, details: Optional[str] = None) -> None:
        """Add a new notification."""
        ...
        
    def get_notifications(self) -> List[Any]:
        """Get all notifications (newest first)."""
        ...
        
    def get_unread_count(self) -> int:
        """Get count of unread notifications."""
        ...
        
    def mark_all_as_read(self) -> None:
        """Mark all notifications as read."""
        ...
        
    def clear_all(self) -> None:
        """Clear all notifications."""
        ...


__all__ = [
    'IAdminService',
    'IDaemonService',
    'ISettingsService',
    'INotificationService',
]


