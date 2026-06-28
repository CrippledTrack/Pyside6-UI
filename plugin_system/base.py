"""
Base plugin classes for the Basic UI Application.
"""
from __future__ import annotations

import logging
import platform
import re
from abc import abstractmethod
from typing import Optional, List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..app.qt_bindings import QWidget
    from ..app.services.container import ServiceContainer
    from ..app.services.settings_service import SettingsService
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
    IServiceContainer,
    ISettingsService,
)

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
    
    # Platform support (empty list = all platforms supported)
    supported_platforms: List[str] = []
    
    # Plugin dependencies (optional)
    dependencies: List[str] = []
    
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
        self._widget: Optional["QWidget"] = None
        
        # Convenience accessors for common services
        # We try to get the settings service using interface first to avoid circular imports
        try:
            self.settings = container.get(ISettingsService)
        except (ValueError, KeyError, TypeError):
            try:
                from ..app.services.settings_service import SettingsService
                self.settings = container.get(SettingsService)
            except (ValueError, KeyError, ImportError):
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
    
    def _cleanup_plugin_resources(self) -> None:
        """Framework-level cleanup of common resources (QTimers, QThreads, QWidgets).
        
        This is called automatically when the plugin is disabled or unloaded to prevent leaks.
        Scans both the plugin instance and its associated tab widget (self._widget) for
        active QTimers, QThreads, and QWidgets that need to be stopped or destroyed.
        """
        from ..app.qt_bindings import QTimer, QThread, QWidget

        try:
            # Scan the plugin instance and the tab widget's attributes,
            # since threads/timers typically live on the widget (e.g. QuickSetupTab),
            # not on the plugin class (e.g. QuickSetupPlugin).
            targets = [self]
            if getattr(self, "_widget", None) is not None:
                targets.append(self._widget)

            for target in targets:
                target_label = target.__class__.__name__
                for attr_name in list(target.__dict__.keys()):
                    try:
                        attr = getattr(target, attr_name, None)
                    except Exception:
                        continue
                    if attr is None:
                        continue
                    
                    # Stop active QTimers
                    if isinstance(attr, QTimer):
                        try:
                            if attr.isActive():
                                attr.stop()
                                logger.debug(f"Automatically stopped active QTimer '{attr_name}' on {target_label} for plugin '{self.plugin_name}'")
                        except Exception as e:
                            logger.warning(f"Error stopping QTimer '{attr_name}': {e}")
                    
                    # Stop active QThreads
                    elif isinstance(attr, QThread):
                        try:
                            if attr.isRunning():
                                attr.quit()
                                if not attr.wait(1000):  # Wait up to 1 second
                                    logger.warning(
                                        f"QThread '{attr_name}' on {target_label} for plugin '{self.plugin_name}' "
                                        f"failed to exit gracefully within timeout"
                                    )
                                else:
                                    logger.debug(f"Automatically stopped active QThread '{attr_name}' on {target_label} for plugin '{self.plugin_name}'")
                        except Exception as e:
                            logger.warning(f"Error stopping QThread '{attr_name}': {e}")
                    
                    # Delete QWidgets (skip self._widget itself, it's handled below)
                    elif isinstance(attr, QWidget) and attr is not self._widget:
                        try:
                            attr.close()
                            attr.deleteLater()
                            logger.debug(f"Automatically requested deletion of QWidget '{attr_name}' on {target_label} for plugin '{self.plugin_name}'")
                        except Exception as e:
                            logger.warning(f"Error deleting QWidget '{attr_name}': {e}")

            # Close and schedule deletion of the tab widget itself
            if self._widget is not None:
                try:
                    self._widget.close()
                    self._widget.deleteLater()
                except Exception as e:
                    logger.warning(f"Error closing/deleting plugin widget for '{self.plugin_name}': {e}")
            
            # Reset the framework-defined widget reference
            self._widget = None
        except Exception as e:
            logger.error(f"Error during framework cleanup of '{self.plugin_name}': {e}")
    
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

        target = _normalize_platform_name_for_matching(platform_name)
        supported_normalized = {
            _normalize_platform_name_for_matching(p) for p in cls.supported_platforms
        }
        return target in supported_normalized
    
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

        # If supported_platforms is empty, show all application-supported platforms
        display_platforms = cls.supported_platforms if cls.supported_platforms else ["Windows", "Linux", "macOS"]
        
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
        
        has_name = bool(getattr(cls, 'plugin_name', None) and cls.plugin_name != "Unnamed Plugin")
        if not has_name:
            errors.append("Plugin must define a valid plugin_name")
        
        has_title = bool(getattr(cls, 'tab_title', None) and cls.tab_title != "Unnamed Tab")
        if not has_title:
            errors.append("Plugin must define a valid tab_title")
        
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



# Re-exports
from .types import MenuItemDefinition, ToolbarAction, PluginEvent

__all__ = [
    # Base classes
    'BaseTabPlugin',
    'CoreTabPlugin',
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