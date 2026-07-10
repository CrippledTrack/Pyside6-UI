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
    """Protocol for main window shell operations without toolkit types."""

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
