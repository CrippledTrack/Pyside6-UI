"""
Status bar manager.

This module provides StatusBarManager to handle status bar messages
and timers.
"""

from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

from PySide6.QtCore import QTimer, QObject, Qt, QPoint
from PySide6.QtWidgets import QStatusBar, QPushButton, QWidget, QHBoxLayout, QLabel

if TYPE_CHECKING:
    from ...services.notification_service import NotificationService
    from ...themes.theme_manager import ThemeManager
    from ..widgets.notification_center import NotificationCenterWidget

logger = logging.getLogger(__name__)


class StatusBarManager(QObject):
    """Manager for status bar messages."""
    
    def __init__(
        self,
        status_bar: QStatusBar,
        parent: Optional[QObject] = None,
        notification_service: Optional["NotificationService"] = None,
        theme_manager: Optional["ThemeManager"] = None
    ) -> None:
        """Initialize the status bar manager.
        
        Args:
            status_bar: The status bar widget to manage
            parent: Optional parent object
            notification_service: Service for notifications (optional)
            theme_manager: Theme manager for styling (optional)
        """
        super().__init__(parent)
        self.status_bar = status_bar
        self.notification_service = notification_service
        self.theme_manager = theme_manager
        self._status_timer: Optional[QTimer] = None
        self._notification_widget: Optional["NotificationCenterWidget"] = None
        
        if self.notification_service:
            self._setup_notification_area()
    
    def _setup_notification_area(self) -> None:
        """Setup the notification button in status bar."""
        # Create a container widget for the right side of status bar
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 10, 0)
        layout.setSpacing(5)
        
        # Notification button
        self.notif_btn = QPushButton("🔔")
        self.notif_btn.setFlat(True)
        self.notif_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_notification_button_style(0)  # Initial style with 0 unread
        self.notif_btn.clicked.connect(self._toggle_notification_center)
        layout.addWidget(self.notif_btn)
        
        # Add container to status bar (permanent widget stays on right)
        self.status_bar.addPermanentWidget(container)
        
        # Connect signals
        self.notification_service.unread_count_changed.connect(self._update_unread_count)
        
        # Initial update
        self._update_unread_count(self.notification_service.get_unread_count())
    
    def _apply_notification_button_style(self, unread_count: int) -> None:
        """Apply theme-aware styling to notification button.
        
        Args:
            unread_count: Number of unread notifications
        """
        if self.theme_manager:
            current_theme = self.theme_manager.get_current_theme()
            theme_data = self.theme_manager.themes.get(current_theme, {})
            palette = theme_data.get('palette', {})
            
            muted_text_color = palette.get('text', '#888888')
            text_color = palette.get('window_text', '#ffffff')
            highlight_color = palette.get('highlight', '#0078d4')
            
            # Lighten highlight color for hover (simple approach: blend with white/text color)
            def lighten_color(hex_color: str) -> str:
                """Lighten a hex color."""
                hex_color = hex_color.lstrip('#')
                if len(hex_color) == 6:
                    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
                    # Lighten by 20%
                    r = min(255, int(r + (255 - r) * 0.2))
                    g = min(255, int(g + (255 - g) * 0.2))
                    b = min(255, int(b + (255 - b) * 0.2))
                    return f"#{r:02x}{g:02x}{b:02x}"
                return hex_color
            
            hover_highlight = lighten_color(highlight_color)
        else:
            # Fallback colors
            muted_text_color = '#888888'
            text_color = '#ffffff'
            highlight_color = '#3498db'
            hover_highlight = '#5dade2'
        
        if unread_count > 0:
            self.notif_btn.setStyleSheet(f"""
                QPushButton {{
                    border: none;
                    padding: 0px 5px;
                    font-weight: bold;
                    color: {highlight_color};
                }}
                QPushButton:hover {{
                    color: {hover_highlight};
                }}
            """)
        else:
            self.notif_btn.setStyleSheet(f"""
                QPushButton {{
                    border: none;
                    padding: 0px 5px;
                    font-weight: bold;
                    color: {muted_text_color};
                }}
                QPushButton:hover {{
                    color: {text_color};
                }}
            """)
    
    def _update_unread_count(self, count: int) -> None:
        """Update the notification button text/style."""
        if count > 0:
            self.notif_btn.setText(f"🔔 {count}")
        else:
            self.notif_btn.setText("🔔")
        
        # Apply theme-aware styling
        self._apply_notification_button_style(count)
            
    def _toggle_notification_center(self) -> None:
        """Toggle the notification center popup."""
        if self._notification_widget and self._notification_widget.isVisible():
            self._notification_widget.hide()
            return
            
        if not self._notification_widget:
            from ..widgets.notification_center import NotificationCenterWidget
            # Determine parent widget (mainwindow)
            parent_widget = self.parent() if isinstance(self.parent(), QWidget) else self.status_bar.window()
            
            self._notification_widget = NotificationCenterWidget(
                self.notification_service,
                self.theme_manager,
                parent_widget
            )
        
        # Position the widget above the button
        btn_pos = self.notif_btn.mapToGlobal(QPoint(0, 0))
        widget_width = self._notification_widget.width()
        widget_height = self._notification_widget.height()
        
        x = btn_pos.x() - widget_width + self.notif_btn.width()
        y = btn_pos.y() - widget_height - 5
        
        self._notification_widget.move(x, y)
        self._notification_widget.show()
        self._notification_widget.raise_()
        self._notification_widget.activateWindow()

    def show_status(self, message: str, timeout: int = 0) -> None:
        """Show a status message in the status bar.
        
        Args:
            message: Status message to display
            timeout: Timeout in milliseconds (0 = permanent, clears on next show_status call)
        """
        # Clear any existing timer
        if self._status_timer:
            self._status_timer.stop()
            self._status_timer.deleteLater()
            self._status_timer = None
        
        # Show the message
        if timeout > 0:
            self.status_bar.showMessage(message, timeout)
            # Set up timer to clear after timeout
            self._status_timer = QTimer(self)
            self._status_timer.setSingleShot(True)
            self._status_timer.timeout.connect(self.clear_status)
            self._status_timer.start(timeout)
        else:
            self.status_bar.showMessage(message)
    
    def clear_status(self) -> None:
        """Clear the status bar message."""
        # Clear any existing timer
        if self._status_timer:
            self._status_timer.stop()
            self._status_timer.deleteLater()
            self._status_timer = None
        self.status_bar.clearMessage()
    
    def get_current_message(self) -> str:
        """Get the current status bar message.
        
        Returns:
            Current message or empty string if no message
        """
        return self.status_bar.currentMessage()
    
    def refresh_theme(self) -> None:
        """Refresh notification UI elements with current theme."""
        import logging
        logger = logging.getLogger(__name__)
        
        # Refresh notification button styling
        if hasattr(self, 'notif_btn') and self.notification_service:
            count = self.notification_service.get_unread_count()
            self._apply_notification_button_style(count)
        
        # Always destroy notification widget on theme refresh so it gets recreated
        # with correct UI mode (new UI vs classic) on next open
        if self._notification_widget:
            # Get current UI mode from theme manager
            is_legacy = getattr(self.theme_manager, '_use_legacy', True)
            widget_uses_new_ui = getattr(self._notification_widget, '_use_new_ui', False)
            
            logger.debug(f"refresh_theme: is_legacy={is_legacy}, widget_uses_new_ui={widget_uses_new_ui}")
            
            # Check if UI mode changed
            ui_mode_changed = widget_uses_new_ui == is_legacy  # Should be opposite
            
            if ui_mode_changed:
                logger.debug("UI mode changed, destroying notification widget")
                was_visible = self._notification_widget.isVisible()
                self._notification_widget.hide()
                self._notification_widget.deleteLater()
                self._notification_widget = None
                
                # Recreate immediately if it was visible
                if was_visible:
                    self._toggle_notification_center()
            else:
                # Just refresh theme colors (no UI mode change)
                logger.debug("Refreshing notification widget theme colors")
                if hasattr(self._notification_widget, 'apply_theme'):
                    self._notification_widget.apply_theme()
        else:
            logger.debug("refresh_theme: notification widget does not exist yet")


__all__ = ['StatusBarManager']

