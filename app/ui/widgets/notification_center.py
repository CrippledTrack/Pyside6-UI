"""
Notification center widget for displaying notification history.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ...qt_bindings import (
    Qt,
    QColor,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QPushButton,
    QFrame,
)

if TYPE_CHECKING:
    from ...services.notification_service import NotificationService, Notification
    from ...themes.theme_manager import ThemeManager

from ...constants import CURRENT_PLATFORM

from ...services.notification_service import NotificationType


def _adjust_color(hex_color: str, factor: float) -> str:
    """Adjust a hex color brightness.
    
    Args:
        hex_color: Color in hex format (e.g., '#0078d4')
        factor: Brightness adjustment. > 1 lightens, < 1 darkens
        
    Returns:
        Adjusted color in hex format
    """
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        if factor > 1:
            r = min(255, int(r + (255 - r) * (factor - 1)))
            g = min(255, int(g + (255 - g) * (factor - 1)))
            b = min(255, int(b + (255 - b) * (factor - 1)))
        else:
            r = int(r * factor)
            g = int(g * factor)
            b = int(b * factor)
        return f"#{r:02x}{g:02x}{b:02x}"
    return hex_color


def _parse_and_adjust_notification_color(hex_color: str, notification_type: NotificationType) -> str:
    """Parse hex color and adjust hue based on notification type.
    
    Args:
        hex_color: Base highlight color in hex format
        notification_type: The notification type to adjust for
        
    Returns:
        Adjusted color in hex format
    """
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    else:
        r, g, b = 0, 120, 212  # Default blue
    
    # Adjust hue based on type
    if notification_type == NotificationType.SUCCESS:
        r, g, b = max(0, r - 30), min(255, g + 40), max(0, b - 30)
    elif notification_type == NotificationType.WARNING:
        r, g, b = min(255, r + 80), min(255, g + 30), max(0, b - 80)
    elif notification_type == NotificationType.ERROR:
        r, g, b = min(255, r + 100), max(0, g - 60), max(0, b - 60)
    # INFO keeps original highlight color
    
    return f"#{r:02x}{g:02x}{b:02x}"


class NotificationItemWidget(QFrame):
    """Widget representing a single notification item."""
    
    def __init__(self, notification: Notification, theme_manager: Optional["ThemeManager"] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.notification = notification
        self.theme_manager = theme_manager
        self.setup_ui()
    
    def setup_ui(self) -> None:
        # Clean, modern frame styling instead of StyledPanel/Raised
        self.setFrameShape(QFrame.Shape.NoFrame)
        
        # Get theme colors for border
        if self.theme_manager:
            current_theme = self.theme_manager.get_current_theme()
            theme_data = self.theme_manager.themes.get(current_theme, {})
            palette = theme_data.get('palette', {})
            button_color = palette.get('button', '#3d3d3d')
            base_color = palette.get('base', '#1e1e1e')
        else:
            button_color = '#3d3d3d'
            base_color = '#1e1e1e'
        
        # Apply subtle border styling
        self.setStyleSheet(f"""
            NotificationItemWidget {{
                background-color: {base_color};
                border-bottom: 1px solid {button_color};
                padding: 0px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        
        # Header: Type and Timestamp
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        # Type indicator (colored dot or text)
        type_label = QLabel(self.notification.type.value.upper())
        font = type_label.font()
        font.setBold(True)
        font.setPointSize(8)
        type_label.setFont(font)
        
        # Get theme colors
        if self.theme_manager:
            current_theme = self.theme_manager.get_current_theme()
            theme_data = self.theme_manager.themes.get(current_theme, {})
            palette = theme_data.get('palette', {})
            
            # Get base colors from theme
            highlight_color = palette.get('highlight', '#0078d4')
            text_color = palette.get('window_text', '#ffffff')
            muted_text_color = palette.get('text', '#888888')
            
            type_color = _parse_and_adjust_notification_color(highlight_color, self.notification.type)

        else:
            # Fallback to hardcoded colors if no theme manager
            color_map = {
                NotificationType.INFO: "#3498db",
                NotificationType.SUCCESS: "#2ecc71",
                NotificationType.WARNING: "#f1c40f",
                NotificationType.ERROR: "#e74c3c"
            }
            type_color = color_map.get(self.notification.type, "#ffffff")
            text_color = "#ffffff"
            muted_text_color = "#888888"
        
        type_label.setStyleSheet(f"color: {type_color};")
        
        header_layout.addWidget(type_label)
        
        # Timestamp
        time_str = self.notification.timestamp.strftime("%H:%M:%S")
        time_label = QLabel(time_str)
        time_label.setStyleSheet(f"color: {muted_text_color};")
        font = time_label.font()
        font.setPointSize(8)
        time_label.setFont(font)
        header_layout.addWidget(time_label)
        
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Message
        msg_label = QLabel(self.notification.message)
        msg_label.setWordWrap(True)
        if self.notification.read:
            msg_label.setStyleSheet(f"color: {muted_text_color};")
        else:
            msg_label.setStyleSheet(f"color: {text_color};")
        layout.addWidget(msg_label)
        
        # Details (if any)
        if self.notification.details:
            details_label = QLabel(self.notification.details)
            details_label.setWordWrap(True)
            details_label.setStyleSheet(f"color: {muted_text_color}; font-style: italic;")
            layout.addWidget(details_label)
        
        # Store labels for theme refreshing
        self.type_label = type_label
        self.time_label = time_label
        self.msg_label = msg_label
        self.details_label = details_label if self.notification.details else None
    
    def apply_theme(self) -> None:
        """Reapply theme colors when theme changes."""
        if not self.theme_manager:
            return
        
        current_theme = self.theme_manager.get_current_theme()
        theme_data = self.theme_manager.themes.get(current_theme, {})
        palette = theme_data.get('palette', {})
        
        # Get base colors from theme
        highlight_color = palette.get('highlight', '#0078d4')
        text_color = palette.get('window_text', '#ffffff')
        muted_text_color = palette.get('text', '#888888')
        button_color = palette.get('button', '#3d3d3d')
        base_color = palette.get('base', '#1e1e1e')
        
        # Update frame styling
        self.setStyleSheet(f"""
            NotificationItemWidget {{
                background-color: {base_color};
                border-bottom: 1px solid {button_color};
                padding: 0px;
            }}
        """)
        
        type_color = _parse_and_adjust_notification_color(highlight_color, self.notification.type)

        
        # Update label styles
        self.type_label.setStyleSheet(f"color: {type_color};")
        self.time_label.setStyleSheet(f"color: {muted_text_color};")
        
        if self.notification.read:
            self.msg_label.setStyleSheet(f"color: {muted_text_color};")
        else:
            self.msg_label.setStyleSheet(f"color: {text_color};")
        
        if self.details_label:
            self.details_label.setStyleSheet(f"color: {muted_text_color}; font-style: italic;")


class NotificationCenterWidget(QWidget):
    """Widget that displays the list of notifications."""
    
    def __init__(
        self, 
        notification_service: NotificationService, 
        theme_manager: ThemeManager,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent, Qt.WindowType.Popup)
        self.notification_service = notification_service
        self.theme_manager = theme_manager
        
        # Detect if using new UI or classic mode
        self._use_new_ui = not getattr(theme_manager, '_use_legacy', True)
        
        if self._use_new_ui:
            # New UI: Modern styling with rounded corners
            # Platform-specific shadow handling
            if CURRENT_PLATFORM == "windows":
                # Windows: QGraphicsDropShadowEffect has rendering issues
                # Use standard size without shadow effect
                self.setFixedWidth(350)
                self.setFixedHeight(400)
                self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
                # No shadow effect on Windows
            else:
                # Linux: Shadow effect works properly
                self.setFixedWidth(370)  # 350 + shadow margin
                self.setFixedHeight(420)  # 400 + shadow margin
                self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
                
                from ...qt_bindings import QGraphicsDropShadowEffect
                shadow = QGraphicsDropShadowEffect(self)
                shadow.setBlurRadius(15)
                shadow.setOffset(0, 3)
                shadow.setColor(QColor(0, 0, 0, 60))
                self.setGraphicsEffect(shadow)
        else:
            # Classic mode: Simple styling without shadow
            self.setFixedWidth(350)
            self.setFixedHeight(400)
        
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        
        self.setup_ui()
        
        # Connect signals
        self.notification_service.notification_added.connect(self.on_notification_added)
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        if self._use_new_ui and CURRENT_PLATFORM != "windows":
            # Add margins to prevent shadow clipping in new UI mode (Linux only)
            layout.setContentsMargins(10, 6, 10, 14)
        else:
            # Windows or classic mode: no extra margins needed
            layout.setContentsMargins(0, 0, 0, 0)
        
        layout.setSpacing(0)
        
        # Get theme colors
        current_theme = self.theme_manager.get_current_theme()
        theme_data = self.theme_manager.themes.get(current_theme, {})
        palette = theme_data.get('palette', {})
        
        # Extract theme colors with fallbacks
        window_color = palette.get('window', '#2d2d2d')
        base_color = palette.get('base', '#1e1e1e')
        text_color = palette.get('window_text', '#ffffff')
        button_color = palette.get('button', '#3d3d3d')
        
        # Create container frame
        self.container = QFrame()
        self.container.setObjectName("notificationContainer")
        
        if self._use_new_ui:
            # New UI: rounded corners with border
            if CURRENT_PLATFORM == "windows":
                # Windows: Enhanced border for better separation without shadow
                # Adjust border based on theme brightness
                is_dark_theme = theme_data.get('is_dark', True)
                if is_dark_theme:
                    # Dark theme: slightly lighter border for visibility
                    border_color = _adjust_color(button_color, 1.2)
                else:
                    # Light theme: slightly darker border for definition
                    border_color = _adjust_color(button_color, 0.8)
                
                self.container.setStyleSheet(f"""
                    QFrame#notificationContainer {{
                        background-color: {base_color};
                        border: 2px solid {border_color};
                        border-radius: 8px;
                    }}
                """)
            else:
                # Linux: Standard border (shadow provides separation)
                self.container.setStyleSheet(f"""
                    QFrame#notificationContainer {{
                        background-color: {base_color};
                        border: 1px solid {button_color};
                        border-radius: 8px;
                    }}
                """)
        else:
            # Classic mode: simple flat styling
            self.container.setStyleSheet(f"""
                QFrame#notificationContainer {{
                    background-color: {base_color};
                    border: 1px solid {button_color};
                }}
            """)
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        layout.addWidget(self.container)
        
        # Header
        self.header = QFrame()
        if self._use_new_ui:
            # New UI: rounded top corners
            self.header.setStyleSheet(f"""
                QFrame {{
                    background-color: {window_color};
                    border: none;
                    border-bottom: 1px solid {button_color};
                    border-top-left-radius: 7px;
                    border-top-right-radius: 7px;
                }}
            """)
        else:
            # Classic mode: simple flat header
            self.header.setStyleSheet(f"""
                QFrame {{
                    background-color: {window_color};
                    border: none;
                    border-bottom: 1px solid {button_color};
                }}
            """)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(16, 12, 16, 12)
        
        self.title = QLabel("Notifications")
        title_font = self.title.font()
        title_font.setPointSize(11)
        title_font.setBold(True)
        self.title.setFont(title_font)
        self.title.setStyleSheet(f"color: {text_color};")
        header_layout.addWidget(self.title)
        
        header_layout.addStretch()
        
        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Get highlight color for accent button styling
        highlight_color = palette.get('highlight', '#0078d4')
        highlight_hover = _adjust_color(highlight_color, 1.15)
        highlight_pressed = _adjust_color(highlight_color, 0.85)
        
        self.clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {highlight_color};
                color: #ffffff;
                border: 1px solid transparent;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
                font-size: 9pt;
            }}
            QPushButton:hover {{
                background-color: {highlight_hover};
                border-color: {highlight_color};
            }}
            QPushButton:pressed {{
                background-color: {highlight_pressed};
            }}
        """)
        self.clear_btn.clicked.connect(self.clear_notifications)
        header_layout.addWidget(self.clear_btn)
        
        container_layout.addWidget(self.header)
        
        # Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        if self._use_new_ui:
            # New UI: rounded bottom corners and enhanced scrollbar
            self.scroll_area.setStyleSheet(f"""
                QScrollArea {{
                    border: none;
                    background-color: {base_color};
                    border-bottom-left-radius: 7px;
                    border-bottom-right-radius: 7px;
                }}
                QScrollBar:vertical {{
                    background: {base_color};
                    width: 10px;
                    margin: 4px 2px 8px 0px;
                }}
                QScrollBar::handle:vertical {{
                    background: {button_color};
                    border-radius: 4px;
                    min-height: 20px;
                }}
                QScrollBar::handle:vertical:hover {{
                    background: {_adjust_color(button_color, 1.2)};
                }}
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                    background: none;
                }}
            """)
        else:
            # Classic mode: simple flat styling
            self.scroll_area.setStyleSheet(f"""
                QScrollArea {{
                    border: none;
                    background-color: {base_color};
                }}
                QScrollBar:vertical {{
                    background: {base_color};
                    width: 10px;
                }}
                QScrollBar::handle:vertical {{
                    background: {button_color};
                    border-radius: 5px;
                }}
            """)
        
        self.scroll_content = QWidget()
        if self._use_new_ui:
            # New UI: rounded bottom corners
            self.scroll_content.setStyleSheet(f"""
                QWidget {{
                    background-color: {base_color};
                    border-bottom-left-radius: 7px;
                    border-bottom-right-radius: 7px;
                }}
            """)
            self.scroll_layout = QVBoxLayout(self.scroll_content)
            self.scroll_layout.setContentsMargins(0, 0, 0, 8)
        else:
            # Classic mode: simple flat styling
            self.scroll_content.setStyleSheet(f"background-color: {base_color};")
            self.scroll_layout = QVBoxLayout(self.scroll_content)
            self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        
        self.scroll_layout.setSpacing(0)
        self.scroll_layout.addStretch()  # Push items to top
        
        self.scroll_area.setWidget(self.scroll_content)
        container_layout.addWidget(self.scroll_area)
        
        # Populate initial list
        self.refresh_list()
    
    def apply_theme(self) -> None:
        """Reapply theme colors when theme changes."""
        # Check if UI mode has changed
        new_ui_mode = not getattr(self.theme_manager, '_use_legacy', True)
        ui_mode_changed = new_ui_mode != self._use_new_ui
        self._use_new_ui = new_ui_mode
        
        # If UI mode changed, update widget properties
        if ui_mode_changed:
            from ...qt_bindings import QGraphicsDropShadowEffect
            
            if self._use_new_ui:
                # Switch to new UI
                if CURRENT_PLATFORM == "windows":
                    # Windows: No shadow effect
                    self.setFixedWidth(350)
                    self.setFixedHeight(400)
                    self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
                    self.setGraphicsEffect(None)  # Remove any existing shadow
                else:
                    # Linux: Add shadow effect
                    self.setFixedWidth(370)
                    self.setFixedHeight(420)
                    self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
                    
                    from ...qt_bindings import QGraphicsDropShadowEffect
                    shadow = QGraphicsDropShadowEffect(self)
                    shadow.setBlurRadius(15)
                    shadow.setOffset(0, 3)
                    shadow.setColor(QColor(0, 0, 0, 60))
                    self.setGraphicsEffect(shadow)
                
                # Update layout margins (platform-specific)
                if CURRENT_PLATFORM == "windows":
                    # Windows: No shadow margins needed
                    self.layout().setContentsMargins(0, 0, 0, 0)
                    self.scroll_layout.setContentsMargins(0, 0, 0, 0)
                else:
                    # Linux: Add shadow margins
                    self.layout().setContentsMargins(10, 6, 10, 14)
                    self.scroll_layout.setContentsMargins(0, 0, 0, 8)
            else:
                # Switch to classic mode: remove shadow and adjust size
                self.setFixedWidth(350)
                self.setFixedHeight(400)
                self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
                self.setGraphicsEffect(None)
                
                # Update layout margins
                self.layout().setContentsMargins(0, 0, 0, 0)
                self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        
        # Get theme colors
        current_theme = self.theme_manager.get_current_theme()
        theme_data = self.theme_manager.themes.get(current_theme, {})
        palette = theme_data.get('palette', {})
        
        # Extract theme colors with fallbacks
        window_color = palette.get('window', '#2d2d2d')
        base_color = palette.get('base', '#1e1e1e')
        text_color = palette.get('window_text', '#ffffff')
        button_color = palette.get('button', '#3d3d3d')

        
        # Update container styling
        if self._use_new_ui:
            if CURRENT_PLATFORM == "windows":
                # Windows: Enhanced border for better separation
                is_dark_theme = theme_data.get('is_dark', True)
                if is_dark_theme:
                    # Dark theme: slightly lighter border
                    border_color = _adjust_color(button_color, 1.2)
                else:
                    # Light theme: slightly darker border
                    border_color = _adjust_color(button_color, 0.8)
                
                self.container.setStyleSheet(f"""
                    QFrame#notificationContainer {{
                        background-color: {base_color};
                        border: 2px solid {border_color};
                        border-radius: 8px;
                    }}
                """)
            else:
                # Linux: Standard border
                self.container.setStyleSheet(f"""
                    QFrame#notificationContainer {{
                        background-color: {base_color};
                        border: 1px solid {button_color};
                        border-radius: 8px;
                    }}
                """)
        else:
            self.container.setStyleSheet(f"""
                QFrame#notificationContainer {{
                    background-color: {base_color};
                    border: 1px solid {button_color};
                }}
            """)
        
        # Update header
        if self._use_new_ui:
            self.header.setStyleSheet(f"""
                QFrame {{
                    background-color: {window_color};
                    border: none;
                    border-bottom: 1px solid {button_color};
                    border-top-left-radius: 7px;
                    border-top-right-radius: 7px;
                }}
            """)
        else:
            self.header.setStyleSheet(f"""
                QFrame {{
                    background-color: {window_color};
                    border: none;
                    border-bottom: 1px solid {button_color};
                }}
            """)
        self.title.setStyleSheet(f"color: {text_color};")
        
        # Update Clear All button with accent styling
        highlight_color = palette.get('highlight', '#0078d4')
        highlight_hover = _adjust_color(highlight_color, 1.15)
        highlight_pressed = _adjust_color(highlight_color, 0.85)

        
        self.clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {highlight_color};
                color: #ffffff;
                border: 1px solid transparent;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
                font-size: 9pt;
            }}
            QPushButton:hover {{
                background-color: {highlight_hover};
                border-color: {highlight_color};
            }}
            QPushButton:pressed {{
                background-color: {highlight_pressed};
            }}
        """)
        
        # Update scroll area
        if self._use_new_ui:
            self.scroll_area.setStyleSheet(f"""
                QScrollArea {{
                    border: none;
                    background-color: {base_color};
                    border-bottom-left-radius: 7px;
                    border-bottom-right-radius: 7px;
                }}
                QScrollBar:vertical {{
                    background: {base_color};
                    width: 10px;
                    margin: 4px 2px 8px 0px;
                }}
                QScrollBar::handle:vertical {{
                    background: {button_color};
                    border-radius: 4px;
                    min-height: 20px;
                }}
                QScrollBar::handle:vertical:hover {{
                    background: {_adjust_color(button_color, 1.2)};
                }}
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                    background: none;
                }}
            """)
            self.scroll_content.setStyleSheet(f"""
                QWidget {{
                    background-color: {base_color};
                    border-bottom-left-radius: 7px;
                    border-bottom-right-radius: 7px;
                }}
            """)
        else:
            self.scroll_area.setStyleSheet(f"""
                QScrollArea {{
                    border: none;
                    background-color: {base_color};
                }}
                QScrollBar:vertical {{
                    background: {base_color};
                    width: 10px;
                }}
                QScrollBar::handle:vertical {{
                    background: {button_color};
                    border-radius: 5px;
                }}
            """)
            self.scroll_content.setStyleSheet(f"background-color: {base_color};")
        
        # Update all notification items
        for i in range(self.scroll_layout.count()):
            item = self.scroll_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if isinstance(widget, NotificationItemWidget):
                    widget.apply_theme()
    
    def refresh_list(self) -> None:
        """Refresh the notification list from the service."""
        # Clear existing items (except the stretch at the end)
        while self.scroll_layout.count() > 1:
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Get theme colors for empty state
        current_theme = self.theme_manager.get_current_theme()
        theme_data = self.theme_manager.themes.get(current_theme, {})
        palette = theme_data.get('palette', {})
        # Use window_text for better visibility in all themes (light and dark)
        empty_text_color = palette.get('window_text', '#ffffff')
        
        # Add items
        notifications = self.notification_service.get_notifications()
        if not notifications:
            empty_label = QLabel("No notifications")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_label.setStyleSheet(f"color: {empty_text_color}; padding: 20px; opacity: 0.7;")
            self.scroll_layout.insertWidget(0, empty_label)
        else:
            for note in notifications:
                item = NotificationItemWidget(note, self.theme_manager)
                self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, item)
    
    def on_notification_added(self, notification: Notification):
        """Handle new notification added signal."""
        # Remove empty label if present
        if self.scroll_layout.count() == 2:  # 1 widget + stretch
            first_item = self.scroll_layout.itemAt(0)
            if first_item and isinstance(first_item.widget(), QLabel) and first_item.widget().text() == "No notifications":
                self.scroll_layout.takeAt(0).widget().deleteLater()
                
        # Insert new item at top
        item = NotificationItemWidget(notification, self.theme_manager)
        self.scroll_layout.insertWidget(0, item)
    
    def clear_notifications(self) -> None:
        """Clear all notifications."""
        self.notification_service.clear_all()
        self.refresh_list()
    
    def showEvent(self, event) -> None:
        """Mark all notifications as read when widget is shown."""
        super().showEvent(event)
        self.notification_service.mark_all_as_read()
