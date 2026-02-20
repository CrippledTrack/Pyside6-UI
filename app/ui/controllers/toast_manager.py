"""
Toast notification manager for non-intrusive user feedback.

Manages multiple toast notifications.
"""
from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ...qt_bindings import QWidget
    from ....themes.theme_manager import ThemeManager
    from ..widgets.toast_notification import ToastNotification
    from ...services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class ToastManager:
    """Manages multiple toast notifications."""
    
    def __init__(
        self,
        parent_widget: Optional["QWidget"] = None,
        theme_manager: Optional["ThemeManager"] = None,
        notification_service: Optional["NotificationService"] = None
    ) -> None:
        self.parent_widget = parent_widget
        self.theme_manager = theme_manager
        self.notification_service = notification_service
        self.active_toasts: list["ToastNotification"] = []
    
    def show_toast(self, message: str, notification_type: str = "info", duration: int = 3000) -> None:
        """Show a toast notification."""
        from ..widgets.toast_notification import ToastNotification
        from ...services.notification_service import NotificationType
        
        # Add to notification history if service is available
        if self.notification_service:
            try:
                # Map string type to enum
                type_map = {
                    "info": NotificationType.INFO,
                    "success": NotificationType.SUCCESS,
                    "warning": NotificationType.WARNING,
                    "error": NotificationType.ERROR,
                    "loading": NotificationType.INFO
                }
                service_type = type_map.get(notification_type, NotificationType.INFO)
                self.notification_service.add_notification(message, service_type)
            except Exception as e:
                logger.error(f"Failed to add notification to history: {e}")

        # Close all existing toasts when showing a new one
        self.clear_all()
        
        # Create and show new toast
        toast = ToastNotification(message, notification_type, duration, self.parent_widget, self.theme_manager)
        toast.show_toast(self.parent_widget)
        
        # Track active toasts
        self.active_toasts.append(toast)
        
        # Clean up when toast closes
        def remove_toast():
            if toast in self.active_toasts:
                self.active_toasts.remove(toast)
        
        toast.destroyed.connect(remove_toast)
    
    def show_info(self, message: str, duration: int = 3000) -> None:
        """Show info toast."""
        self.show_toast(message, "info", duration)
    
    def show_success(self, message: str, duration: int = 3000) -> None:
        """Show success toast."""
        self.show_toast(message, "success", duration)
    
    def show_warning(self, message: str, duration: int = 4000) -> None:
        """Show warning toast."""
        self.show_toast(message, "warning", duration)
    
    def show_error(self, message: str, duration: int = 5000) -> None:
        """Show error toast."""
        self.show_toast(message, "error", duration)
    
    def show_loading(self, message: str, duration: int = 2000) -> None:
        """Show loading toast."""
        self.show_toast(message, "loading", duration)
    
    def clear_all(self) -> None:
        """Clear all active toasts."""
        for toast in self.active_toasts.copy():
            toast.close_toast()
        self.active_toasts.clear()
    
    def refresh_theme(self) -> None:
        """Refresh all active toasts with current theme."""
        for toast in self.active_toasts:
            if hasattr(toast, 'apply_theme'):
                toast.apply_theme()
    
    def update_theme_manager(self, theme_manager: Optional["ThemeManager"]) -> None:
        """Update the theme manager reference."""
        self.theme_manager = theme_manager


__all__ = ['ToastManager']

