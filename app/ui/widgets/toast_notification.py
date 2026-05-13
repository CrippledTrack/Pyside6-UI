"""
Toast notification widget for non-intrusive user feedback.

Provides animated toast notifications that appear temporarily.
"""
from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING
from ...qt_bindings import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QFrame,
    QMainWindow,
    Qt,
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
    QRect,
    QEvent,
    QFont,
    QPalette,
    QColor,
    QMouseEvent,
    Signal,
)

if TYPE_CHECKING:
    from ....themes.theme_manager import ThemeManager

logger = logging.getLogger(__name__)


class ToastNotification(QFrame):
    """A toast notification widget that appears temporarily."""
    
    toast_closed = Signal()
    
    def __init__(
        self, 
        message: str, 
        notification_type: str = "info", 
        duration: int = 3000, 
        parent: Optional[QWidget] = None, 
        theme_manager: Optional["ThemeManager"] = None
    ) -> None:
        super().__init__(parent)  # Set parent for proper window hierarchy
        self.message = message
        self.notification_type = notification_type
        self.duration = duration
        self.theme_manager = theme_manager
        self.parent_window = parent  # Store for positioning
        self.setup_ui()
        self.setup_animation()
        self.apply_theme()
    
    def setup_ui(self) -> None:
        """Setup the toast notification UI."""
        # Set parent to establish window hierarchy (Tool windows stay above their parent)
        if self.parent_window:
            self.setParent(self.parent_window)
        
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
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
        
        # Close button (needs to be clickable while toast is click-through)
        self.close_button = QPushButton("×")
        self.close_button.setFixedSize(18, 18)
        self.close_button.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.close_button.clicked.connect(self.close_toast)
        self.close_button.setObjectName("closeButton")
        content_layout.addWidget(self.close_button)
        
        layout.addWidget(content_frame)
        
    
    
    def apply_theme(self) -> None:
        """Apply theme styling based on notification type and current theme."""
        if self.theme_manager:
            theme_data = self.theme_manager.get_theme_data()
            palette = theme_data.get('palette', {})
            window_color = palette.get('window', '#ffffff')

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
                if len(hex_color) == 3:
                    hex_color = ''.join(c + c for c in hex_color)
                r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
                # Calculate luminance
                luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
                return luminance < 0.5
        except Exception:
            pass
        return False
    
    def _get_notification_colors(self, notification_type: str, is_dark: bool) -> dict:
        """Get notification colors based on type and theme.
        
        Now derives colors from the theme's palette rather than using hardcoded values.
        """
        if not self.theme_manager:
            return self._get_default_notification_colors(notification_type)
        
        theme_data = self.theme_manager.get_theme_data()
        palette = theme_data.get('palette', {})
        
        # Extract theme colors
        window_color = palette.get('window', '#2d2d2d' if is_dark else '#ffffff')
        text_color = palette.get('window_text', '#ffffff' if is_dark else '#000000')
        base_color = palette.get('base', '#1e1e1e' if is_dark else '#f5f5f5')
        highlight_color = palette.get('highlight', '#0078d4')
        button_color = palette.get('button', '#3d3d3d' if is_dark else '#e0e0e0')
        
        # Parse highlight color to get RGB
        def parse_hex_color(hex_color: str) -> tuple:
            """Parse hex color to RGB tuple."""
            hex_color = hex_color.lstrip('#')
            if len(hex_color) == 3:
                hex_color = ''.join(c + c for c in hex_color)
            if len(hex_color) == 6:
                return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            return (0, 120, 212)  # Default blue
        
        def adjust_hue(r: int, g: int, b: int, notification_type: str) -> tuple:
            """Adjust hue based on notification type."""
            if notification_type == "success":
                # Shift toward green
                return (max(0, r - 30), min(255, g + 40), max(0, b - 30))
            elif notification_type == "warning":
                # Shift toward orange/yellow
                return (min(255, r + 50), min(255, g + 20), max(0, b - 50))
            elif notification_type == "error":
                # Shift toward red
                return (min(255, r + 60), max(0, g - 60), max(0, b - 60))
            elif notification_type == "loading":
                # Shift toward purple
                return (min(255, r + 20), max(0, g - 40), min(255, b + 40))
            else:  # info - keep original
                return (r, g, b)
        
        r, g, b = parse_hex_color(highlight_color)
        r, g, b = adjust_hue(r, g, b, notification_type)
        
        # Create colors based on theme
        if is_dark:
            border_color = f"rgb({r}, {g}, {b})"
            background_color = f"rgba({r}, {g}, {b}, 0.25)"
            hover_color = f"rgba({r}, {g}, {b}, 0.35)"
        else:
            border_color = f"rgb({r}, {g}, {b})"
            background_color = window_color
            hover_color = f"rgba({r}, {g}, {b}, 0.1)"
        
        return {
            "background": background_color,
            "border": border_color,
            "text": text_color,
            "hover": hover_color
        }
    
    def _get_default_notification_colors(self, notification_type: str) -> dict:
        """Get default notification colors when no theme manager is available."""
        palette = self.palette()
        window_color = palette.color(QPalette.ColorRole.Window)
        text_color = palette.color(QPalette.ColorRole.WindowText)
        is_dark = window_color.lightnessF() < 0.5

        accents = {
            "info": QColor("#0078d4"),
            "success": QColor("#2e7d32"),
            "warning": QColor("#ed6c02"),
            "error": QColor("#d32f2f"),
            "loading": QColor("#6a1b9a"),
        }
        accent = accents.get(notification_type, accents["info"])
        r, g, b = accent.red(), accent.green(), accent.blue()

        if is_dark:
            background_color = f"rgba({r}, {g}, {b}, 0.25)"
            hover_color = f"rgba({r}, {g}, {b}, 0.35)"
        else:
            background_color = window_color.name()
            hover_color = f"rgba({r}, {g}, {b}, 0.1)"

        return {
            "background": background_color,
            "border": accent.name(),
            "text": text_color.name(),
            "hover": hover_color,
        }
    
    def setup_animation(self) -> None:
        """Setup slide-in animation."""
        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(250)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # Auto-close timer
        self.close_timer = QTimer()
        self.close_timer.setSingleShot(True)
        self.close_timer.timeout.connect(self.close_toast)
    
    def show_toast(self, parent_widget: Optional[QWidget] = None, target_y: int = 40):
        """Show the toast notification with animation."""
        from ...qt_bindings import QPoint
        
        target_parent = parent_widget or self.parent_window
        
        if target_parent:
            x = target_parent.width() - self.width() - 15
        else:
            from ...qt_bindings import QApplication
            screen = QApplication.primaryScreen().geometry()
            x = screen.width() - self.width() - 15
            
        # Start hidden to the right
        start_rect = QRect(x + self.width() + 20, target_y, self.width(), self.height())
        end_rect = QRect(x, target_y, self.width(), self.height())
        
        self.setGeometry(start_rect)
        self.show()
        self.raise_()
        
        self.animation.stop()
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.setStartValue(start_rect)
        self.animation.setEndValue(end_rect)
        self.animation.start()
        
        # Start auto-close timer
        self.close_timer.start(self.duration)
        
        logger.debug(f"Showing toast: {self.message}")
        
    def update_position(self, target_x: int, target_y: int):
        """Smoothly move to a new position."""
        if getattr(self, '_is_closing', False):
            return
            
        current_rect = self.geometry()
        end_rect = QRect(target_x, target_y, self.width(), self.height())
        
        self.animation.stop()
        self.animation.setDuration(250)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.animation.setStartValue(current_rect)
        self.animation.setEndValue(end_rect)
        self.animation.start()
    
    def close_toast(self):
        """Close the toast notification with animation."""
        if getattr(self, '_is_closing', False):
            return
        self._is_closing = True
        
        self.animation.stop()
        
        # Animate slide out to the right
        current_rect = self.geometry()
        end_rect = QRect(current_rect.x() + self.width() + 20, current_rect.y(), 
                        current_rect.width(), current_rect.height())
        
        self.animation.setStartValue(current_rect)
        self.animation.setEndValue(end_rect)
        self.animation.setEasingCurve(QEasingCurve.Type.InCubic)
        self.animation.finished.connect(self._on_close_animation_finished)
        self.animation.start()
        
        logger.debug(f"Closing toast: {self.message}")
        
    def _on_close_animation_finished(self):
        self.toast_closed.emit()
        self.close()


__all__ = ['ToastNotification']
