"""
Base plugin classes for the Basic UI Application.
"""
from __future__ import annotations

import logging
import platform
import re
from typing import Optional, List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..app.services.container import ServiceContainer
    from .registry import PluginRegistry

from .identity import plugin_identity
from .interfaces import (
    IServiceContainer,
    ISettingsService,
    IPluginResourceCleanup,
)
from .types import TabContent, TabCreateContext

logger = logging.getLogger(__name__)



def _normalize_platform_name_for_matching(name: str) -> str:
    """Normalize platform names for matching against supported_platforms.

    This allows plugins to declare user-friendly labels like "macOS" while
    Python's platform.system() returns identifiers such as "Darwin".
    """
    s = str(name).strip().lower()
    if s in ("windows", "win32"):
        return "Windows"
    if s == "linux":
        return "Linux"
    if s in ("darwin", "macos", "mac os", "osx", "mac os x"):
        return "macOS"
    # Fallback: capitalize the original for best-effort matching.
    return str(name).capitalize()


class BaseTabPlugin:
    """Base class for tab plugins with service injection.
    
    This is now an instance-based class. Plugins receive a 
    ServiceContainer in their constructor and use instance methods.
    
    Override exactly one of ``create_tab_content`` (preferred) or
    ``create_widget`` (legacy). The other delegates automatically.
    
    Example:
        class MyPlugin(BaseTabPlugin):
            plugin_name = "My Plugin"
            tab_title = "My Tab"
            
            def create_tab_content(self, context):
                return MyView(context.parent)
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
    
    # Platform support (empty list = all platforms supported)
    supported_platforms: List[str] = []

    # UI backends that can host this plugin's tab content
    # (empty list = all backends supported)
    ui_backends: List[str] = []
    
    # Plugin dependencies (plugin_id or unique display name). Enforced after discovery.
    dependencies: List[str] = []

    # Immutable identity. Empty means default to plugin_name.
    plugin_id: str = ""
    
    # If True, plugin is disabled by default on first discovery
    disabled_by_default: bool = False
    
    # Version requirements (optional)
    min_gui_version: Optional[str] = None
    required_gui_version: Optional[str] = None
    
    def __init__(self, container: "IServiceContainer" | "ServiceContainer") -> None:
        """Initialize the plugin with service container.
        
        Args:
            container: The application's service container for DI
        """
        self.container = container
        self._widget: Optional[TabContent] = None
        
        # Convenience accessors for common services
        try:
            self.settings = container.get(ISettingsService)
        except (ValueError, KeyError, TypeError):
            self.settings = None
    
    def create_tab_content(self, context: TabCreateContext) -> TabContent:
        """Create tab content for the active UI backend.
        
        Subclasses should override this (preferred) or ``create_widget``.
        """
        if type(self).create_widget is not BaseTabPlugin.create_widget:
            return self.create_widget(context.parent)
        raise NotImplementedError(
            f"{type(self).__name__} must override create_tab_content() or create_widget()"
        )
    
    def create_widget(self, parent: Optional[Any] = None) -> TabContent:
        """Legacy entry point for Qt-oriented tab content creation.
        
        Subclasses may override this instead of ``create_tab_content``.
        """
        if type(self).create_tab_content is not BaseTabPlugin.create_tab_content:
            return self.create_tab_content(
                TabCreateContext(backend_id="qt", parent=parent)
            )
        raise NotImplementedError(
            f"{type(self).__name__} must override create_tab_content() or create_widget()"
        )
    
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
    
    def _cleanup_plugin_resources(self) -> None:
        """Release backend-specific resources via a registered cleanup service.
        
        Qt hosts register ``IPluginResourceCleanup``; other backends may no-op.
        """
        try:
            cleanup = self.container.get(IPluginResourceCleanup)
        except (ValueError, KeyError, TypeError):
            return
        try:
            cleanup.cleanup(self)
        except Exception as e:
            logger.error(f"Error during framework cleanup of '{self.plugin_name}': {e}")
    
    def on_settings_changed(self, settings_dict: Dict[str, Any]) -> None:
        """Called when plugin settings are changed."""
        pass
    
    def get_settings_widget(self, parent: Optional[Any] = None) -> Optional[TabContent]:
        """Get settings content for this plugin. Override to provide settings UI."""
        return None
    
    # Class methods that don't need instance state
    @classmethod
    def is_supported_platform(cls, platform_name: str) -> bool:
        """Check if this plugin supports the given platform.
        
        If supported_platforms is empty, all platforms are supported.
        """
        if not cls.supported_platforms:
            return True  # Empty = all platforms supported

        target = _normalize_platform_name_for_matching(platform_name)
        supported_normalized = {
            _normalize_platform_name_for_matching(p) for p in cls.supported_platforms
        }
        return target in supported_normalized
    
    @classmethod
    def is_supported_ui_backend(cls, backend_id: str) -> bool:
        """Check if this plugin supports the given UI backend.

        If ``ui_backends`` is empty, all backends are supported.
        """
        backends = getattr(cls, "ui_backends", None) or []
        if not backends:
            return True
        return backend_id in backends
    
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

        name = getattr(cls, 'plugin_name', cls.__name__)
        title = getattr(cls, 'tab_title', name)
        description = getattr(cls, 'plugin_description', "No description provided")
        identity = plugin_identity(cls)

        # If supported_platforms is empty, show all application-supported platforms
        display_platforms = cls.supported_platforms if cls.supported_platforms else ["Windows", "Linux", "macOS"]
        
        return {
            'name': name,
            'plugin_id': identity,
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
            'ui_backends': list(getattr(cls, 'ui_backends', []) or []),
        }
    
    @classmethod
    def validate_plugin(cls) -> List[str]:
        """Validate the plugin configuration and return any error messages."""
        errors = []
        
        has_name = bool(getattr(cls, 'plugin_name', None) and cls.plugin_name != "Unnamed Plugin")
        if not has_name:
            errors.append("Plugin must define a valid plugin_name")
        
        has_title = bool(getattr(cls, 'tab_title', None) and cls.tab_title != "Unnamed Tab")
        if not has_title:
            errors.append("Plugin must define a valid tab_title")
        
        # Note: supported_platforms is optional - empty means all platforms supported
        
        if not cls.plugin_version:
            errors.append("Plugin must define plugin_version")

        has_tab_content = (
            getattr(cls, "create_tab_content", None) is not BaseTabPlugin.create_tab_content
        )
        has_widget = getattr(cls, "create_widget", None) is not BaseTabPlugin.create_widget
        if not has_tab_content and not has_widget:
            errors.append(
                "Plugin must override create_tab_content() or create_widget()"
            )
        
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
    
    is_core_plugin: bool = True

    @classmethod
    def _default_core_author(cls) -> str:
        """Derive the default author string from VERSION_NAME."""
        try:
            from ..app.constants import VERSION_NAME
            return f"{VERSION_NAME} Team"
        except Exception:
            return "Core Team"

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Only set the default if the subclass hasn't explicitly overridden it
        if cls.plugin_author == "Unknown":
            cls.plugin_author = cls._default_core_author()


__all__ = [
    'BaseTabPlugin',
    'CoreTabPlugin',
    'TabContent',
    'TabCreateContext',
]
