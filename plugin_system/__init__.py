"""
Plugin system for Basic UI Application
"""

from .base import BaseTabPlugin, CoreTabPlugin
from .registry import PluginRegistry
from .interfaces import (
    PluginProtocol,
    TabExtension,
    MenuExtension,
    StatusExtension,
    ToolbarExtension,
    ServiceExtension,
    EventSubscriberExtension,
    SettingsExtension,
    IPluginLifecycle,
    IPluginResourceCleanup,
)
from .types import MenuItemDefinition, ToolbarAction, PluginEvent, TabContent, TabCreateContext
from .tab_content import resolve_tab_content, supports_tab_on_backend
from .extensions import (
    ExtensionPoint,
    EXTENSION_POINTS,
    get_extension_point,
    get_extension_point_by_interface,
)
from .decorators import ui_thread

__all__ = [
    # Base classes
    "BaseTabPlugin",
    "CoreTabPlugin",
    # Registry
    "PluginRegistry",
    # Protocol interfaces
    "PluginProtocol",
    "TabExtension",
    "MenuExtension",
    "StatusExtension",
    "ToolbarExtension",
    "ServiceExtension",
    "EventSubscriberExtension",
    "SettingsExtension",
    "IPluginLifecycle",
    "IPluginResourceCleanup",
    # Types
    "MenuItemDefinition",
    "ToolbarAction",
    "PluginEvent",
    "TabContent",
    "TabCreateContext",
    # Tab content helpers
    "resolve_tab_content",
    "supports_tab_on_backend",
    # Extensions Registry
    "ExtensionPoint",
    "EXTENSION_POINTS",
    "get_extension_point",
    "get_extension_point_by_interface",
    # Decorators
    "ui_thread",
]
