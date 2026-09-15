"""Main window shell abstraction."""

from __future__ import annotations

from typing import Any, List, Optional, Protocol, Type, TYPE_CHECKING

from .types import (
    MenuItemHandle,
    MenuItemSpec,
    StatusWidgetHandle,
    ToolbarActionHandle,
    ToolbarActionSpec,
    ToastType,
)

if TYPE_CHECKING:
    from ...services.notification_service import Notification


class IMainWindowShell(Protocol):
    """Protocol for main window shell operations without toolkit types.

    This is the primary host contract for UI backends. Tab-only consumers may
    use ``IPluginTabHost``, which is a structural subset of these tab methods.
    """

    def add_menu_item(self, spec: MenuItemSpec) -> MenuItemHandle:
        """Add a menu item; return an opaque handle."""
        ...

    def remove_menu_item(self, handle: MenuItemHandle) -> None:
        """Remove a menu item by handle."""
        ...

    def remove_menu_if_empty(self, menu_title: str) -> None:
        """Remove a top-level menu if it has no actions."""
        ...

    def add_status_widget_for_plugin(self, plugin_name: str, plugin_instance: Any) -> StatusWidgetHandle:
        """Create and add a status widget for a plugin."""
        ...

    def remove_status_widget(self, handle: StatusWidgetHandle) -> None:
        """Remove a status widget by handle."""
        ...

    def add_toolbar_action(self, spec: ToolbarActionSpec) -> ToolbarActionHandle:
        """Add a toolbar action; return an opaque handle."""
        ...

    def remove_toolbar_action(self, handle: ToolbarActionHandle) -> None:
        """Remove a toolbar action by handle."""
        ...

    def has_plugin_tab(self, plugin_name: str) -> bool:
        """Check if a plugin tab is currently loaded."""
        ...

    def add_plugin_tab(self, plugin_name: str, plugin_class: Type) -> None:
        """Add a tab for a plugin."""
        ...

    def remove_plugin_tab(self, plugin_name: str) -> None:
        """Remove a tab for a plugin."""
        ...

    def clear_tabs_for_plugins(self, plugin_names: List[str]) -> None:
        """Remove tabs and clear stale references for unloaded plugins."""
        ...

    def reload_plugins(self) -> None:
        """Rediscover plugins and rebuild tabs/extensions from a clean state."""
        ...

    def show_status(self, message: str, timeout: int = 0) -> None:
        """Show a message in the shell status area."""
        ...

    def clear_status(self) -> None:
        """Clear the shell status area."""
        ...

    def show_toast(
        self,
        message: str,
        notification_type: ToastType = ToastType.INFO,
        duration: Optional[int] = None,
    ) -> None:
        """Show a transient toast notification."""
        ...

    def on_notification_added(self, notification: "Notification") -> None:
        """Handle a new notification (toast + notification center)."""
        ...

    def on_unread_count_changed(self, count: int) -> None:
        """Update notification center unread badge."""
        ...


__all__ = ['IMainWindowShell']
