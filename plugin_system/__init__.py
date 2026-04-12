"""
Plugin system for Basic UI Application
"""

from .base import BaseTabPlugin, CoreTabPlugin
from .registry import PluginRegistry, plugin_registry
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
from .types import MenuItemDefinition, ToolbarAction, PluginEvent

__all__ = [
    # Base classes
    "BaseTabPlugin",
    "CoreTabPlugin",
    # Registry
    "PluginRegistry",
    "plugin_registry",
    # Protocol interfaces
    "PluginProtocol",
    "TabExtension",
    "MenuExtension",
    "StatusExtension",
    "ToolbarExtension",
    "ServiceExtension",
    "EventSubscriberExtension",
    "SettingsExtension",
    # Types
    "MenuItemDefinition",
    "ToolbarAction",
    "PluginEvent",
]