"""
Plugin system for Basic UI Application

v4.0.0 BREAKING CHANGES:
- Instance-based plugins with ServiceContainer injection
- Protocol-based interfaces (duck typing support)
- Use plugin_name + tab_title instead of tab_name
- LegacyPluginAdapter for 3.x compatibility
"""

from .base import BaseTabPlugin, CoreTabPlugin, LegacyBaseTabPlugin
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
    Plugin,  # Legacy ABC
)
from .types import MenuItemDefinition, ToolbarAction, PluginEvent
from .migration import LegacyPluginAdapter, wrap_legacy_plugin

__all__ = [
    # v4.0.0 base classes
    "BaseTabPlugin",
    "CoreTabPlugin",
    # Registry
    "PluginRegistry",
    "plugin_registry",
    # Protocol interfaces (v4.0.0)
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
    # Migration utilities
    "LegacyPluginAdapter",
    "wrap_legacy_plugin",
    # Legacy (for 3.x compatibility)
    "LegacyBaseTabPlugin",
    "Plugin",
]