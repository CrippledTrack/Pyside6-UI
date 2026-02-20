"""
Plugin extension interfaces for the Basic UI Application.

This module defines Protocol-based interfaces for each extension point that plugins
can implement. Plugins can implement any combination of these interfaces.

v4.0.0 BREAKING CHANGES:
- All interfaces now use typing.Protocol instead of ABC
- Methods are instance-based (use `self`) instead of classmethods
- Removed `tab_name` aliasing - use `plugin_name` and `tab_title`
- `create_widget` now typed to return QWidget

Legacy 3.x plugins can use LegacyPluginAdapter from compatibility.py.
"""

from __future__ import annotations

from typing import (
    Any, Callable, Dict, List, Optional, 
    Protocol, runtime_checkable, TYPE_CHECKING
)

if TYPE_CHECKING:
    from ..app.qt_bindings import QWidget
    from .types import MenuItemDefinition, ToolbarAction
    from ..app.services.container import ServiceContainer


@runtime_checkable
class PluginProtocol(Protocol):
    """Base protocol all plugins must satisfy.
    
    This is checked at runtime using isinstance() to determine if a class
    is a valid plugin.
    """
    
    # Required metadata (class-level)
    plugin_name: str
    plugin_version: str
    supported_platforms: List[str]
    
    # Optional metadata with defaults
    plugin_description: str
    plugin_author: str
    plugin_authors: List[str]
    dependencies: List[str]
    disabled_by_default: bool
    min_gui_version: Optional[str]
    required_gui_version: Optional[str]


@runtime_checkable
class TabExtension(Protocol):
    """Interface for plugins that provide a tab widget.
    
    This is the primary extension point for adding new tabs to the application.
    
    Attributes:
        plugin_name: Unique identifier for the plugin
        tab_title: Display name shown in the tab bar
        requires_admin: Whether admin privileges are needed
    """
    
    plugin_name: str
    tab_title: str
    requires_admin: bool
    
    def create_widget(self, parent: Optional["QWidget"] = None) -> "QWidget":
        """Create and return a UI widget to be used as the tab's content.
        
        Args:
            parent: The parent widget (e.g., QTabWidget for PySide6)
            
        Returns:
            A QWidget instance for the tab content
        """
        ...
    
    def on_tab_activated(self) -> None:
        """Called when the tab becomes active. Optional override."""
        ...
    
    def on_tab_deactivated(self) -> None:
        """Called when the tab becomes inactive. Optional override."""
        ...


@runtime_checkable
class MenuExtension(Protocol):
    """Interface for plugins that contribute menu items to the main menu bar."""
    
    plugin_name: str
    
    def get_menu_items(self) -> List["MenuItemDefinition"]:
        """Return a list of menu items to add to the application menu bar.
        
        Returns:
            List of MenuItemDefinition objects specifying menu, label, callback, etc.
        """
        ...


@runtime_checkable
class StatusExtension(Protocol):
    """Interface for plugins that contribute widgets to the status bar."""
    
    plugin_name: str
    
    def create_status_widget(self, parent: Optional["QWidget"] = None) -> "QWidget":
        """Create and return a widget to display in the status bar.
        
        Args:
            parent: The parent widget (status bar)
            
        Returns:
            A UI widget to embed in the status bar
        """
        ...


@runtime_checkable
class ToolbarExtension(Protocol):
    """Interface for plugins that contribute actions to the main toolbar."""
    
    plugin_name: str
    
    def get_toolbar_actions(self) -> List["ToolbarAction"]:
        """Return a list of actions to add to the main toolbar.
        
        Returns:
            List of ToolbarAction objects
        """
        ...


@runtime_checkable
class ServiceExtension(Protocol):
    """Interface for plugins that provide background services with no UI.
    
    These plugins are initialized when the application starts and cleaned up
    when it shuts down. They can perform background tasks, monitoring, etc.
    """
    
    plugin_name: str
    
    def on_application_start(self, container: "ServiceContainer") -> None:
        """Called when the application starts.
        
        Args:
            container: The ServiceContainer for accessing other services
        """
        ...
    
    def on_application_shutdown(self) -> None:
        """Called when the application is shutting down."""
        ...


@runtime_checkable
class EventSubscriberExtension(Protocol):
    """Interface for plugins that subscribe to application events.
    
    This enables cross-plugin communication via a publish/subscribe pattern.
    """
    
    plugin_name: str
    
    def get_event_subscriptions(self) -> Dict[str, Callable[..., None]]:
        """Return a mapping of event names to callback functions.
        
        Returns:
            Dict mapping event name strings to callback functions
        """
        ...


@runtime_checkable  
class SettingsExtension(Protocol):
    """Interface for plugins that have configurable settings."""
    
    plugin_name: str
    
    def get_settings_widget(self, parent: Optional["QWidget"] = None) -> Optional["QWidget"]:
        """Get a settings widget for this plugin.
        
        Args:
            parent: Parent widget for the settings widget
            
        Returns:
            A widget containing settings controls, or None
        """
        ...
    
    def on_settings_changed(self, settings_dict: Dict[str, Any]) -> None:
        """Called when plugin settings are changed."""
        ...


from .compatibility import Plugin  # Legacy ABC kept in compatibility module


__all__ = [
    # New Protocol interfaces (v4.0.0)
    'PluginProtocol',
    'TabExtension',
    'MenuExtension',
    'StatusExtension',
    'ToolbarExtension',
    'ServiceExtension',
    'EventSubscriberExtension',
    'SettingsExtension',
    # Legacy (for 3.x compatibility)
    'Plugin',
]
