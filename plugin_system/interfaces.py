"""
Plugin extension interfaces for the CyberPatriot-Scripts GUI.

This module defines abstract base classes for each extension point that plugins
can implement. Plugins can implement any combination of these interfaces.

All interfaces are optional - plugins only need to implement the ones they use.
Backward compatibility: existing plugins using BaseTabPlugin continue to work.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .types import MenuItemDefinition, ToolbarAction


class Plugin(ABC):
    """Base class for all plugins.
    
    This provides common metadata that all plugins should have.
    Plugins don't inherit from this directly - they implement one or more
    of the extension interfaces below.
    """
    
    # Required metadata
    plugin_name: str = "Unnamed Plugin"
    plugin_description: str = "No description provided"
    plugin_version: str = "1.0.0"
    plugin_author: str = "Unknown"
    plugin_authors: List[str] = []  # Optional list of authors
    
    # Platform support
    supported_platforms: List[str] = ["Windows", "Linux"]
    
    # Optional: dependencies on other plugins (by plugin_name)
    dependencies: List[str] = []
    
    # If True, the plugin will be disabled by default on first discovery
    disabled_by_default: bool = False
    
    # Version requirements (optional)
    min_gui_version: Optional[str] = None
    required_gui_version: Optional[str] = None
    
    @classmethod
    def get_plugin_info(cls) -> Dict[str, Any]:
        """Get comprehensive information about this plugin."""
        authors_list: List[str] = []
        try:
            if isinstance(getattr(cls, 'plugin_authors', []), list) and getattr(cls, 'plugin_authors'):
                authors_list = [str(a) for a in getattr(cls, 'plugin_authors') if a]
        except Exception:
            authors_list = []
        if not authors_list and getattr(cls, 'plugin_author', None):
            authors_list = [str(getattr(cls, 'plugin_author'))]

        author_text = ", ".join(authors_list) if authors_list else str(getattr(cls, 'plugin_author', 'Unknown'))

        return {
            'name': getattr(cls, 'plugin_name', cls.__name__),
            'description': cls.plugin_description,
            'supported_platforms': cls.supported_platforms,
            'version': cls.plugin_version,
            'author': author_text,
            'authors': authors_list,
            'dependencies': getattr(cls, 'dependencies', []),
            'min_gui_version': getattr(cls, 'min_gui_version', None),
            'required_gui_version': getattr(cls, 'required_gui_version', None)
        }


class TabExtension(ABC):
    """Interface for plugins that provide a tab widget.
    
    This is the primary extension point and corresponds to the existing
    BaseTabPlugin functionality.
    """
    
    # Tab-specific metadata
    tab_name: str = "Unnamed Tab"
    tab_description: str = "No description provided"
    requires_admin: bool = False
    
    @classmethod
    @abstractmethod
    def create_widget(cls, parent: Optional[Any] = None) -> Any:
        """Create and return a UI widget to be used as the tab's content.
        
        Args:
            parent: The parent widget (e.g., QTabWidget for PySide6)
            
        Returns:
            A UI widget appropriate for the framework being used
        """
        pass
    
    @classmethod
    def on_tab_activated(cls, widget: Any) -> None:
        """Called when the tab becomes active. Optional override."""
        pass
    
    @classmethod
    def on_tab_deactivated(cls, widget: Any) -> None:
        """Called when the tab becomes inactive. Optional override."""
        pass


class MenuExtension(ABC):
    """Interface for plugins that contribute menu items to the main menu bar."""
    
    @classmethod
    @abstractmethod
    def get_menu_items(cls) -> List["MenuItemDefinition"]:
        """Return a list of menu items to add to the application menu bar.
        
        Returns:
            List of MenuItemDefinition objects specifying menu, label, callback, etc.
        """
        pass


class StatusExtension(ABC):
    """Interface for plugins that contribute widgets to the status bar."""
    
    @classmethod
    @abstractmethod
    def create_status_widget(cls, parent: Optional[Any] = None) -> Any:
        """Create and return a widget to display in the status bar.
        
        Args:
            parent: The parent widget (status bar)
            
        Returns:
            A UI widget to embed in the status bar
        """
        pass


class ToolbarExtension(ABC):
    """Interface for plugins that contribute actions to the main toolbar."""
    
    @classmethod
    @abstractmethod
    def get_toolbar_actions(cls) -> List["ToolbarAction"]:
        """Return a list of actions to add to the main toolbar.
        
        Returns:
            List of ToolbarAction objects
        """
        pass


class ServiceExtension(ABC):
    """Interface for plugins that provide background services with no UI.
    
    These plugins are initialized when the application starts and cleaned up
    when it shuts down. They can perform background tasks, monitoring, etc.
    """
    
    @classmethod
    def on_application_start(cls, container: Any) -> None:
        """Called when the application starts.
        
        Args:
            container: The ServiceContainer for accessing other services
        """
        pass
    
    @classmethod
    def on_application_shutdown(cls) -> None:
        """Called when the application is shutting down."""
        pass


class EventSubscriberExtension(ABC):
    """Interface for plugins that subscribe to application events.
    
    This enables cross-plugin communication via a publish/subscribe pattern.
    """
    
    @classmethod
    @abstractmethod
    def get_event_subscriptions(cls) -> Dict[str, Callable]:
        """Return a mapping of event names to callback functions.
        
        Returns:
            Dict mapping event name strings to callback functions
        """
        pass


class SettingsExtension(ABC):
    """Interface for plugins that have configurable settings."""
    
    @classmethod
    def get_settings_widget(cls, parent: Optional[Any] = None) -> Optional[Any]:
        """Get a settings widget for this plugin.
        
        Args:
            parent: Parent widget for the settings widget
            
        Returns:
            A widget containing settings controls, or None
        """
        return None
    
    @classmethod
    def on_settings_changed(cls, settings_dict: Dict[str, Any]) -> None:
        """Called when plugin settings are changed."""
        pass


__all__ = [
    'Plugin',
    'TabExtension',
    'MenuExtension',
    'StatusExtension',
    'ToolbarExtension',
    'ServiceExtension',
    'EventSubscriberExtension',
    'SettingsExtension',
]
