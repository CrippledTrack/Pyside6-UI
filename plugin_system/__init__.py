"""
Plugin system for Basic GUI Application

This package contains the plugin system for the Basic GUI Application.

New in v3.4.0: Multiple extension interfaces for flexible plugin architecture.
"""

from .base import BaseTabPlugin, CoreTabPlugin
from .registry import PluginRegistry, plugin_registry
from .interfaces import (
    Plugin,
    TabExtension,
    MenuExtension,
    StatusExtension,
    ToolbarExtension,
    ServiceExtension,
    EventSubscriberExtension,
    SettingsExtension,
)
from .types import MenuItemDefinition, ToolbarAction, PluginEvent

__all__ = [
    # Backward compatible
    "BaseTabPlugin",
    "CoreTabPlugin",
    "PluginRegistry",
    "plugin_registry",
    # New extension interfaces (v3.4.0)
    "Plugin",
    "TabExtension",
    "MenuExtension",
    "StatusExtension",
    "ToolbarExtension",
    "ServiceExtension",
    "EventSubscriberExtension",
    "SettingsExtension",
    # New types (v3.4.0)
    "MenuItemDefinition",
    "ToolbarAction",
    "PluginEvent",
]