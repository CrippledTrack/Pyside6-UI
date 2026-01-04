"""
Example plugin for Basic GUI Application.

This demonstrates how to create a comprehensive plugin using all
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

import logging
from typing import Optional, Dict, List, Any, Callable, TYPE_CHECKING
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTextEdit, QCheckBox, QSpinBox, QFormLayout, QMessageBox
)
from PySide6.QtCore import QTimer

from GUI.plugin_system.base import BaseTabPlugin
from GUI.plugin_system.types import MenuItemDefinition, ToolbarAction

if TYPE_CHECKING:
    from GUI.app.services.container import ServiceContainer

# Note: Inheriting from BaseTabPlugin covers the basic Plugin requirements.
# We implement the protocols by defining the required methods.
class ExampleTabPlugin(BaseTabPlugin):
    """
    Comprehensive example plugin demonstrating all extension interfaces.
    """
    
    # =========================================================================
    # Plugin Metadata
    # =========================================================================
    plugin_name = "Example Plugin"
    tab_title = "Example Plugin"
    plugin_description = "A comprehensive example plugin showing all extension points"
    supported_platforms = ["Windows", "Linux"]
    requires_admin = False
    plugin_version = "2.0.1"
    plugin_author = "Example Author"
    plugin_authors = ["Example Author", "Contributors"]
    min_gui_version = "3.4.0"
    required_gui_version = ">=3.4.0"
    disabled_by_default = True  # Set to False to test extensions on launch
    
    # Dependencies on other plugins
    dependencies: List[str] = []
    
    def __init__(self, container: "ServiceContainer") -> None:
        """Initialize the plugin instance."""
        super().__init__(container)
        
        # Instance state
        self._event_log: List[str] = []
        self._status_label: Optional[QLabel] = None
        self._action_count: int = 0
        self._settings: Dict[str, Any] = {
            "notifications_enabled": True,
            "refresh_interval": 30,
            "show_popups": True,
        }
    
    # =========================================================================
    # TabExtension Interface
    # =========================================================================
    
    def create_widget(self, parent: Optional[QWidget] = None) -> QWidget:
        """Create the widget for this tab."""
        # Pass self so widget can access plugin state/methods
        return ExampleWidget(parent, self)
    
    def on_tab_activated(self) -> None:
        """Called when the tab becomes active."""
        self._log_event("Tab activated")
        self._update_status("Active")
    
    def on_tab_deactivated(self) -> None:
        """Called when the tab becomes inactive."""
        self._log_event("Tab deactivated")
        self._update_status("Ready")
    
    # =========================================================================
    # MenuExtension Interface
    # =========================================================================
    
    def get_menu_items(self) -> List[MenuItemDefinition]:
        """Return menu items to add to the application menu bar."""
        return [
            MenuItemDefinition(
                menu="Tools",
                label="Example Plugin Action",
                callback=self._on_menu_action,
                shortcut="Ctrl+Shift+E",
                separator_before=True,
            ),
            MenuItemDefinition(
                menu="Help",
                label="About Example Plugin",
                callback=self._on_about_action,
            ),
        ]
    
    def _on_menu_action(self) -> None:
        """Handle the custom menu action."""
        self._action_count += 1
        self._log_event(f"Menu action triggered (#{self._action_count})")
        self._update_status(f"Action #{self._action_count}")
        
        if self._settings.get("show_popups", True):
            QMessageBox.information(
                None,
                "Example Plugin",
                f"Menu action triggered!\n\n"
                f"This is action #{self._action_count}.\n"
                f"Check the Example Plugin tab for the event log."
            )
    
    def _on_about_action(self) -> None:
        """Handle the about menu item."""
        self._log_event("About dialog opened")
        QMessageBox.about(
            None,
            "About Example Plugin",
            "<h2>Example Plugin v2.0</h2>"
            "<p>A comprehensive example demonstrating all extension interfaces:</p>"
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
    
    def create_status_widget(self, parent: Optional[QWidget] = None) -> QWidget:
        """Create a widget to display in the status bar."""
        self._status_label = QLabel("Example: Ready", parent)
        self._status_label.setStyleSheet(
            "padding: 2px 8px; "
            "color: #4CAF50; "
            "font-weight: bold;"
        )
        self._status_label.setToolTip("Example Plugin status indicator")
        return self._status_label
    
    def _update_status(self, status: str) -> None:
        """Update the status bar indicator."""
        if self._status_label:
            self._status_label.setText(f"Example: {status}")
    
    # =========================================================================
    # ToolbarExtension Interface
    # =========================================================================
    
    def get_toolbar_actions(self) -> List[ToolbarAction]:
        """Return actions to add to the main toolbar."""
        return [
            ToolbarAction(
                label="Example Plugin",
                callback=self._on_toolbar_action,
                tooltip="Click to trigger Example Plugin action (Ctrl+Shift+E)",
                checkable=False,
            ),
        ]
    
    def _on_toolbar_action(self) -> None:
        """Handle toolbar action."""
        self._action_count += 1
        self._log_event(f"Toolbar action triggered (#{self._action_count})")
        self._update_status(f"Action #{self._action_count}")
        
        if self._settings.get("show_popups", True):
            QMessageBox.information(
                None,
                "Example Plugin",
                f"Toolbar action triggered!\n\n"
                f"This is action #{self._action_count}.\n"
                f"Check the Example Plugin tab for the event log."
            )
    
    # =========================================================================
    # ServiceExtension Interface
    # =========================================================================
    
    def on_application_start(self, container: "ServiceContainer") -> None:
        """Called when the application starts."""
        self._log_event("Application started - service initialized")
        self._log_event("   Container services are now available")
    
    def on_application_shutdown(self) -> None:
        """Called when the application is shutting down."""
        self._log_event("Application shutting down - cleaning up")
        # Could stop background tasks, save state, etc.
    
    # =========================================================================
    # EventSubscriberExtension Interface
    # =========================================================================
    
    def get_event_subscriptions(self) -> Dict[str, Callable]:
        """Return a mapping of event names to callback functions."""
        return {
            "plugin_enabled": self._on_plugin_enabled,
            "plugin_disabled": self._on_plugin_disabled,
            "theme_changed": self._on_theme_changed,
        }
    
    def _on_plugin_enabled(self, event_data: Dict[str, Any]) -> None:
        """Handle plugin_enabled event."""
        plugin_name = event_data.get("plugin_name", "Unknown")
        self._log_event(f"Event: Plugin '{plugin_name}' was enabled")
    
    def _on_plugin_disabled(self, event_data: Dict[str, Any]) -> None:
        """Handle plugin_disabled event."""
        plugin_name = event_data.get("plugin_name", "Unknown")
        self._log_event(f"Event: Plugin '{plugin_name}' was disabled")
    
    def _on_theme_changed(self, event_data: Dict[str, Any]) -> None:
        """Handle theme_changed event."""
        theme = event_data.get("theme", "Unknown")
        self._log_event(f"Event: Theme changed to '{theme}'")
    
    # =========================================================================
    # SettingsExtension Interface
    # =========================================================================
    
    def get_settings_widget(self, parent: Optional[QWidget] = None) -> Optional[QWidget]:
        """Get a settings widget for this plugin."""
        return ExampleSettingsWidget(parent, self._settings)
    
    def on_settings_changed(self, settings_dict: Dict[str, Any]) -> None:
        """Called when plugin settings are changed."""
        self._settings.update(settings_dict)
        self._log_event(f"Settings updated: {settings_dict}")
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _log_event(self, message: str) -> None:
        """Log an event for display in the UI."""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self._event_log.append(f"[{timestamp}] {message}")
        # Keep only last 100 events
        if len(self._event_log) > 100:
            self._event_log = self._event_log[-100:]
            
        # If we have an active widget, update it immediately?
        # Typically the widget pulls via timer, but we could push here if we tracked the widget.
    
    def get_event_log(self) -> List[str]:
        """Get the event log for display."""
        return self._event_log.copy()


class ExampleWidget(QWidget):
    """The actual widget displayed in the tab."""
    
    def __init__(self, parent: Optional[QWidget], plugin: ExampleTabPlugin) -> None:
        """Initialize the widget.
        
        Args:
            parent: Parent widget
            plugin: The plugin instance owning this widget
        """
        super().__init__(parent)
        self.plugin = plugin
        self.setup_ui()
        self._setup_refresh_timer()
        # Log that widget was created
        self.plugin._log_event("Tab widget created")
    
    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        
        # Title label
        title_label = QLabel("Example Plugin v2.0 (Extensions Demo)")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)
        
        # Description
        desc_label = QLabel(
            "This plugin demonstrates all extension interfaces:\n"
            "• TabExtension - This tab you're viewing\n"
            "• MenuExtension - Tools → Example Plugin Action (Ctrl+Shift+E)\n"
            "• StatusExtension - \"Example: Ready\" in status bar\n"
            "• ToolbarExtension - \"Example Plugin\" button in toolbar\n"
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
        # Call plugin method via instance
        self.trigger_btn.clicked.connect(self.plugin._on_menu_action)
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
        events = self.plugin.get_event_log()
        if events:
            # Show newest events at top
            self.event_log.setPlainText("\n".join(reversed(events)))
        else:
            self.event_log.setPlainText(
                "No events logged yet...\n\n"
                "Try these actions to generate events:\n"
                "• Click 'Example Plugin' in the toolbar\n"
                "• Use menu: Tools → Example Plugin Action\n"
                "• Change the theme\n"
                "• Enable/disable other plugins"
            )
    
    def _clear_log(self):
        """Clear the event log."""
        self.plugin._event_log.clear()
        self.plugin._action_count = 0
        self.plugin._log_event("Log cleared by user")
        self._refresh_log()
    
    def _generate_test_event(self):
        """Generate a test event."""
        self.plugin._log_event("⚡ Test event generated by user")
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