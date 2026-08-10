"""
Example plugin for Basic GUI Application.

This demonstrates how to create a comprehensive plugin using all
extension interfaces:
- TabExtension (via BaseTabPlugin) - provides a tab via create_tab_content
- MenuExtension - contributes menu items
- StatusExtension - provides a status bar widget
- ToolbarExtension - contributes toolbar actions
- ServiceExtension - runs background service
- EventSubscriberExtension - subscribes to application events
- SettingsExtension - provides configurable settings

Tab chrome (labels, buttons, log, layout) uses ``GUI.app.ui.definitions``
so the active UI backend supplies the toolkit. Settings still uses raw Qt
widgets (checkbox/spinbox are outside the basic definitions kit).
"""
from __future__ import annotations

from typing import Optional, Dict, List, Any, Callable, TYPE_CHECKING

from ..app.ui.definitions import (
    ButtonRole,
    LabelRole,
    add,
    add_stretch,
    create_button,
    create_column,
    create_label,
    create_row,
    create_text_area,
    on_click,
    on_interval,
    set_text,
)
from ..plugin_system.base import BaseTabPlugin
from ..plugin_system.types import MenuItemDefinition, ToolbarAction, TabContent, TabCreateContext

if TYPE_CHECKING:
    from ..app.services.container import ServiceContainer


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
    supported_platforms = ["Windows", "Linux", "macOS"]
    requires_admin = False
    plugin_version = "2.2.0"
    plugin_author = "Example Author"
    plugin_authors = ["Example Author", "Contributors"]
    min_gui_version = "6.0.0"
    required_gui_version = ">=6.0.0"
    disabled_by_default = True

    # Dependencies on other plugins
    dependencies: List[str] = []

    def __init__(self, container: "ServiceContainer") -> None:
        """Initialize the plugin instance."""
        super().__init__(container)

        # Instance state
        self._event_log: List[str] = []
        self._status_label: Any = None
        self._action_count: int = 0
        self._tab_log: Any = None
        self._refresh_timer: Any = None
        self._settings: Dict[str, Any] = {
            "notifications_enabled": True,
            "refresh_interval": 30,
            "show_popups": True,
        }

    # =========================================================================
    # TabExtension Interface
    # =========================================================================

    def create_tab_content(self, context: TabCreateContext) -> TabContent:
        """Create tab content via shared UI definitions (backend-auto-dispatch)."""
        root = create_column(parent=context.parent)

        add(
            root,
            create_label(
                "Example Plugin v2.2 (Extensions Demo)",
                role=LabelRole.HEADING,
            ),
        )
        add(
            root,
            create_label(
                "This plugin demonstrates all extension interfaces:\n"
                "• TabExtension - create_tab_content via GUI.app.ui.definitions\n"
                "• MenuExtension - Tools → Example Plugin Action (Ctrl+Shift+E)\n"
                "• StatusExtension - \"Example: Ready\" in status bar\n"
                "• ToolbarExtension - \"Example Plugin\" button in toolbar\n"
                "• ServiceExtension - Background service lifecycle\n"
                "• EventSubscriberExtension - Responds to plugin/theme events\n"
                "• SettingsExtension - Configurable settings",
                role=LabelRole.BODY,
            ),
        )

        add(
            root,
            create_label(
                "Event Log (auto-refreshes every 1 second):",
                role=LabelRole.FIELD,
            ),
        )
        self._tab_log = create_text_area(read_only=True, expand=True)
        add(root, self._tab_log)

        row = create_row()
        refresh_btn = create_button("Refresh Log", role=ButtonRole.DEFAULT)
        clear_btn = create_button("Clear Log", role=ButtonRole.DEFAULT)
        test_btn = create_button("Generate Test Event", role=ButtonRole.DEFAULT)
        trigger_btn = create_button("Trigger Menu Action", role=ButtonRole.DEFAULT)
        add(row, refresh_btn)
        add(row, clear_btn)
        add(row, test_btn)
        add(row, trigger_btn)
        add(root, row)

        on_click(refresh_btn, self._refresh_log)
        on_click(clear_btn, self._clear_log)
        on_click(test_btn, self._generate_test_event)
        on_click(trigger_btn, self._on_menu_action)

        add_stretch(root)

        self._refresh_timer = on_interval(self._refresh_log, 1000, parent=root)
        self._log_event("Tab content created via create_tab_content (definitions)")
        self._refresh_log()
        return root

    def _refresh_log(self) -> None:
        """Refresh the event log display."""
        if self._tab_log is None:
            return
        events = self.get_event_log()
        if events:
            set_text(self._tab_log, "\n".join(reversed(events)))
        else:
            set_text(
                self._tab_log,
                "No events logged yet...\n\n"
                "Try these actions to generate events:\n"
                "• Click 'Example Plugin' in the toolbar\n"
                "• Use menu: Tools → Example Plugin Action\n"
                "• Change the theme\n"
                "• Enable/disable other plugins",
            )

    def _clear_log(self) -> None:
        """Clear the event log."""
        self._event_log.clear()
        self._action_count = 0
        self._log_event("Log cleared by user")
        self._refresh_log()

    def _generate_test_event(self) -> None:
        """Generate a test event."""
        self._log_event("Test event generated by user")
        self._refresh_log()

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
        self._refresh_log()

        if self._settings.get("show_popups", True):
            self._show_info(
                "Example Plugin",
                f"Menu action triggered!\n\n"
                f"This is action #{self._action_count}.\n"
                f"Check the Example Plugin tab for the event log.",
            )

    def _on_about_action(self) -> None:
        """Handle the about menu item."""
        self._log_event("About dialog opened")
        self._refresh_log()
        self._show_info(
            "About Example Plugin",
            "Example Plugin v2.2\n\n"
            "Demonstrates all extension interfaces:\n"
            "- TabExtension (definitions facade)\n"
            "- MenuExtension\n"
            "- StatusExtension\n"
            "- ToolbarExtension\n"
            "- ServiceExtension\n"
            "- EventSubscriberExtension\n"
            "- SettingsExtension",
        )

    def _show_info(self, title: str, message: str) -> None:
        """Show an info dialog; uses Qt MessageBox as an escape hatch."""
        try:
            from ..app.ui.qt.bindings import QMessageBox
        except ImportError:
            return
        QMessageBox.information(None, title, message)

    # =========================================================================
    # StatusExtension Interface
    # =========================================================================

    def create_status_widget(self, parent: Optional[Any] = None) -> TabContent:
        """Create content to display in the status bar."""
        self._status_label = create_label(
            "Example: Ready",
            role=LabelRole.SUCCESS,
            parent=parent,
        )
        return self._status_label

    def _update_status(self, status: str) -> None:
        """Update the status bar indicator."""
        if self._status_label is not None:
            set_text(self._status_label, f"Example: {status}")

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
        self._refresh_log()

        if self._settings.get("show_popups", True):
            self._show_info(
                "Example Plugin",
                f"Toolbar action triggered!\n\n"
                f"This is action #{self._action_count}.\n"
                f"Check the Example Plugin tab for the event log.",
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
        self._refresh_log()

    def _on_plugin_disabled(self, event_data: Dict[str, Any]) -> None:
        """Handle plugin_disabled event."""
        plugin_name = event_data.get("plugin_name", "Unknown")
        self._log_event(f"Event: Plugin '{plugin_name}' was disabled")
        self._refresh_log()

    def _on_theme_changed(self, event_data: Dict[str, Any]) -> None:
        """Handle theme_changed event."""
        theme = event_data.get("theme", "Unknown")
        self._log_event(f"Event: Theme changed to '{theme}'")
        self._refresh_log()

    # =========================================================================
    # SettingsExtension Interface
    # =========================================================================

    def get_settings_widget(self, parent: Optional[Any] = None) -> Optional[TabContent]:
        """Get settings content for this plugin (raw Qt — form controls not in defs yet)."""
        return ExampleSettingsWidget(parent, self._settings)

    def on_settings_changed(self, settings_dict: Dict[str, Any]) -> None:
        """Called when plugin settings are changed."""
        self._settings.update(settings_dict)
        self._log_event(f"Settings updated: {settings_dict}")
        self._refresh_log()

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _log_event(self, message: str) -> None:
        """Log an event for display in the UI."""
        import datetime

        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self._event_log.append(f"[{timestamp}] {message}")
        if len(self._event_log) > 100:
            self._event_log = self._event_log[-100:]

    def get_event_log(self) -> List[str]:
        """Get the event log for display."""
        return self._event_log.copy()


def ExampleSettingsWidget(parent: Optional[Any] = None, settings: Dict[str, Any] | None = None) -> Any:
    """Build the example settings form (raw Qt escape hatch).

    Returns a ``QWidget`` with ``get_settings()`` for the plugin dialog host.
    """
    from ..app.ui.qt.bindings import QCheckBox, QFormLayout, QSpinBox, QWidget

    class _SettingsWidget(QWidget):
        def __init__(self, parent: Optional[Any] = None, settings: Dict[str, Any] | None = None) -> None:
            super().__init__(parent)
            self.settings = settings or {}
            layout = QFormLayout(self)

            self.notifications_cb = QCheckBox()
            self.notifications_cb.setChecked(self.settings.get("notifications_enabled", True))
            layout.addRow("Enable Notifications:", self.notifications_cb)

            self.popups_cb = QCheckBox()
            self.popups_cb.setChecked(self.settings.get("show_popups", True))
            layout.addRow("Show Action Popups:", self.popups_cb)

            self.refresh_spin = QSpinBox()
            self.refresh_spin.setRange(5, 300)
            self.refresh_spin.setSuffix(" seconds")
            self.refresh_spin.setValue(self.settings.get("refresh_interval", 30))
            layout.addRow("Refresh Interval:", self.refresh_spin)

        def get_settings(self) -> Dict[str, Any]:
            return {
                "notifications_enabled": self.notifications_cb.isChecked(),
                "show_popups": self.popups_cb.isChecked(),
                "refresh_interval": self.refresh_spin.value(),
            }

    return _SettingsWidget(parent, settings)


__all__ = ["ExampleTabPlugin"]
