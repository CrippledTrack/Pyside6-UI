"""
Compatibility utilities for adapting legacy plugins to v4.0.0.

This module provides the LegacyPluginAdapter class which wraps v3.x 
class-based plugins to work with the new instance-based architecture.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Type, TYPE_CHECKING

from abc import ABC

if TYPE_CHECKING:
    from ..app.qt_bindings import QWidget
    from ..app.services.container import ServiceContainer

logger = logging.getLogger(__name__)


class Plugin(ABC):
    """Legacy base class for all plugins (3.x compatibility)."""
    
    # Required metadata
    plugin_name: str = "Unnamed Plugin"
    plugin_description: str = "No description provided"
    plugin_version: str = "1.0.0"
    plugin_author: str = "Unknown"
    plugin_authors: List[str] = []
    
    # Platform support (empty list = all platforms supported)
    supported_platforms: List[str] = []
    
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

        # If supported_platforms is empty, show all application-supported platforms
        display_platforms = cls.supported_platforms if cls.supported_platforms else ["Windows", "Linux"]

        return {
            'name': getattr(cls, 'plugin_name', cls.__name__),
            'description': cls.plugin_description,
            'supported_platforms': display_platforms,
            'version': cls.plugin_version,
            'author': author_text,
            'authors': authors_list,
            'dependencies': getattr(cls, 'dependencies', []),
            'min_gui_version': getattr(cls, 'min_gui_version', None),
            'required_gui_version': getattr(cls, 'required_gui_version', None)
        }


class LegacyPluginAdapter:
    """Adapts a v3.x classmethod-based plugin to the v4.0.0 instance interface.
    
    This adapter wraps legacy plugins that use @classmethod and allows them
    to work with the new instance-based plugin system. 
    
    Example:
        # Old 3.x plugin
        class OldPlugin(BaseTabPlugin):
            tab_name = "Old Tab"
            @classmethod
            def create_widget(cls, parent=None):
                return OldWidget(parent)
        
        # Wrapped as instance
        adapter = LegacyPluginAdapter(OldPlugin, container)
        widget = adapter.create_widget(parent)
    """
    
    def __init__(self, legacy_class: Type[Any], container: "ServiceContainer") -> None:
        """Initialize the adapter with a legacy plugin class.
        
        Args:
            legacy_class: The v3.x plugin class to wrap
            container: The service container (stored but not passed to legacy methods)
        """
        self._legacy_class = legacy_class
        self.container = container
        self._widget: Optional["QWidget"] = None
        
        # Copy metadata from legacy class, mapping old names to new
        self.plugin_name = self._get_legacy_name()
        self.tab_title = self._get_legacy_name()  # Same for legacy
        
        # Get description, preferring tab_description for legacy
        desc = getattr(legacy_class, 'tab_description', None)
        if not desc or desc == "No description provided":
            desc = getattr(legacy_class, 'plugin_description', "No description provided")
        self.plugin_description = desc
        
        self.plugin_version = getattr(legacy_class, 'plugin_version', '1.0.0')
        self.plugin_author = getattr(legacy_class, 'plugin_author', 'Unknown')
        self.plugin_authors = getattr(legacy_class, 'plugin_authors', [])
        self.supported_platforms = getattr(legacy_class, 'supported_platforms', ['Windows', 'Linux'])
        self.requires_admin = getattr(legacy_class, 'requires_admin', False)
        self.dependencies = getattr(legacy_class, 'dependencies', [])
        self.disabled_by_default = getattr(legacy_class, 'disabled_by_default', False)
        self.min_gui_version = getattr(legacy_class, 'min_gui_version', None)
        self.required_gui_version = getattr(legacy_class, 'required_gui_version', None)
        
        # Access settings via container if available
        self.settings = None
        try:
            from ..app.services.settings_service import SettingsService
            self.settings = container.get(SettingsService)
        except (ValueError, KeyError, ImportError):
            pass
    
    def _get_legacy_name(self) -> str:
        """Get plugin name from legacy class, checking both old and new attribute names."""
        cls = self._legacy_class
        # Prefer tab_name (old convention) then plugin_name
        if hasattr(cls, 'tab_name') and cls.tab_name != "Unnamed Tab":
            return cls.tab_name
        if hasattr(cls, 'plugin_name') and cls.plugin_name != "Unnamed Plugin":
            return cls.plugin_name
        return cls.__name__
    

    
    def create_widget(self, parent: Optional["QWidget"] = None) -> "QWidget":
        """Create widget by calling the legacy classmethod."""
        self._widget = self._legacy_class.create_widget(parent)
        return self._widget
    
    def on_tab_activated(self) -> None:
        """Call legacy on_tab_activated with stored widget."""
        if hasattr(self._legacy_class, 'on_tab_activated'):
            # Legacy signature passes widget as argument
            self._legacy_class.on_tab_activated(self._widget)
    
    def on_tab_deactivated(self) -> None:
        """Call legacy on_tab_deactivated with stored widget."""
        if hasattr(self._legacy_class, 'on_tab_deactivated'):
            self._legacy_class.on_tab_deactivated(self._widget)
    
    def on_plugin_enabled(self) -> None:
        """Call legacy on_plugin_enabled if available."""
        if hasattr(self._legacy_class, 'on_plugin_enabled'):
            self._legacy_class.on_plugin_enabled()
    
    def on_plugin_disabled(self) -> None:
        """Call legacy on_plugin_disabled if available."""
        if hasattr(self._legacy_class, 'on_plugin_disabled'):
            self._legacy_class.on_plugin_disabled()
    
    def on_settings_changed(self, settings_dict: Dict[str, Any]) -> None:
        """Call legacy on_settings_changed if available."""
        if hasattr(self._legacy_class, 'on_settings_changed'):
            self._legacy_class.on_settings_changed(settings_dict)
    
    def get_settings_widget(self, parent: Optional["QWidget"] = None) -> Optional["QWidget"]:
        """Call legacy get_settings_widget if available."""
        if hasattr(self._legacy_class, 'get_settings_widget'):
            return self._legacy_class.get_settings_widget(parent)
        return None

    def get_menu_items(self) -> List[Any]:
        """Call legacy get_menu_items if available."""
        if hasattr(self._legacy_class, 'get_menu_items'):
            return self._legacy_class.get_menu_items()
        return []

    def create_status_widget(self, parent: Optional["QWidget"] = None) -> Optional["QWidget"]:
        """Call legacy create_status_widget if available."""
        if hasattr(self._legacy_class, 'create_status_widget'):
            return self._legacy_class.create_status_widget(parent)
        return None

    def get_toolbar_actions(self) -> List[Any]:
        """Call legacy get_toolbar_actions if available."""
        if hasattr(self._legacy_class, 'get_toolbar_actions'):
            return self._legacy_class.get_toolbar_actions()
        return []

    def on_application_start(self, container: "ServiceContainer") -> None:
        """Call legacy on_application_start if available."""
        if hasattr(self._legacy_class, 'on_application_start'):
            self._legacy_class.on_application_start(container)

    def on_application_shutdown(self) -> None:
        """Call legacy on_application_shutdown if available."""
        if hasattr(self._legacy_class, 'on_application_shutdown'):
            self._legacy_class.on_application_shutdown()

    def get_event_subscriptions(self) -> Dict[str, Any]:
        """Call legacy get_event_subscriptions if available."""
        if hasattr(self._legacy_class, 'get_event_subscriptions'):
            return self._legacy_class.get_event_subscriptions()
        return {}
    
    # Class method proxies (these don't need instance state)
    @classmethod
    def is_legacy_plugin(cls, plugin_class: Type[Any]) -> bool:
        """Check if a plugin class is a legacy 3.x plugin needing adaptation.
        
        A plugin is considered legacy if:
        1. It has classmethod create_widget (not instance method)
        2. It uses tab_name instead of plugin_name
        3. It doesn't have an __init__ that accepts ServiceContainer
        """
        # Check for tab_name (legacy naming)
        has_tab_name = hasattr(plugin_class, 'tab_name') and plugin_class.tab_name != "Unnamed Tab"
        has_plugin_name = hasattr(plugin_class, 'plugin_name') and plugin_class.plugin_name != "Unnamed Plugin"
        
        if has_tab_name and not has_plugin_name:
            return True
        
        # Check if create_widget is a classmethod
        if hasattr(plugin_class, 'create_widget'):
            create_method = getattr(plugin_class, 'create_widget')
            # classmethods have __self__ pointing to the class
            if hasattr(create_method, '__self__') and create_method.__self__ is plugin_class:
                return True
        
        # Check __init__ signature - legacy plugins don't override __init__
        # or don't accept container
        import inspect
        try:
            init_sig = inspect.signature(plugin_class.__init__)
            params = list(init_sig.parameters.keys())
            # v4.0 plugins should have 'container' as second param (after self)
            if len(params) < 2 or 'container' not in params:
                return True
        except (ValueError, TypeError):
            # Can't inspect, assume legacy
            return True
        
        return False
    
    def get_plugin_info(self) -> Dict[str, Any]:
        """Get plugin info by calling legacy class method."""
        if hasattr(self._legacy_class, 'get_plugin_info'):
            info = self._legacy_class.get_plugin_info()
            # Ensure new fields are present
            info.setdefault('tab_title', info.get('name', self.tab_title))
            return info
        return {
            'name': self.plugin_name,
            'tab_title': self.tab_title,
            'description': self.plugin_description,
            'version': self.plugin_version,
        }
    
    def is_compatible(self) -> bool:
        """Check compatibility via legacy class method."""
        if hasattr(self._legacy_class, 'is_compatible'):
            return self._legacy_class.is_compatible()
        return True
    
    def validate_plugin(self) -> List[str]:
        """Validate via legacy class method."""
        if hasattr(self._legacy_class, 'validate_plugin'):
            return self._legacy_class.validate_plugin()
        return []
    
    @property
    def legacy_class(self) -> Type[Any]:
        """Get the wrapped legacy class."""
        return self._legacy_class


def wrap_legacy_plugin(plugin_class: Type[Any], container: "ServiceContainer") -> Any:
    """Wrap a legacy plugin class if needed, or instantiate a v4.0 plugin directly.
    
    Args:
        plugin_class: Plugin class to wrap or instantiate
        container: Service container for injection
        
    Returns:
        Either a LegacyPluginAdapter or a v4.0 plugin instance
    """
    if LegacyPluginAdapter.is_legacy_plugin(plugin_class):
        logger.debug(f"Wrapping legacy plugin: {plugin_class.__name__}")
        return LegacyPluginAdapter(plugin_class, container)
    else:
        logger.debug(f"Instantiating v4.0 plugin: {plugin_class.__name__}")
        return plugin_class(container)


__all__ = [
    'Plugin',
    'LegacyPluginAdapter',
    'wrap_legacy_plugin',
]
