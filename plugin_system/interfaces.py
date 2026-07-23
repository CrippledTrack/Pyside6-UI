"""
Plugin extension interfaces for the Basic UI Application.

This module defines Protocol-based interfaces for each extension point that plugins
can implement. Plugins can implement any combination of these interfaces.
"""

from __future__ import annotations

from typing import (
    Any, Callable, Dict, List, Optional,
    Protocol, runtime_checkable, TYPE_CHECKING,
    Type, TypeVar
)

if TYPE_CHECKING:
    from .types import MenuItemDefinition, ToolbarAction, TabContent, TabCreateContext
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
    """Interface for plugins that provide tab content.
    
    Prefer ``create_tab_content`` for new plugins. ``create_widget`` remains
    supported as a legacy Qt-oriented entry point; hosts may accept either.
    
    Attributes:
        plugin_name: Unique identifier for the plugin
        tab_title: Display name shown in the tab bar
        requires_admin: Whether admin privileges are needed
    """
    
    plugin_name: str
    tab_title: str
    requires_admin: bool
    
    def create_tab_content(self, context: "TabCreateContext") -> "TabContent":
        """Create and return tab content for the active UI backend.
        
        Args:
            context: Backend id and parent handle for content creation
            
        Returns:
            Opaque content understood by the active UI backend
        """
        ...
    
    def create_widget(self, parent: Optional[Any] = None) -> "TabContent":
        """Legacy entry point: create tab content with a parent handle.
        
        Qt hosts historically passed a QWidget parent. New plugins should
        implement ``create_tab_content`` instead.
        
        Args:
            parent: Backend-specific parent handle (may be ``None``)
            
        Returns:
            Opaque tab content for the active UI backend
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
    """Interface for plugins that contribute content to the status bar."""
    
    plugin_name: str
    
    def create_status_widget(self, parent: Optional[Any] = None) -> "TabContent":
        """Create and return content to display in the status bar.
        
        Args:
            parent: Backend-specific parent handle (status bar)
            
        Returns:
            Opaque content to embed in the status bar
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
    
    def get_settings_widget(self, parent: Optional[Any] = None) -> Optional["TabContent"]:
        """Get settings content for this plugin.
        
        Args:
            parent: Backend-specific parent handle
            
        Returns:
            Opaque settings content, or None
        """
        ...
    
    def on_settings_changed(self, settings_dict: Dict[str, Any]) -> None:
        """Called when plugin settings are changed."""
        ...


T = TypeVar('T')


@runtime_checkable
class IServiceContainer(Protocol):
    """Protocol for the service container to decouple plugin system from app services."""
    
    def get(self, service_type: Type[T]) -> T:
        """Retrieve a service instance by its class or interface type."""
        ...


@runtime_checkable
class ISettingsService(Protocol):
    """Canonical settings service Protocol (app + plugin_system).

    Defined here so ``plugin_system`` does not import ``app.services``.
    The concrete implementation lives in ``app.services.settings_service``.
    """

    def get_settings(self) -> Any:
        """Get current settings object."""
        ...

    def save_theme_preference(self, theme_name: str) -> None:
        """Save theme preference."""
        ...

    def get_theme_preference(self) -> str:
        """Get saved theme preference."""
        ...

    def save_disabled_plugins(self, plugin_names: List[str]) -> None:
        """Save user-disabled plugin names."""
        ...

    def get_disabled_plugins(self) -> List[str]:
        """Get saved user-disabled plugin names."""
        ...

    def save_window_geometry(self, x: int, y: int, width: int, height: int) -> None:
        """Save window geometry."""
        ...

    def get_window_geometry(self) -> Any:
        """Get saved window geometry."""
        ...

    def get_show_tooltips(self) -> bool:
        """Get show tooltips setting."""
        ...

    def save_shortcuts_enabled(self, enabled: bool) -> None:
        """Save shortcuts enabled setting."""
        ...

    def get_shortcuts_enabled(self) -> bool:
        """Get shortcuts enabled setting."""
        ...

    def save_toast_settings(self, enabled: bool, duration: int) -> None:
        """Save toast notification settings."""
        ...

    def get_toast_notifications_enabled(self) -> bool:
        """Get toast notifications enabled setting."""
        ...

    def get_toast_duration(self) -> int:
        """Get toast duration setting."""
        ...

    def save_new_ui_enabled(self, enabled: bool) -> None:
        """Save whether the modern (non-classic) UI is enabled."""
        ...

    def get_new_ui_enabled(self) -> bool:
        """Return whether the modern (non-classic) UI is enabled."""
        ...

    def save_gui_version(self, version: str) -> None:
        """Save GUI version to settings."""
        ...

    def get_gui_version(self) -> str:
        """Get saved GUI version."""
        ...

    def save_plugin_settings(self, plugin_name: str, settings: Dict[str, Any]) -> None:
        """Save settings for a specific plugin."""
        ...

    def get_plugin_settings(self, plugin_name: str) -> Dict[str, Any]:
        """Get settings for a specific plugin."""
        ...

    def is_extension_enabled(self, plugin_name: str, extension_type: str) -> bool:
        """Check if a specific extension type is enabled for a plugin."""
        ...


@runtime_checkable
class IPluginLifecycle(Protocol):
    """Toolkit-neutral plugin lifecycle events."""

    def on_plugins_unloaded(self, plugin_names: List[str]) -> None:
        """Called when plugin instances are unloaded and resources cleaned up."""
        ...

    def on_plugins_discovered(self, plugin_names: List[str]) -> None:
        """Called when new plugins are discovered and registered."""
        ...

    def on_plugin_state_changed(self, plugin_name: str, enabled: bool) -> None:
        """Called when a plugin is enabled or disabled."""
        ...


@runtime_checkable
class IPluginResourceCleanup(Protocol):
    """Backend-registered cleanup for plugin-owned UI resources."""

    def cleanup(self, plugin: Any) -> None:
        """Release backend-specific resources held by a plugin instance."""
        ...


__all__ = [
    # Protocol interfaces
    'PluginProtocol',
    'TabExtension',
    'MenuExtension',
    'StatusExtension',
    'ToolbarExtension',
    'ServiceExtension',
    'EventSubscriberExtension',
    'SettingsExtension',
    'IServiceContainer',
    'ISettingsService',
    'IPluginLifecycle',
    'IPluginResourceCleanup',
]
