"""
Example plugin for Basic GUI Application.

This demonstrates how to create a comprehensive plugin using all v3.4.0
extension interfaces:
- TabExtension (via BaseTabPlugin) - provides a tab in the main window
- MenuExtension - contributes menu items
- StatusExtension - provides a status bar widget
- ToolbarExtension - contributes toolbar actions
- ServiceExtension - runs background service
- EventSubscriberExtension - subscribes to application events
- SettingsExtension - provides configurable settings
"""
from __future__ import annotations

from typing import Optional, Dict, List, Any, Callable
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTextEdit, QCheckBox, QSpinBox, QFormLayout, QMessageBox
)
from PySide6.QtCore import QTimer

from GUI.plugins.base import BaseTabPlugin
from GUI.plugin_system.interfaces import (
    MenuExtension,
    StatusExtension,
    ToolbarExtension,
    ServiceExtension,
    EventSubscriberExtension,
    SettingsExtension,
)
from GUI.plugin_system.types import MenuItemDefinition, ToolbarAction


class ExampleTabPlugin(
    BaseTabPlugin,
    MenuExtension,
    StatusExtension,
    ToolbarExtension,
    ServiceExtension,
    EventSubscriberExtension,
    SettingsExtension
):
    """
    Comprehensive example plugin demonstrating all v3.4.0 extension interfaces.
    
    This plugin shows how a single class can implement multiple interfaces
    to extend the application in various ways.
    """
    
    # =========================================================================
    # Plugin Metadata (from BaseTabPlugin/Plugin)
    # =========================================================================
    tab_name = "Example Plugin"
    tab_description = "A comprehensive example plugin showing all v3.4.0 extension points"
    supported_platforms = ["Windows", "Linux"]
    requires_admin = False
    plugin_version = "2.0.0"
    plugin_author = "Example Author"
    plugin_authors = ["Example Author", "Contributors"]
    min_gui_version = "3.4.0"
    required_gui_version = ">=3.4.0"
    disabled_by_default = False  # Set to False to test extensions on launch
    
    # Dependencies on other plugins (optional)
    dependencies: List[str] = []
    
    # Internal state (for demo purposes)
    _event_log: List[str] = []
    _status_label: Optional[QLabel] = None
    _action_count: int = 0
    _settings: Dict[str, Any] = {
        "notifications_enabled": True,
        "refresh_interval": 30,
        "show_popups": True,
    }
    
    # =========================================================================
    # TabExtension Interface
    # =========================================================================
    
    @classmethod
    def create_widget(cls, parent: Optional[QWidget] = None) -> QWidget:
        """Create the widget for this tab."""
        return ExampleWidget(parent)
    
    @classmethod
    def on_tab_activated(cls, widget: Any) -> None:
        """Called when the tab becomes active."""
        cls._log_event("Tab activated")
        cls._update_status("Active")
    
    @classmethod
    def on_tab_deactivated(cls, widget: Any) -> None:
        """Called when the tab becomes inactive."""
        cls._log_event("Tab deactivated")
        cls._update_status("Ready")
    
    # =========================================================================
    # MenuExtension Interface
    # =========================================================================
    
    @classmethod
    def get_menu_items(cls) -> List[MenuItemDefinition]:
        """Return menu items to add to the application menu bar."""
        return [
            MenuItemDefinition(
                menu="Tools",
                label="Example Plugin Action",
                callback=cls._on_menu_action,
                shortcut="Ctrl+Shift+E",
                separator_before=True,
            ),
            MenuItemDefinition(
                menu="Help",
                label="About Example Plugin",
                callback=cls._on_about_action,
            ),
        ]
    
    @classmethod
    def _on_menu_action(cls) -> None:
        """Handle the custom menu action."""
        cls._action_count += 1
        cls._log_event(f"Menu action triggered (#{cls._action_count})")
        cls._update_status(f"Action #{cls._action_count}")
        
        if cls._settings.get("show_popups", True):
            QMessageBox.information(
                None,
                "Example Plugin",
                f"Menu action triggered!\n\n"
                f"This is action #{cls._action_count}.\n"
                f"Check the Example Plugin tab for the event log."
            )
    
    @classmethod
    def _on_about_action(cls) -> None:
        """Handle the about menu item."""
        cls._log_event("About dialog opened")
        QMessageBox.about(
            None,
            "About Example Plugin",
            "<h2>Example Plugin v2.0</h2>"
            "<p>A comprehensive example demonstrating all v3.4.0 extension interfaces:</p>"
            "<ul>"
            "<li><b>TabExtension</b> - This tab you're viewing</li>"
            "<li><b>MenuExtension</b> - Tools → Example Plugin Action</li>"
            "<li><b>StatusExtension</b> - Status bar indicator</li>"
            "<li><b>ToolbarExtension</b> - Toolbar button</li>"
            "<li><b>ServiceExtension</b> - Background service lifecycle</li>"
            "<li><b>EventSubscriberExtension</b> - Responds to app events</li>"
            "<li><b>SettingsExtension</b> - Configurable settings</li>"
            "</ul>"
        )
    
    # =========================================================================
    # StatusExtension Interface
    # =========================================================================
    
    @classmethod
    def create_status_widget(cls, parent: Optional[Any] = None) -> Any:
        """Create a widget to display in the status bar."""
        cls._status_label = QLabel("Example: Ready")
        cls._status_label.setStyleSheet(
            "padding: 2px 8px; "
            "color: #4CAF50; "
            "font-weight: bold;"
        )
        cls._status_label.setToolTip("Example Plugin status indicator")
        return cls._status_label
    
    @classmethod
    def _update_status(cls, status: str) -> None:
        """Update the status bar indicator."""
        if cls._status_label:
            cls._status_label.setText(f"Example: {status}")
    
    # =========================================================================
    # ToolbarExtension Interface
    # =========================================================================
    
    @classmethod
    def get_toolbar_actions(cls) -> List[ToolbarAction]:
        """Return actions to add to the main toolbar."""
        return [
            ToolbarAction(
                label="Example Plugin",
                callback=cls._on_toolbar_action,
                tooltip="Click to trigger Example Plugin action (Ctrl+Shift+E)",
                checkable=False,
            ),
        ]
    
    @classmethod
    def _on_toolbar_action(cls) -> None:
        """Handle toolbar action."""
        cls._action_count += 1
        cls._log_event(f"Toolbar action triggered (#{cls._action_count})")
        cls._update_status(f"Action #{cls._action_count}")
        
        if cls._settings.get("show_popups", True):
            QMessageBox.information(
                None,
                "Example Plugin",
                f"Toolbar action triggered!\n\n"
                f"This is action #{cls._action_count}.\n"
                f"Check the Example Plugin tab for the event log."
            )
    
    # =========================================================================
    # ServiceExtension Interface
    # =========================================================================
    
    @classmethod
    def on_application_start(cls, container: Any) -> None:
        """Called when the application starts."""
        cls._log_event("Application started - service initialized")
        cls._log_event("   Container services are now available")
    
    @classmethod
    def on_application_shutdown(cls) -> None:
        """Called when the application is shutting down."""
        cls._log_event("Application shutting down - cleaning up")
        # Could stop background tasks, save state, etc.
    
    # =========================================================================
    # EventSubscriberExtension Interface
    # =========================================================================
    
    @classmethod
    def get_event_subscriptions(cls) -> Dict[str, Callable]:
        """Return a mapping of event names to callback functions."""
        return {
            "plugin_enabled": cls._on_plugin_enabled,
            "plugin_disabled": cls._on_plugin_disabled,
            "theme_changed": cls._on_theme_changed,
        }
    
    @classmethod
    def _on_plugin_enabled(cls, event_data: Dict[str, Any]) -> None:
        """Handle plugin_enabled event."""
        plugin_name = event_data.get("plugin_name", "Unknown")
        cls._log_event(f"Event: Plugin '{plugin_name}' was enabled")
    
    @classmethod
    def _on_plugin_disabled(cls, event_data: Dict[str, Any]) -> None:
        """Handle plugin_disabled event."""
        plugin_name = event_data.get("plugin_name", "Unknown")
        cls._log_event(f"Event: Plugin '{plugin_name}' was disabled")
    
    @classmethod
    def _on_theme_changed(cls, event_data: Dict[str, Any]) -> None:
        """Handle theme_changed event."""
        theme = event_data.get("theme", "Unknown")
        cls._log_event(f"Event: Theme changed to '{theme}'")
    
    # =========================================================================
    # SettingsExtension Interface
    # =========================================================================
    
    @classmethod
    def get_settings_widget(cls, parent: Optional[Any] = None) -> Optional[Any]:
        """Get a settings widget for this plugin."""
        return ExampleSettingsWidget(parent, cls._settings)
    
    @classmethod
    def on_settings_changed(cls, settings_dict: Dict[str, Any]) -> None:
        """Called when plugin settings are changed."""
        cls._settings.update(settings_dict)
        cls._log_event(f"Settings updated: {settings_dict}")
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    @classmethod
    def _log_event(cls, message: str) -> None:
        """Log an event for display in the UI."""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        cls._event_log.append(f"[{timestamp}] {message}")
        # Keep only last 100 events
        if len(cls._event_log) > 100:
            cls._event_log = cls._event_log[-100:]
    
    @classmethod
    def get_event_log(cls) -> List[str]:
        """Get the event log for display."""
        return cls._event_log.copy()


class ExampleWidget(QWidget):
    """The actual widget displayed in the tab."""
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setup_ui()
        self._setup_refresh_timer()
        # Log that widget was created
        ExampleTabPlugin._log_event("Tab widget created")
    
    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        
        # Title label
        title_label = QLabel("Example Plugin v2.0 (v3.4.0 Extensions Demo)")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)
        
        # Description
        desc_label = QLabel(
            "This plugin demonstrates all v3.4.0 extension interfaces:\n"
            "• TabExtension - This tab you're viewing\n"
            "• MenuExtension - Tools → Example Plugin Action (Ctrl+Shift+E)\n"
            "• StatusExtension - \"Example: Ready\" in status bar\n"
            "• ToolbarExtension - \"Example Plugin\" button in Plugins menu\n"
            "• ServiceExtension - Background service lifecycle\n"
            "• EventSubscriberExtension - Responds to plugin/theme events\n"
            "• SettingsExtension - Configurable settings (coming soon)"
        )
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # Event log section
        log_label = QLabel("Event Log (auto-refreshes every 1 second):")
        log_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(log_label)
        
        self.event_log = QTextEdit()
        self.event_log.setReadOnly(True)
        self.event_log.setMinimumHeight(250)
        self.event_log.setStyleSheet("font-family: monospace;")
        layout.addWidget(self.event_log)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("Refresh Log")
        self.refresh_btn.clicked.connect(self._refresh_log)
        btn_layout.addWidget(self.refresh_btn)
        
        self.clear_btn = QPushButton("Clear Log")
        self.clear_btn.clicked.connect(self._clear_log)
        btn_layout.addWidget(self.clear_btn)
        
        self.test_btn = QPushButton("Generate Test Event")
        self.test_btn.clicked.connect(self._generate_test_event)
        btn_layout.addWidget(self.test_btn)
        
        self.trigger_btn = QPushButton("Trigger Menu Action")
        self.trigger_btn.clicked.connect(ExampleTabPlugin._on_menu_action)
        btn_layout.addWidget(self.trigger_btn)
        
        layout.addLayout(btn_layout)
        layout.addStretch()
        
        # Initial refresh
        self._refresh_log()
    
    def _setup_refresh_timer(self):
        """Set up auto-refresh timer."""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_log)
        self.timer.start(1000)  # Refresh every 1 second for responsiveness
    
    def _refresh_log(self):
        """Refresh the event log display."""
        events = ExampleTabPlugin.get_event_log()
        if events:
            # Show newest events at top
            self.event_log.setPlainText("\n".join(reversed(events)))
        else:
            self.event_log.setPlainText(
                "No events logged yet...\n\n"
                "Try these actions to generate events:\n"
                "• Click 'Example Plugin' in the Plugins menu\n"
                "• Use menu: Tools → Example Plugin Action\n"
                "• Change the theme\n"
                "• Enable/disable other plugins"
            )
    
    def _clear_log(self):
        """Clear the event log."""
        ExampleTabPlugin._event_log.clear()
        ExampleTabPlugin._action_count = 0
        ExampleTabPlugin._log_event("Log cleared by user")
        self._refresh_log()
    
    def _generate_test_event(self):
        """Generate a test event."""
        ExampleTabPlugin._log_event("⚡ Test event generated by user")
        self._refresh_log()


class ExampleSettingsWidget(QWidget):
    """Settings widget for the example plugin."""
    
    def __init__(self, parent: Optional[QWidget] = None, settings: Dict[str, Any] = None) -> None:
        super().__init__(parent)
        self.settings = settings or {}
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the settings UI."""
        layout = QFormLayout(self)
        
        # Notifications checkbox
        self.notifications_cb = QCheckBox()
        self.notifications_cb.setChecked(self.settings.get("notifications_enabled", True))
        layout.addRow("Enable Notifications:", self.notifications_cb)
        
        # Show popups checkbox
        self.popups_cb = QCheckBox()
        self.popups_cb.setChecked(self.settings.get("show_popups", True))
        layout.addRow("Show Action Popups:", self.popups_cb)
        
        # Refresh interval
        self.refresh_spin = QSpinBox()
        self.refresh_spin.setRange(5, 300)
        self.refresh_spin.setSuffix(" seconds")
        self.refresh_spin.setValue(self.settings.get("refresh_interval", 30))
        layout.addRow("Refresh Interval:", self.refresh_spin)
    
    def get_settings(self) -> Dict[str, Any]:
        """Get the current settings values."""
        return {
            "notifications_enabled": self.notifications_cb.isChecked(),
            "show_popups": self.popups_cb.isChecked(),
            "refresh_interval": self.refresh_spin.value(),
        }


__all__ = ['ExampleTabPlugin']