"""
Toast notification manager for non-intrusive user feedback.

Manages multiple toast notifications.
"""
from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING
from ...qt_bindings import QObject, QEvent

if TYPE_CHECKING:
    from ...qt_bindings import QWidget
    from ....themes.theme_manager import ThemeManager
    from ..widgets.toast_notification import ToastNotification
    from ...services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class ToastManager(QObject):
    """Manages multiple toast notifications."""
    
    def __init__(
        self,
        parent_widget: Optional["QWidget"] = None,
        theme_manager: Optional["ThemeManager"] = None,
        notification_service: Optional["NotificationService"] = None
    ) -> None:
        super().__init__(parent_widget)
        self.parent_widget = parent_widget
        self.theme_manager = theme_manager
        self.notification_service = notification_service
        self.active_toasts: list["ToastNotification"] = []
        
        if self.parent_widget:
            self.parent_widget.installEventFilter(self)
            
    def eventFilter(self, obj: 'QObject', event: 'QEvent') -> bool:
        """Handle parent widget resize to reposition toasts."""
        if obj == self.parent_widget and event.type() == QEvent.Type.Resize:
            self._reposition_toasts(animate=False)
        return super().eventFilter(obj, event)
    
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

        # Limit maximum active toasts to prevent covering too much screen
        if len(self.active_toasts) >= 5:
            oldest = self.active_toasts.pop(0)
            oldest.close_toast()
        
        # Create and show new toast
        toast = ToastNotification(message, notification_type, duration, self.parent_widget, self.theme_manager)
        
        # Determine target Y based on existing toasts
        target_y = 40
        for t in self.active_toasts:
            target_y += t.height() + 10
            
        toast.show_toast(self.parent_widget, target_y)
        
        # Track active toasts
        self.active_toasts.append(toast)
        
        # Clean up when toast closes
        def remove_toast():
            if toast in self.active_toasts:
                self.active_toasts.remove(toast)
                self._reposition_toasts(animate=True)
        
        toast.toast_closed.connect(remove_toast)
        
    def _reposition_toasts(self, animate: bool = True) -> None:
        """Update positions of all active toasts."""
        if not self.parent_widget:
            return
            
        current_y = 40
        parent_width = self.parent_widget.width()
        
        for toast in self.active_toasts:
            target_x = parent_width - toast.width() - 15
            if animate:
                toast.update_position(current_y)
            else:
                # Direct move without animation (e.g., during rapid resize)
                if hasattr(toast, 'animation'):
                    toast.animation.stop()
                toast.move(target_x, current_y)
            current_y += toast.height() + 10
    
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

