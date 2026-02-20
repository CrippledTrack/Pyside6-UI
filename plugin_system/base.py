"""
Base plugin classes for the Basic UI Application.

v4.0.0 BREAKING CHANGES:
- BaseTabPlugin is now instance-based (use `self` instead of `cls`)
- Constructor receives ServiceContainer for dependency injection
- Use `plugin_name` and `tab_title` instead of `tab_name`
- Removed PluginMeta metaclass and aliasing

Legacy 3.x plugins using classmethods will continue to work via LegacyPluginAdapter.
"""
from __future__ import annotations

import platform
import re
from abc import abstractmethod
from typing import Optional, List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..app.qt_bindings import QWidget
    from ..app.services.container import ServiceContainer
    from ..app.services.settings_service import SettingsService

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


class BaseTabPlugin:
    """Base class for tab plugins with service injection.
    
    v4.0.0: This is now an instance-based class. Plugins receive a 
    ServiceContainer in their constructor and use instance methods.
    
    For backward compatibility, both old (tab_name) and new (plugin_name/tab_title)
    attribute names are supported.
    
    Example:
        class MyPlugin(BaseTabPlugin):
            plugin_name = "My Plugin"
            tab_title = "My Tab"
            
            def create_widget(self, parent=None):
                return MyWidget(parent, settings=self.settings)
    """
    
    # Required metadata (class-level)
    plugin_name: str = "Unnamed Plugin"
    plugin_description: str = "No description provided"
    plugin_version: str = "1.0.0"
    plugin_author: str = "Unknown"
    plugin_authors: List[str] = []
    
    # Tab-specific
    tab_title: str = "Unnamed Tab"  # Display name in tab bar
    requires_admin: bool = False
    
    # Legacy aliases (backward compatibility with 3.x)
    tab_name: str = "Unnamed Tab"  # Alias for plugin_name/tab_title
    tab_description: str = "No description provided"  # Alias for plugin_description
    
    # Platform support (empty list = all platforms supported)
    supported_platforms: List[str] = []
    
    # Plugin dependencies (optional)
    dependencies: List[str] = []
    
    # If True, plugin is disabled by default on first discovery
    disabled_by_default: bool = False
    
    # Version requirements (optional)
    min_gui_version: Optional[str] = None
    required_gui_version: Optional[str] = None
    
    def __init__(self, container: "ServiceContainer") -> None:
        """Initialize the plugin with service container.
        
        Args:
            container: The application's service container for DI
        """
        self.container = container
        self._widget: Optional["QWidget"] = None
        
        # Convenience accessors for common services
        # Import here to avoid circular imports
        from ..app.services.settings_service import SettingsService
        try:
            self.settings: Optional["SettingsService"] = container.get(SettingsService)
        except (ValueError, KeyError):
            self.settings = None
    
    @abstractmethod
    def create_widget(self, parent: Optional["QWidget"] = None) -> "QWidget":
        """Create and return the tab widget.
        
        Args:
            parent: Parent widget (typically QTabWidget)
            
        Returns:
            QWidget instance for the tab content
        """
        raise NotImplementedError("Subclasses must implement create_widget()")
    
    def on_tab_activated(self) -> None:
        """Called when the tab becomes active. Override as needed."""
        pass
    
    def on_tab_deactivated(self) -> None:
        """Called when the tab becomes inactive. Override as needed."""
        pass
    
    def on_plugin_enabled(self) -> None:
        """Called when the plugin is enabled."""
        pass
    
    def on_plugin_disabled(self) -> None:
        """Called when the plugin is disabled."""
        pass
    
    def on_settings_changed(self, settings_dict: Dict[str, Any]) -> None:
        """Called when plugin settings are changed."""
        pass
    
    def get_settings_widget(self, parent: Optional["QWidget"] = None) -> Optional["QWidget"]:
        """Get a settings widget for this plugin. Override to provide settings UI."""
        return None
    
    # Class methods that don't need instance state
    @classmethod
    def is_supported_platform(cls, platform_name: str) -> bool:
        """Check if this plugin supports the given platform.
        
        If supported_platforms is empty, all platforms are supported.
        """
        if not cls.supported_platforms:
            return True  # Empty = all platforms supported
        return platform_name.capitalize() in cls.supported_platforms
    
    @classmethod
    def get_current_platform(cls) -> str:
        """Get the current platform name."""
        return platform.system()
    
    @classmethod
    def is_compatible(cls) -> bool:
        """Check if this plugin is compatible with the current platform."""
        return cls.is_supported_platform(cls.get_current_platform())
    
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

        # Support both new (plugin_name/tab_title) and legacy (tab_name) naming
        name = getattr(cls, 'plugin_name', None)
        if not name or name == "Unnamed Plugin":
            name = getattr(cls, 'tab_name', cls.__name__)
        
        title = getattr(cls, 'tab_title', None)
        if not title or title == "Unnamed Tab":
            title = getattr(cls, 'tab_name', name)
        
        description = getattr(cls, 'plugin_description', None)
        if not description or description == "No description provided":
            description = getattr(cls, 'tab_description', "No description provided")

        # If supported_platforms is empty, show all application-supported platforms
        display_platforms = cls.supported_platforms if cls.supported_platforms else ["Windows", "Linux"]
        
        return {
            'name': name,
            'tab_title': title,
            'description': description,
            'supported_platforms': display_platforms,
            'requires_admin': cls.requires_admin,
            'version': cls.plugin_version,
            'author': author_text,
            'authors': authors_list,
            'compatible': cls.is_compatible(),
            'current_platform': cls.get_current_platform(),
            'min_gui_version': getattr(cls, 'min_gui_version', None),
            'required_gui_version': getattr(cls, 'required_gui_version', None),
            'dependencies': getattr(cls, 'dependencies', []),
        }
    
    @classmethod
    def validate_plugin(cls) -> List[str]:
        """Validate the plugin configuration and return any error messages."""
        errors = []
        
        # Support both new (plugin_name) and legacy (tab_name) naming
        has_name = (
            (hasattr(cls, 'plugin_name') and cls.plugin_name and cls.plugin_name != "Unnamed Plugin") or
            (hasattr(cls, 'tab_name') and cls.tab_name and cls.tab_name != "Unnamed Tab")
        )
        if not has_name:
            errors.append("Plugin must define a valid plugin_name or tab_name")
        
        # Support both new (tab_title) and legacy (tab_name) for display title
        has_title = (
            (hasattr(cls, 'tab_title') and cls.tab_title and cls.tab_title != "Unnamed Tab") or
            (hasattr(cls, 'tab_name') and cls.tab_name and cls.tab_name != "Unnamed Tab")
        )
        if not has_title:
            errors.append("Plugin must define a valid tab_title or tab_name")
        
        # Note: supported_platforms is optional - empty means all platforms supported
        
        if not cls.plugin_version:
            errors.append("Plugin must define plugin_version")
        
        # Validate version requirements format
        if hasattr(cls, 'min_gui_version') and cls.min_gui_version:
            if not re.match(r'^\d+\.\d+(?:\.\d+)?', str(cls.min_gui_version)):
                errors.append(f"Invalid min_gui_version format: {cls.min_gui_version}")
        
        if hasattr(cls, 'required_gui_version') and cls.required_gui_version:
            req_str = str(cls.required_gui_version)
            if not re.search(r'[><!=]+', req_str):
                errors.append(f"Invalid required_gui_version format: {cls.required_gui_version}")
        
        return errors


class CoreTabPlugin(BaseTabPlugin):
    """Base class for core (built-in) tab plugins."""
    
    plugin_author: str = "Basic GUI Application Team"
    is_core_plugin: bool = True


# =============================================================================
# Legacy 3.x support
# =============================================================================

class LegacyBaseTabPlugin(Plugin):
    """Legacy base class for 3.x classmethod-based plugins.
    
    This class exists for backward compatibility with 3.x plugins.
    It will be adapted via LegacyPluginAdapter at runtime.
    """
    
    # Legacy naming (kept for 3.x compat)
    tab_name: str = "Unnamed Tab"
    tab_description: str = "No description provided"
    supported_platforms: List[str] = ["Windows", "Linux"]
    requires_admin: bool = False
    plugin_version: str = "1.0.0"
    plugin_author: str = "Unknown"
    plugin_authors: List[str] = []
    disabled_by_default: bool = False
    dependencies: List[str] = []
    min_gui_version: Optional[str] = None
    required_gui_version: Optional[str] = None
    
    @classmethod
    @abstractmethod
    def create_widget(cls, parent: Optional[Any] = None) -> Any:
        """Legacy classmethod - use instance method instead."""
        pass
    
    @classmethod
    def on_tab_activated(cls, widget: Any) -> None:
        """Legacy classmethod - use instance method without widget param."""
        pass
    
    @classmethod
    def on_tab_deactivated(cls, widget: Any) -> None:
        """Legacy classmethod - use instance method without widget param."""
        pass
    
    @classmethod
    def is_supported_platform(cls, platform_name: str) -> bool:
        """Check if this plugin supports the given platform.
        
        If supported_platforms is empty, all platforms are supported.
        """
        if not cls.supported_platforms:
            return True  # Empty = all platforms supported
        return platform_name.capitalize() in cls.supported_platforms
    
    @classmethod
    def get_current_platform(cls) -> str:
        return platform.system()
    
    @classmethod
    def is_compatible(cls) -> bool:
        return cls.is_supported_platform(cls.get_current_platform())
    
    @classmethod
    def get_plugin_info(cls) -> Dict[str, Any]:
        """Get plugin info using legacy naming."""
        authors_list: List[str] = []
        try:
            if isinstance(getattr(cls, 'plugin_authors', []), list) and getattr(cls, 'plugin_authors'):
                authors_list = [str(a) for a in getattr(cls, 'plugin_authors') if a]
        except Exception:
            authors_list = []
        if not authors_list and getattr(cls, 'plugin_author', None):
            authors_list = [str(getattr(cls, 'plugin_author'))]

        author_text = ", ".join(authors_list) if authors_list else str(getattr(cls, 'plugin_author', 'Unknown'))

        # If supported_platforms is empty, show all application-supported platforms
        display_platforms = cls.supported_platforms if cls.supported_platforms else ["Windows", "Linux"]

        return {
            'name': getattr(cls, 'tab_name', cls.__name__),
            'description': getattr(cls, 'tab_description', ''),
            'supported_platforms': display_platforms,
            'requires_admin': cls.requires_admin,
            'version': cls.plugin_version,
            'author': author_text,
            'authors': authors_list,
            'compatible': cls.is_compatible(),
            'current_platform': cls.get_current_platform(),
            'min_gui_version': getattr(cls, 'min_gui_version', None),
            'required_gui_version': getattr(cls, 'required_gui_version', None),
            'dependencies': getattr(cls, 'dependencies', []),
        }


# Re-exports
from .registry import PluginRegistry, plugin_registry
from .types import MenuItemDefinition, ToolbarAction, PluginEvent

__all__ = [
    # v4.0.0 classes
    'BaseTabPlugin',
    'CoreTabPlugin',
    # Legacy (for 3.x compatibility)
    'LegacyBaseTabPlugin',
    # Registry
    'PluginRegistry',
    'plugin_registry',
    # Interfaces
    'PluginProtocol',
    'TabExtension',
    'MenuExtension',
    'StatusExtension',
    'ToolbarExtension',
    'ServiceExtension',
    'EventSubscriberExtension',
    'SettingsExtension',
    # Types
    'MenuItemDefinition',
    'ToolbarAction',
    'PluginEvent',
]