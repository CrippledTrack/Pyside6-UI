"""
Service interfaces/protocols for dependency injection.

This module defines protocols (interfaces) for all services to enable
dependency injection and improve testability.

``ISettingsService`` is defined canonically in ``plugin_system.interfaces``
and re-exported here so app code can keep importing from ``app.services.interfaces``.
"""

from __future__ import annotations

from typing import Protocol, Optional, Dict, Any, List, Callable, TYPE_CHECKING

from ...plugin_system.interfaces import ISettingsService

if TYPE_CHECKING:
    from .notification_service import Notification, NotificationType, Unsubscribe


class IAdminService(Protocol):
    """Protocol for admin/elevation service."""

    def is_admin(self) -> bool:
        """Check if the application is running with admin privileges."""
        ...

    def get_sudo_status(self) -> Optional[Dict[str, Any]]:
        """Get Linux sudo status information."""
        ...

    def prompt_for_admin_operation(self, operation_description: str) -> bool:
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

    def start(self) -> tuple[bool, Optional[str]]:
        """Start the privileged daemon."""
        ...

    def register_refresh_callback(self, callback: Callable[[], None]) -> None:
        """Register a callback to be called when daemon becomes available."""
        ...


class INotificationService(Protocol):
    """Protocol for notification service."""

    def subscribe_added(self, callback: Callable[["Notification"], None]) -> "Unsubscribe":
        """Subscribe to new notifications."""
        ...

    def subscribe_unread_changed(self, callback: Callable[[int], None]) -> "Unsubscribe":
        """Subscribe to unread count changes."""
        ...

    def add_notification(
        self,
        message: str,
        type: "NotificationType",
        details: Optional[str] = None,
    ) -> None:
        """Add a new notification."""
        ...

    def get_notifications(self) -> List["Notification"]:
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
