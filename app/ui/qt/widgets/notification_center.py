"""
Notification center widget for displaying notification history.

The status-bar popup lists recent notifications, marks them read when opened,
and allows dismissing one row or clearing the whole history.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from ..bindings import (
    Qt,
    QColor,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QPushButton,
    QFrame,
    QTimer,
    Signal,
)

if TYPE_CHECKING:
    from ....services.notification_service import NotificationService, Notification
    from ..themes.theme_manager import ThemeManager

from ....constants import CURRENT_PLATFORM
from ....services.notification_service import NotificationType, format_notification_age
from ..themes.theme_manager import ThemeManager

_EMPTY_LABEL_NAME = "emptyNotificationsLabel"
_AGE_REFRESH_MS = 30_000


def uses_manual_popup_shadow(platform_name: Optional[str] = None) -> bool:
    """Whether this popup has to draw its own drop shadow.

    Windows is excluded because ``QGraphicsDropShadowEffect`` renders
    incorrectly there, and macOS because the compositor already shadows popup
    windows: a manual effect doubles the shadow and the translucent padding it
    needs leaves a dead border around the panel.
    """
    return (platform_name or CURRENT_PLATFORM) not in ("windows", "darwin")


def muted_notification_text_color(window_text: str, is_dark: bool) -> str:
    """Derive a muted text color from *window_text* for read/secondary labels.

    Palette ``text`` is often identical to ``window_text``, so this does not
    read that role. Dark themes darken; light themes lighten toward gray.
    """
    if is_dark:
        return ThemeManager.adjust_color(window_text, 0.55)
    return ThemeManager.adjust_color(window_text, 1.5)


class NotificationItemWidget(QFrame):
    """Widget representing a single notification item."""

    dismiss_requested = Signal(object)

    def __init__(
        self,
        notification: Notification,
        theme_manager: Optional["ThemeManager"] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.notification = notification
        self.theme_manager = theme_manager
        self.setup_ui()

    def setup_ui(self) -> None:
        # Clean, modern frame styling instead of StyledPanel/Raised
        self.setFrameShape(QFrame.Shape.NoFrame)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        self.type_label = QLabel(self.notification.type.value.upper())
        font = self.type_label.font()
        font.setBold(True)
        font.setPointSize(8)
        self.type_label.setFont(font)
        header_layout.addWidget(self.type_label)

        self.time_label = QLabel()
        font = self.time_label.font()
        font.setPointSize(8)
        self.time_label.setFont(font)
        header_layout.addWidget(self.time_label)

        header_layout.addStretch()

        self.dismiss_btn = QPushButton("×")
        self.dismiss_btn.setObjectName("dismissButton")
        self.dismiss_btn.setFixedSize(18, 18)
        self.dismiss_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dismiss_btn.setToolTip("Dismiss")
        self.dismiss_btn.setAccessibleName("Dismiss notification")
        self.dismiss_btn.clicked.connect(self._on_dismiss)
        header_layout.addWidget(self.dismiss_btn)

        layout.addLayout(header_layout)

        self.msg_label = QLabel(self.notification.message)
        self.msg_label.setWordWrap(True)
        layout.addWidget(self.msg_label)

        if self.notification.details:
            self.details_label = QLabel(self.notification.details)
            self.details_label.setWordWrap(True)
            layout.addWidget(self.details_label)
        else:
            self.details_label = None

        self.refresh_timestamp()
        self._update_styling()

    def refresh_timestamp(self, now=None) -> None:
        """Update the relative age label and absolute tooltip."""
        self.time_label.setText(
            format_notification_age(self.notification.timestamp, now)
        )
        self.time_label.setToolTip(
            self.notification.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        )

    def _on_dismiss(self) -> None:
        self.dismiss_requested.emit(self.notification)

    def _update_styling(self) -> None:
        """Apply theme-aware styling to the item widget."""
        if self.theme_manager:
            theme_data = self.theme_manager.get_theme_data()
            palette = theme_data.get('palette', {})
            button_color = palette.get('button', '#3d3d3d')
            base_color = palette.get('base', '#1e1e1e')
            highlight_color = palette.get('highlight', '#0078d4')
            text_color = palette.get('window_text', '#ffffff')
            is_dark = bool(theme_data.get('is_dark', True))
            muted_text_color = muted_notification_text_color(text_color, is_dark)
            type_color = ThemeManager.adjust_notification_color(
                highlight_color, self.notification.type
            )
        else:
            button_color = '#3d3d3d'
            base_color = '#1e1e1e'
            color_map = {
                NotificationType.INFO: "#3498db",
                NotificationType.SUCCESS: "#2ecc71",
                NotificationType.WARNING: "#f1c40f",
                NotificationType.ERROR: "#e74c3c"
            }
            type_color = color_map.get(self.notification.type, "#ffffff")
            text_color = "#ffffff"
            muted_text_color = "#888888"

        self.setStyleSheet(f"""
            NotificationItemWidget {{
                background-color: {base_color};
                border-bottom: 1px solid {button_color};
                padding: 0px;
            }}
        """)

        if hasattr(self, 'type_label'):
            self.type_label.setStyleSheet(f"color: {type_color};")
        if hasattr(self, 'time_label'):
            self.time_label.setStyleSheet(f"color: {muted_text_color};")
        if hasattr(self, 'msg_label'):
            if self.notification.read:
                self.msg_label.setStyleSheet(f"color: {muted_text_color};")
            else:
                self.msg_label.setStyleSheet(f"color: {text_color};")
        if hasattr(self, 'details_label') and self.details_label:
            self.details_label.setStyleSheet(
                f"color: {muted_text_color}; font-style: italic;"
            )
        if hasattr(self, 'dismiss_btn'):
            self.dismiss_btn.setStyleSheet(f"""
                QPushButton#dismissButton {{
                    background-color: transparent;
                    border: none;
                    color: {muted_text_color};
                    font-weight: bold;
                    border-radius: 9px;
                    padding: 0px;
                }}
                QPushButton#dismissButton:hover {{
                    color: {text_color};
                    background-color: {button_color};
                }}
            """)

    def apply_theme(self) -> None:
        """Reapply theme colors when theme or read-state changes."""
        self._update_styling()


class NotificationCenterWidget(QWidget):
    """Status-bar popup that lists notification history.

    Opening the popup marks every entry read and restyles rows. Individual
    rows can be dismissed; Clear All wipes the service history.
    """

    def __init__(
        self,
        notification_service: NotificationService,
        theme_manager: ThemeManager,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent, Qt.WindowType.Popup)
        self.notification_service = notification_service
        self.theme_manager = theme_manager

        from ..themes.ui_mode import is_classic_ui
        self._use_new_ui = not is_classic_ui(theme_manager)

        if self._use_new_ui:
            # New UI: Modern styling with rounded corners
            # Platform-specific shadow handling
            if uses_manual_popup_shadow():
                # Linux: Shadow effect works properly
                self.setFixedWidth(370)  # 350 + shadow margin
                self.setFixedHeight(420)  # 400 + shadow margin
                self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

                from ..bindings import QGraphicsDropShadowEffect
                shadow = QGraphicsDropShadowEffect(self)
                shadow.setBlurRadius(15)
                shadow.setOffset(0, 3)
                shadow.setColor(QColor(0, 0, 0, 60))
                self.setGraphicsEffect(shadow)
            else:
                # Windows and macOS: standard size, shadow left to the platform
                self.setFixedWidth(350)
                self.setFixedHeight(400)
                self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        else:
            # Classic mode: Simple styling without shadow
            self.setFixedWidth(350)
            self.setFixedHeight(400)

        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        self._age_timer = QTimer(self)
        self._age_timer.setInterval(_AGE_REFRESH_MS)
        self._age_timer.timeout.connect(self._refresh_item_timestamps)

        self.setup_ui()

        self._unsub_added = None
        self._subscribe()
        self.destroyed.connect(self._unsubscribe)

    def _subscribe(self) -> None:
        if getattr(self, "_unsub_added", None) is not None:
            return
        self._unsub_added = self.notification_service.subscribe_added(
            self.on_notification_added
        )

    def _unsubscribe(self, *_args: object) -> None:
        unsub = getattr(self, "_unsub_added", None)
        if unsub is None:
            return
        self._unsub_added = None
        try:
            unsub()
        except Exception:
            pass

    def closeEvent(self, event) -> None:
        # Qt.Popup click-outside calls close(). The widget is reused, so
        # drop the live subscription here and rebuild on the next show.
        self._age_timer.stop()
        self._unsubscribe()
        super().closeEvent(event)

    def hideEvent(self, event) -> None:
        self._age_timer.stop()
        super().hideEvent(event)

    def setup_ui(self):
        layout = QVBoxLayout(self)

        if self._use_new_ui and uses_manual_popup_shadow():
            # Add margins to prevent shadow clipping in new UI mode (Linux only)
            layout.setContentsMargins(10, 6, 10, 14)
        else:
            # Platform-drawn shadow or classic mode: no extra margins needed
            layout.setContentsMargins(0, 0, 0, 0)

        layout.setSpacing(0)

        # Create container frame
        self.container = QFrame()
        self.container.setObjectName("notificationContainer")

        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        layout.addWidget(self.container)

        # Header
        self.header = QFrame()
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(16, 12, 16, 12)

        self.title = QLabel("Notifications")
        title_font = self.title.font()
        title_font.setPointSize(11)
        title_font.setBold(True)
        self.title.setFont(title_font)
        header_layout.addWidget(self.title)

        header_layout.addStretch()

        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setToolTip("Clear all notifications")
        self.clear_btn.clicked.connect(self.clear_notifications)
        header_layout.addWidget(self.clear_btn)

        container_layout.addWidget(self.header)

        # Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setSpacing(0)
        self.scroll_layout.addStretch()  # Push items to top

        self.scroll_area.setWidget(self.scroll_content)
        container_layout.addWidget(self.scroll_area)

        # Apply theme stylesheets
        self._update_stylesheets()

        # Populate initial list
        self.refresh_list()

    def _muted_text_color(self) -> str:
        theme_data = self.theme_manager.get_theme_data()
        palette = theme_data.get('palette', {})
        text_color = palette.get('window_text', '#ffffff')
        is_dark = bool(theme_data.get('is_dark', True))
        return muted_notification_text_color(text_color, is_dark)

    def _update_stylesheets(self) -> None:
        """Generate and apply theme-aware stylesheets to all children without duplication."""
        theme_data = self.theme_manager.get_theme_data()
        palette = theme_data.get('palette', {})
        window_color = palette.get('window', '#2d2d2d')
        base_color = palette.get('base', '#1e1e1e')
        text_color = palette.get('window_text', '#ffffff')
        button_color = palette.get('button', '#3d3d3d')
        highlight_color = palette.get('highlight', '#0078d4')
        muted_text_color = self._muted_text_color()

        # Container stylesheet
        if self._use_new_ui:
            if CURRENT_PLATFORM == "windows":
                is_dark_theme = theme_data.get('is_dark', True)
                border_color = ThemeManager.adjust_color(button_color, 1.2 if is_dark_theme else 0.8)
                container_style = f"""
                    QFrame#notificationContainer {{
                        background-color: {base_color};
                        border: 2px solid {border_color};
                        border-radius: 8px;
                    }}
                """
            else:
                container_style = f"""
                    QFrame#notificationContainer {{
                        background-color: {base_color};
                        border: 1px solid {button_color};
                        border-radius: 8px;
                    }}
                """
        else:
            container_style = f"""
                QFrame#notificationContainer {{
                    background-color: {base_color};
                    border: 1px solid {button_color};
                }}
            """
        self.container.setStyleSheet(container_style)

        # Header stylesheet
        header_radius = "; border-top-left-radius: 7px; border-top-right-radius: 7px" if self._use_new_ui else ""
        self.header.setStyleSheet(f"""
            QFrame {{
                background-color: {window_color};
                border: none;
                border-bottom: 1px solid {button_color}{header_radius};
            }}
        """)
        self.title.setStyleSheet(f"color: {text_color};")

        hover_fill = ThemeManager.adjust_color(
            button_color,
            1.15 if theme_data.get('is_dark', True) else 0.92,
        )
        self.clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {muted_text_color};
                border: none;
                border-radius: 6px;
                padding: 6px 10px;
                font-weight: 500;
                font-size: 9pt;
            }}
            QPushButton:hover {{
                color: {highlight_color};
                background-color: {hover_fill};
            }}
            QPushButton:pressed {{
                color: {text_color};
            }}
            QPushButton:disabled {{
                color: {muted_text_color};
                background-color: transparent;
            }}
        """)

        # Scroll Area stylesheet
        if self._use_new_ui:
            scroll_style = f"""
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
                    background: {ThemeManager.adjust_color(button_color, 1.2)};
                }}
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                    height: 0px;
                }}
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                    background: none;
                }}
            """
            scroll_content_style = f"""
                QWidget {{
                    background-color: {base_color};
                    border-bottom-left-radius: 7px;
                    border-bottom-right-radius: 7px;
                }}
            """
            self.scroll_layout.setContentsMargins(0, 0, 0, 8)
        else:
            scroll_style = f"""
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
            """
            scroll_content_style = f"background-color: {base_color};"
            self.scroll_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area.setStyleSheet(scroll_style)
        self.scroll_content.setStyleSheet(scroll_content_style)
        self._style_empty_label()

    def apply_theme(self) -> None:
        """Reapply theme colors when theme changes."""
        from ..themes.ui_mode import is_classic_ui
        new_ui_mode = not is_classic_ui(self.theme_manager)
        ui_mode_changed = new_ui_mode != self._use_new_ui
        self._use_new_ui = new_ui_mode

        # If UI mode changed, update widget properties
        if ui_mode_changed:
            if self._use_new_ui:
                # Switch to new UI
                if uses_manual_popup_shadow():
                    # Linux: Add shadow effect and margins to fit it
                    self.setFixedWidth(370)
                    self.setFixedHeight(420)
                    self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

                    from ..bindings import QGraphicsDropShadowEffect
                    shadow = QGraphicsDropShadowEffect(self)
                    shadow.setBlurRadius(15)
                    shadow.setOffset(0, 3)
                    shadow.setColor(QColor(0, 0, 0, 60))
                    self.setGraphicsEffect(shadow)
                    self.layout().setContentsMargins(10, 6, 10, 14)
                else:
                    # Windows and macOS: platform-drawn shadow, no padding
                    self.setFixedWidth(350)
                    self.setFixedHeight(400)
                    self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
                    self.setGraphicsEffect(None)  # Remove any existing shadow
                    self.layout().setContentsMargins(0, 0, 0, 0)
            else:
                # Switch to classic mode: remove shadow and adjust size
                self.setFixedWidth(350)
                self.setFixedHeight(400)
                self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
                self.setGraphicsEffect(None)

                # Update layout margins
                self.layout().setContentsMargins(0, 0, 0, 0)

        # Reapply all stylesheets
        self._update_stylesheets()

        # Update all notification items
        for widget in self._item_widgets():
            widget.apply_theme()

    def _item_widgets(self) -> List[NotificationItemWidget]:
        widgets: List[NotificationItemWidget] = []
        for i in range(self.scroll_layout.count()):
            item = self.scroll_layout.itemAt(i)
            widget = item.widget() if item else None
            if isinstance(widget, NotificationItemWidget):
                widgets.append(widget)
        return widgets

    def _remove_empty_label(self) -> None:
        for i in range(self.scroll_layout.count()):
            item = self.scroll_layout.itemAt(i)
            widget = item.widget() if item else None
            if isinstance(widget, QLabel) and widget.objectName() == _EMPTY_LABEL_NAME:
                self.scroll_layout.takeAt(i)
                widget.deleteLater()
                return

    def _style_empty_label(self) -> None:
        muted = self._muted_text_color()
        for i in range(self.scroll_layout.count()):
            item = self.scroll_layout.itemAt(i)
            widget = item.widget() if item else None
            if isinstance(widget, QLabel) and widget.objectName() == _EMPTY_LABEL_NAME:
                widget.setStyleSheet(f"color: {muted}; padding: 20px;")

    def _show_empty_state(self) -> None:
        if self._item_widgets():
            return
        self._remove_empty_label()
        empty_label = QLabel("No notifications")
        empty_label.setObjectName(_EMPTY_LABEL_NAME)
        empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_label.setStyleSheet(f"color: {self._muted_text_color()}; padding: 20px;")
        self.scroll_layout.insertWidget(0, empty_label)

    def _update_clear_enabled(self) -> None:
        self.clear_btn.setEnabled(bool(self.notification_service.get_notifications()))

    def _make_item(self, notification: Notification) -> NotificationItemWidget:
        item = NotificationItemWidget(notification, self.theme_manager)
        item.dismiss_requested.connect(self._on_item_dismissed)
        return item

    def _trim_to_history(self) -> None:
        expected = len(self.notification_service.get_notifications())
        items = self._item_widgets()
        while len(items) > expected:
            widget = items.pop()
            self.scroll_layout.removeWidget(widget)
            widget.deleteLater()

    def _refresh_item_timestamps(self) -> None:
        for widget in self._item_widgets():
            widget.refresh_timestamp()

    def refresh_list(self) -> None:
        """Refresh the notification list from the service."""
        # Clear existing items (except the stretch at the end)
        while self.scroll_layout.count() > 1:
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        notifications = self.notification_service.get_notifications()
        if not notifications:
            self._show_empty_state()
        else:
            for note in notifications:
                item = self._make_item(note)
                self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, item)
        self._update_clear_enabled()

    def on_notification_added(self, notification: Notification):
        """Handle new notification added signal."""
        if not self.isVisible():
            return
        self._remove_empty_label()
        item = self._make_item(notification)
        self.scroll_layout.insertWidget(0, item)
        self._trim_to_history()
        self._update_clear_enabled()

    def _on_item_dismissed(self, notification: Notification) -> None:
        """Remove one notification from history and the list."""
        self.notification_service.remove_notification(notification)
        for widget in self._item_widgets():
            if widget.notification is notification:
                self.scroll_layout.removeWidget(widget)
                widget.deleteLater()
                break
        if not self._item_widgets():
            self._show_empty_state()
        self._update_clear_enabled()

    def clear_notifications(self) -> None:
        """Clear all notifications."""
        self.notification_service.clear_all()
        self.refresh_list()

    def showEvent(self, event) -> None:
        """Sync history, then mark all notifications as read."""
        super().showEvent(event)
        self._subscribe()
        self.refresh_list()
        self.notification_service.mark_all_as_read()
        for widget in self._item_widgets():
            widget.apply_theme()
        self._refresh_item_timestamps()
        self._age_timer.start()
