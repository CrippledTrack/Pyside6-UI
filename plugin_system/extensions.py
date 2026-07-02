"""
Central registry of plugin extension points.
"""

from __future__ import annotations

import inspect
from typing import Type, List, Optional, Callable

from .interfaces import (
    PluginProtocol,
    TabExtension,
    MenuExtension,
    StatusExtension,
    ToolbarExtension,
    ServiceExtension,
    EventSubscriberExtension,
    SettingsExtension,
)


class ExtensionPoint:
    """Descriptor for a plugin extension point."""

    def __init__(
        self,
        name: str,
        interface: Type,
        required_methods: List[str],
        required_attrs: Optional[List[str]] = None,
        is_user_toggleable: bool = True,
        parent_toggle: Optional[str] = None,
        custom_validator: Optional[Callable[[Type], bool]] = None,
    ) -> None:
        self.name = name
        self.interface = interface
        self.required_methods = required_methods
        self.required_attrs = required_attrs or []
        self.is_user_toggleable = is_user_toggleable
        self.parent_toggle = parent_toggle
        self.custom_validator = custom_validator

    def check_implements(self, plugin_class: Type) -> bool:
        """Check if a plugin class implements this extension point."""
        if self.custom_validator:
            try:
                return self.custom_validator(plugin_class)
            except Exception:
                return False

        # Default structural check
        for method in self.required_methods:
            try:
                member = inspect.getattr_static(plugin_class, method)
            except Exception:
                return False
            if member is None or not callable(getattr(plugin_class, method, None)):
                return False

        for attr in self.required_attrs:
            if not hasattr(plugin_class, attr):
                return False

        return True


def _validate_settings_extension(plugin_class: Type) -> bool:
    """Validate that SettingsExtension is actually implemented (overridden)."""
    try:
        from .base import BaseTabPlugin
        method = inspect.getattr_static(plugin_class, "get_settings_widget")
        base_method = getattr(BaseTabPlugin, "get_settings_widget", None)
        if getattr(plugin_class, "get_settings_widget", None) is base_method:
            return False
        return method is not None and callable(getattr(plugin_class, "get_settings_widget", None))
    except Exception:
        return False


# Global list of registered plugin extension points
EXTENSION_POINTS = [
    ExtensionPoint(
        name="Tab",
        interface=TabExtension,
        required_methods=["create_widget"],
    ),
    ExtensionPoint(
        name="Menu",
        interface=MenuExtension,
        required_methods=["get_menu_items"],
    ),
    ExtensionPoint(
        name="Status",
        interface=StatusExtension,
        required_methods=["create_status_widget"],
    ),
    ExtensionPoint(
        name="Toolbar",
        interface=ToolbarExtension,
        required_methods=["get_toolbar_actions"],
    ),
    ExtensionPoint(
        name="Service",
        interface=ServiceExtension,
        required_methods=["on_application_start"],
    ),
    ExtensionPoint(
        name="Events",
        interface=EventSubscriberExtension,
        required_methods=["get_event_subscriptions"],
        is_user_toggleable=False,
        parent_toggle="Service",
    ),
    ExtensionPoint(
        name="Settings",
        interface=SettingsExtension,
        required_methods=["get_settings_widget"],
        is_user_toggleable=False,
        custom_validator=_validate_settings_extension,
    ),
    ExtensionPoint(
        name="PluginProtocol",
        interface=PluginProtocol,
        required_methods=[],
        required_attrs=["plugin_name", "supported_platforms"],
        is_user_toggleable=False,
    ),
]


def get_extension_point(name: str) -> Optional[ExtensionPoint]:
    """Retrieve an extension point by its name."""
    for ep in EXTENSION_POINTS:
        if ep.name == name:
            return ep
    return None


def get_extension_point_by_interface(interface: Type) -> Optional[ExtensionPoint]:
    """Retrieve an extension point by its Protocol interface class."""
    for ep in EXTENSION_POINTS:
        if ep.interface is interface:
            return ep
    return None


__all__ = [
    "ExtensionPoint",
    "EXTENSION_POINTS",
    "get_extension_point",
    "get_extension_point_by_interface",
]
