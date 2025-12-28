"""
Base plugin interface for Basic GUI Application tabs.

All tab plugins must inherit from BaseTabPlugin.

This module provides backward-compatible base classes that implement the
new extension interfaces defined in interfaces.py. Existing plugins using
BaseTabPlugin will continue to work without modification.
"""
from __future__ import annotations

import platform
import re
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Type

# Import new extension interfaces
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


class BaseTabPlugin(Plugin, TabExtension, ABC):
    """
    Base class for all tab plugins in the Basic GUI Application.
    
    All tab plugins must inherit from this class and implement the required methods.
    
    This class combines the Plugin (metadata) and TabExtension (tab widget)
    interfaces for backward compatibility with existing plugins.
    
    New plugins can choose to implement individual interfaces directly if they
    don't need a tab (e.g., MenuExtension only, or ServiceExtension only).
    """
    
    # Required class attributes (backward compatible with existing plugins)
    tab_name: str = "Unnamed Tab"
    tab_description: str = "No description provided"
    supported_platforms: List[str] = ["Windows", "Linux"]  # Platforms this plugin supports
    requires_admin: bool = False  # Whether this plugin requires admin privileges
    plugin_version: str = "1.0.0"
    plugin_author: str = "Unknown"
    plugin_authors: List[str] = []  # Optional list of authors; if provided, overrides plugin_author
    # If True, the plugin will be disabled by default on first discovery (can be enabled by user)
    disabled_by_default: bool = False
    
    # Plugin dependencies (new in v3.4.0, optional)
    dependencies: List[str] = []
    
    # Version requirements (optional)
    # Simple minimum version (e.g., "3.0.0")
    min_gui_version: Optional[str] = None
    # Advanced range specification (e.g., ">=3.0.0,<4.0.0")
    # Takes precedence over min_gui_version if both are specified
    required_gui_version: Optional[str] = None
    
    # Alias plugin_name to tab_name for backward compatibility
    @classmethod
    @property
    def plugin_name(cls) -> str:
        """Return the plugin name (aliases tab_name for compatibility)."""
        return cls.tab_name
    
    @classmethod
    @property
    def plugin_description(cls) -> str:
        """Return the plugin description (aliases tab_description for compatibility)."""
        return cls.tab_description
    
    @classmethod
    @abstractmethod
    def create_widget(cls, parent: Optional[Any] = None) -> Any:
        """
        Create and return a UI widget to be used as the tab's content.
        
        The specific widget type depends on the UI framework being used.
        For PySide6 implementations, this should return a QWidget instance.
        
        Args:
            parent: The parent widget (framework-specific, e.g., QTabWidget for PySide6)
            
        Returns:
            Any: A UI widget appropriate for the framework being used
        """
        pass
    
    @classmethod
    def is_supported_platform(cls, platform_name: str) -> bool:
        """
        Check if this plugin supports the given platform.
        
        Args:
            platform_name: Name of the platform (e.g., "Windows", "Linux")
            
        Returns:
            bool: True if the platform is supported, False otherwise
        """
        return platform_name.capitalize() in cls.supported_platforms
    
    @classmethod
    def get_current_platform(cls) -> str:
        """Get the current platform name."""
        return platform.system()
    
    @classmethod
    def is_compatible(cls) -> bool:
        """
        Check if this plugin is compatible with the current platform.
        
        Returns:
            bool: True if compatible, False otherwise
        """
        return cls.is_supported_platform(cls.get_current_platform())
    
    @classmethod
    def get_plugin_info(cls) -> Dict[str, Any]:
        """
        Get comprehensive information about this plugin.
        
        Returns:
            dict: Plugin information including name, description, version, etc.
        """
        # Normalize authors: prefer plugin_authors if set; otherwise fallback to plugin_author
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
            'name': cls.tab_name,
            'description': cls.tab_description,
            'supported_platforms': cls.supported_platforms,
            'requires_admin': cls.requires_admin,
            'version': cls.plugin_version,
            'author': author_text,           # Backward-compatible single string for display
            'authors': authors_list,         # New field for multi-author support
            'compatible': cls.is_compatible(),
            'current_platform': cls.get_current_platform(),
            'min_gui_version': getattr(cls, 'min_gui_version', None),
            'required_gui_version': getattr(cls, 'required_gui_version', None),
            'dependencies': getattr(cls, 'dependencies', []),  # New in v3.4.0
        }
    
    @classmethod
    def validate_plugin(cls) -> List[str]:
        """
        Validate the plugin configuration and return any error messages.
        
        Returns:
            List[str]: List of validation error messages (empty if valid)
        """
        errors = []
        
        if not cls.tab_name or cls.tab_name == "Unnamed Tab":
            errors.append("Plugin must define a valid tab_name")
        
        if not cls.supported_platforms:
            errors.append("Plugin must define supported_platforms")
        
        if not cls.plugin_version:
            errors.append("Plugin must define plugin_version")
        
        # Validate version requirements format (basic check)
        if hasattr(cls, 'min_gui_version') and cls.min_gui_version:
            if not re.match(r'^\d+\.\d+(?:\.\d+)?', str(cls.min_gui_version)):
                errors.append(f"Invalid min_gui_version format: {cls.min_gui_version}")
        
        if hasattr(cls, 'required_gui_version') and cls.required_gui_version:
            # Basic format check for range specifications
            # Should contain operators like >=, <, etc. and version numbers
            req_str = str(cls.required_gui_version)
            if not re.search(r'[><=-]+', req_str):
                errors.append(f"Invalid required_gui_version format (must include operators): {cls.required_gui_version}")
        
        return errors
    
    @classmethod
    def on_tab_activated(cls, widget: Any) -> None:
        """
        Called when the tab becomes active.
        
        This method is optional and can be overridden by plugins to perform
        actions when their tab is activated (e.g., refresh data, update UI).
        
        Args:
            widget: The widget instance for this tab
        """
        pass
    
    @classmethod
    def on_tab_deactivated(cls, widget: Any) -> None:
        """
        Called when the tab becomes inactive.
        
        This method is optional and can be overridden by plugins to perform
        actions when their tab is deactivated (e.g., save state, pause updates).
        
        Args:
            widget: The widget instance for this tab
        """
        pass
    
    @classmethod
    def on_plugin_enabled(cls) -> None:
        """
        Called when the plugin is enabled.
        
        This method is optional and can be overridden by plugins to perform
        initialization when the plugin is enabled.
        """
        pass
    
    @classmethod
    def on_plugin_disabled(cls) -> None:
        """
        Called when the plugin is disabled.
        
        This method is optional and can be overridden by plugins to perform
        cleanup when the plugin is disabled.
        """
        pass
    
    @classmethod
    def on_settings_changed(cls, settings_dict: Dict[str, Any]) -> None:
        """
        Called when plugin settings are changed.
        
        This method is optional and can be overridden by plugins to react
        to settings changes.
        
        Args:
            settings_dict: Dictionary containing the updated settings
        """
        pass
    
    @classmethod
    def get_settings_widget(cls, parent: Optional[Any] = None) -> Optional[Any]:
        """
        Get a settings widget for this plugin.
        
        This method is optional and can be overridden by plugins to provide
        a configuration widget. The widget should contain controls for all
        plugin settings that the user can configure.
        
        Args:
            parent: Parent widget for the settings widget
            
        Returns:
            A widget containing settings controls, or None if the plugin
            has no configurable settings
        """
        return None


class CoreTabPlugin(BaseTabPlugin):
    """
    Base class for core (built-in) tab plugins.
    
    These are the original tabs that come with the application.
    """
    
    plugin_author: str = "Basic GUI Application Team"
    is_core_plugin: bool = True


# Re-export new interfaces for convenient access
from .interfaces import (
    Plugin as PluginBase,
    TabExtension,
    MenuExtension,
    StatusExtension,
    ToolbarExtension,
    ServiceExtension,
    EventSubscriberExtension,
    SettingsExtension,
)

from .types import MenuItemDefinition, ToolbarAction, PluginEvent

from .registry import PluginRegistry, plugin_registry  # re-export

__all__ = [
    # Backward compatible exports
    'BaseTabPlugin',
    'CoreTabPlugin',
    'PluginRegistry',
    'plugin_registry',
    # New extension interfaces (v3.4.0)
    'PluginBase',
    'TabExtension',
    'MenuExtension',
    'StatusExtension',
    'ToolbarExtension',
    'ServiceExtension',
    'EventSubscriberExtension',
    'SettingsExtension',
    # New types (v3.4.0)
    'MenuItemDefinition',
    'ToolbarAction',
    'PluginEvent',
]