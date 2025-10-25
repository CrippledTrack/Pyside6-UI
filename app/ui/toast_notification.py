"""
Toast notification system for non-intrusive user feedback.

Provides animated toast notifications that appear temporarily.
"""
from __future__ import annotations

import logging
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QFrame
)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect
from PySide6.QtGui import QFont, QPalette, QColor

logger = logging.getLogger(__name__)


class ToastNotification(QFrame):
    """A toast notification widget that appears temporarily."""
    
    def __init__(self, message: str, notification_type: str = "info", duration: int = 3000, parent=None, theme_manager=None):
        super().__init__(parent)
        self.message = message
        self.notification_type = notification_type
        self.duration = duration
        self.theme_manager = theme_manager
        self.setup_ui()
        self.setup_animation()
        self.apply_theme()
    
    def setup_ui(self):
        """Setup the toast notification UI."""
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(320, 70)
        # Set a semi-transparent background instead of fully transparent
        self.setWindowOpacity(0.95)
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Content frame
        content_frame = QFrame()
        content_frame.setObjectName("toastContent")
        content_layout = QHBoxLayout(content_frame)
        content_layout.setContentsMargins(15, 10, 12, 10)
        content_layout.setSpacing(8)
        
        # Message label (no icon)
        self.message_label = QLabel(self.message)
        self.message_label.setWordWrap(True)
        self.message_label.setFont(QFont("Segoe UI", 9))
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        content_layout.addWidget(self.message_label)
        
        # Close button
        close_button = QPushButton("×")
        close_button.setFixedSize(18, 18)
        close_button.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        close_button.clicked.connect(self.close_toast)
        close_button.setObjectName("closeButton")
        content_layout.addWidget(close_button)
        
        layout.addWidget(content_frame)
        
    
    
    def apply_theme(self):
        """Apply theme styling based on notification type and current theme."""
        if self.theme_manager:
            # Get current theme colors
            current_theme = self.theme_manager.get_current_theme()
            theme_data = self.theme_manager.themes.get(current_theme, {})
            palette = theme_data.get('palette', {})
            
            # Extract theme colors
            window_color = palette.get('window', '#ffffff')
            window_text_color = palette.get('window_text', '#000000')
            base_color = palette.get('base', '#ffffff')
            highlight_color = palette.get('highlight', '#0078d4')
            
            # Determine if theme is dark
            is_dark = self._is_dark_theme(window_color)
            
            # Get notification-specific colors
            colors = self._get_notification_colors(self.notification_type, is_dark)
        else:
            # Fallback to default colors
            colors = self._get_default_notification_colors(self.notification_type)
        
        self.setStyleSheet(f"""
            QFrame#toastContent {{
                background-color: {colors['background']};
                border: 2px solid {colors['border']};
                border-radius: 8px;
            }}
            QLabel {{
                color: {colors['text']};
                font-family: "Segoe UI", Arial, sans-serif;
                background-color: transparent;
                font-weight: 500;
            }}
            QPushButton#closeButton {{
                background-color: transparent;
                border: none;
                color: {colors['text']};
                font-weight: bold;
                border-radius: 9px;
                padding: 2px;
            }}
            QPushButton#closeButton:hover {{
                background-color: {colors['hover']};
            }}
        """)
    
    def _is_dark_theme(self, window_color: str) -> bool:
        """Determine if the theme is dark based on window color."""
        try:
            # Convert hex to RGB
            if window_color.startswith('#'):
                hex_color = window_color.lstrip('#')
                r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
                # Calculate luminance
                luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
                return luminance < 0.5
        except:
            pass
        return False
    
    def _get_notification_colors(self, notification_type: str, is_dark: bool) -> dict:
        """Get notification colors based on type and theme."""
        if is_dark:
            base_styles = {
                "info": {
                    "background": "rgba(33, 150, 243, 0.85)",
                    "border": "#2196f3",
                    "text": "#ffffff",
                    "hover": "rgba(33, 150, 243, 0.95)"
                },
                "success": {
                    "background": "rgba(76, 175, 80, 0.85)",
                    "border": "#4caf50",
                    "text": "#ffffff",
                    "hover": "rgba(76, 175, 80, 0.95)"
                },
                "warning": {
                    "background": "rgba(255, 152, 0, 0.85)",
                    "border": "#ff9800",
                    "text": "#ffffff",
                    "hover": "rgba(255, 152, 0, 0.95)"
                },
                "error": {
                    "background": "rgba(244, 67, 54, 0.85)",
                    "border": "#f44336",
                    "text": "#ffffff",
                    "hover": "rgba(244, 67, 54, 0.95)"
                },
                "loading": {
                    "background": "rgba(156, 39, 176, 0.85)",
                    "border": "#9c27b0",
                    "text": "#ffffff",
                    "hover": "rgba(156, 39, 176, 0.95)"
                }
            }
        else:
            base_styles = {
                "info": {
                    "background": "#ffffff",
                    "border": "#2196f3",
                    "text": "#1976d2",
                    "hover": "rgba(33, 150, 243, 0.1)"
                },
                "success": {
                    "background": "#ffffff",
                    "border": "#4caf50",
                    "text": "#2e7d32",
                    "hover": "rgba(76, 175, 80, 0.1)"
                },
                "warning": {
                    "background": "#ffffff",
                    "border": "#ff9800",
                    "text": "#f57c00",
                    "hover": "rgba(255, 152, 0, 0.1)"
                },
                "error": {
                    "background": "#ffffff",
                    "border": "#f44336",
                    "text": "#d32f2f",
                    "hover": "rgba(244, 67, 54, 0.1)"
                },
                "loading": {
                    "background": "#ffffff",
                    "border": "#9c27b0",
                    "text": "#7b1fa2",
                    "hover": "rgba(156, 39, 176, 0.1)"
                }
            }
        
        return base_styles.get(notification_type, base_styles["info"])
    
    def _get_default_notification_colors(self, notification_type: str) -> dict:
        """Get default notification colors when no theme manager is available."""
        return self._get_notification_colors(notification_type, False)
    
    def setup_animation(self):
        """Setup slide-in animation."""
        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(250)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # Auto-close timer
        self.close_timer = QTimer()
        self.close_timer.setSingleShot(True)
        self.close_timer.timeout.connect(self.close_toast)
    
    def show_toast(self, parent_widget: Optional[QWidget] = None):
        """Show the toast notification with animation."""
        if parent_widget:
            # Position relative to parent - try to get the main window
            main_window = parent_widget
            while main_window and not hasattr(main_window, 'geometry'):
                main_window = main_window.parent()
            
            if main_window and hasattr(main_window, 'geometry'):
                parent_rect = main_window.geometry()
                # Position in top-right corner with better spacing
                x = parent_rect.x() + parent_rect.width() - self.width() - 15
                y = parent_rect.y() + 15
                self.move(x, y)
            else:
                # Fallback positioning
                self.move(100, 100)
        
        # Start hidden above the target position
        start_rect = QRect(self.x(), self.y() - self.height(), self.width(), self.height())
        end_rect = QRect(self.x(), self.y(), self.width(), self.height())
        
        self.setGeometry(start_rect)
        self.show()
        
        # Animate slide down
        self.animation.setStartValue(start_rect)
        self.animation.setEndValue(end_rect)
        self.animation.start()
        
        # Start auto-close timer
        self.close_timer.start(self.duration)
        
        logger.debug(f"Showing toast: {self.message}")
    
    def close_toast(self):
        """Close the toast notification with animation."""
        if hasattr(self, 'animation') and self.animation.state() == QPropertyAnimation.State.Running:
            return  # Already animating
        
        # Animate slide up and close
        current_rect = self.geometry()
        end_rect = QRect(current_rect.x(), current_rect.y() - self.height(), 
                        current_rect.width(), current_rect.height())
        
        self.animation.setStartValue(current_rect)
        self.animation.setEndValue(end_rect)
        self.animation.setEasingCurve(QEasingCurve.Type.InCubic)
        self.animation.finished.connect(self.close)
        self.animation.start()
        
        logger.debug(f"Closing toast: {self.message}")


class ToastManager:
    """Manages multiple toast notifications."""
    
    def __init__(self, parent_widget: Optional[QWidget] = None, theme_manager=None):
        self.parent_widget = parent_widget
        self.theme_manager = theme_manager
        self.active_toasts: list[ToastNotification] = []
        self.max_toasts = 3  # Maximum number of toasts to show
    
    def show_toast(self, message: str, notification_type: str = "info", duration: int = 3000):
        """Show a toast notification."""
        # Close all existing toasts when showing a new one
        self.clear_all()
        
        # Create and show new toast
        toast = ToastNotification(message, notification_type, duration, self.parent_widget, self.theme_manager)
        toast.show_toast(self.parent_widget)
        
        # Track active toasts
        self.active_toasts.append(toast)
        
        # Clean up when toast closes
        toast.destroyed.connect(lambda: self.active_toasts.remove(toast) if toast in self.active_toasts else None)
    
    def show_info(self, message: str, duration: int = 3000):
        """Show info toast."""
        self.show_toast(message, "info", duration)
    
    def show_success(self, message: str, duration: int = 3000):
        """Show success toast."""
        self.show_toast(message, "success", duration)
    
    def show_warning(self, message: str, duration: int = 4000):
        """Show warning toast."""
        self.show_toast(message, "warning", duration)
    
    def show_error(self, message: str, duration: int = 5000):
        """Show error toast."""
        self.show_toast(message, "error", duration)
    
    def show_loading(self, message: str, duration: int = 2000):
        """Show loading toast."""
        self.show_toast(message, "loading", duration)
    
    def clear_all(self):
        """Clear all active toasts."""
        for toast in self.active_toasts.copy():
            toast.close_toast()
        self.active_toasts.clear()
    
    def refresh_theme(self):
        """Refresh all active toasts with current theme."""
        for toast in self.active_toasts:
            if hasattr(toast, 'apply_theme'):
                toast.apply_theme()
    
    def update_theme_manager(self, theme_manager):
        """Update the theme manager reference."""
        self.theme_manager = theme_manager
