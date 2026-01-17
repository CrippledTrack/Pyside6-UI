"""
Plugin registry system for managing discovered and loaded plugins.

v4.0.0 BREAKING CHANGES:
- Registry now accepts ServiceContainer for plugin instantiation
- Plugins are instantiated on-demand via get_plugin_instance()
- Legacy 3.x plugins are wrapped via LegacyPluginAdapter
- Interface checking uses Protocol-based isinstance()

The registry maintains both plugin classes (for compatibility) and 
plugin instances (for the new instance-based architecture).
"""

from __future__ import annotations

import inspect
import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Optional, List, Dict, Tuple, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from ..app.services.container import ServiceContainer

# Import interfaces for type checking
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
from .version_utils import check_version_compatibility, get_gui_version

logger = logging.getLogger(__name__)


def _is_show_all_platforms() -> bool:
    """Check if show all platforms mode is enabled."""
    try:
        from ..app.utils.admin import is_show_all_platforms
        result = is_show_all_platforms()
        if result:
            logger.info("Show all platforms mode is ENABLED - bypassing platform filtering")
        return result
    except Exception as e:
        logger.debug(f"Could not check show_all_platforms flag: {e}")
        return False

def _check_implements_interface(plugin_class: Type[Any], interface: Type) -> bool:
    """Check if a plugin class implements an interface.

    Protocol types don't work with issubclass() reliably for classes, so we use
    an explicit interface → requirements mapping and a minimal ABC fallback.
    """
    interface_name = getattr(interface, "__name__", str(interface))

    def _has_callable(attr: str) -> bool:
        try:
            member = inspect.getattr_static(plugin_class, attr)
        except Exception:
            return False
        return callable(getattr(plugin_class, attr, None)) and member is not None

    def _has_attr(attr: str) -> bool:
        return hasattr(plugin_class, attr)

    requirements: Dict[str, Dict[str, List[str]]] = {
        "TabExtension": {"callable": ["create_widget"], "attrs": []},
        "MenuExtension": {"callable": ["get_menu_items"], "attrs": []},
        "StatusExtension": {"callable": ["create_status_widget"], "attrs": []},
        "ToolbarExtension": {"callable": ["get_toolbar_actions"], "attrs": []},
        "ServiceExtension": {"callable": ["on_application_start"], "attrs": []},
        "EventSubscriberExtension": {"callable": ["get_event_subscriptions"], "attrs": []},
        "SettingsExtension": {"callable": ["get_settings_widget"], "attrs": []},
        "PluginProtocol": {"callable": [], "attrs": ["plugin_name", "supported_platforms"]},
    }

    req = requirements.get(interface_name)
    if req:
        if interface_name == "SettingsExtension":
            # Must be overridden (not just inherited default from BaseTabPlugin)
            try:
                from .base import BaseTabPlugin
                method = inspect.getattr_static(plugin_class, "get_settings_widget")
                base_method = getattr(BaseTabPlugin, "get_settings_widget", None)
                if getattr(plugin_class, "get_settings_widget", None) is base_method:
                    return False
                return method is not None and callable(getattr(plugin_class, "get_settings_widget", None))
            except Exception:
                return False

        if any(not _has_callable(name) for name in req["callable"]):
            return False
        if any(not _has_attr(name) for name in req["attrs"]):
            return False
        return True

    # Fallback: try ABC-style check (best-effort)
    try:
        if isinstance(interface, type) and issubclass(plugin_class, interface):
            return True
    except TypeError:
        pass
    return False



class PluginRegistry:
    """Registry for managing discovered plugins.
    
    v4.0.0: Now supports instance-based plugins with ServiceContainer injection.
    Plugin classes are still registered, but instances are created on-demand.
    
    Supports multiple extension interfaces:
    - TabExtension: Plugins that provide a tab widget
    - MenuExtension: Plugins that contribute menu items
    - StatusExtension: Plugins that contribute status bar widgets
    - ToolbarExtension: Plugins that contribute toolbar actions
    - ServiceExtension: Plugins that provide background services
    - EventSubscriberExtension: Plugins that subscribe to events
    """

    def __init__(self, container: Optional["ServiceContainer"] = None) -> None:
        """Initialize the registry.
        
        Args:
            container: Optional ServiceContainer for instantiating v4.0.0 plugins.
                      Can be set later via set_container().
        """
        self._container = container
        
        # Main plugin registry (by name) - stores CLASSES
        self._plugins: Dict[str, Type[Any]] = {}
        self._core_plugins: Dict[str, Type[Any]] = {}
        self._external_plugins: Dict[str, Type[Any]] = {}
        self._disabled_plugins: set = set()
        
        # Plugin instances cache (v4.0.0)
        self._plugin_instances: Dict[str, Any] = {}

        # Optional async event delivery executor (opt-in)
        self._event_executor: Optional[ThreadPoolExecutor] = None
        self._event_executor_lock = threading.Lock()
        
        # Track plugins seen in this runtime
        self._seen_plugins: set = set()
        self._version_incompatibilities: Dict[str, str] = {}
        
        # Interface-based plugin tracking
        self._tab_plugins: Dict[str, Type[Any]] = {}
        self._menu_plugins: Dict[str, Type[Any]] = {}
        self._status_plugins: Dict[str, Type[Any]] = {}
        self._toolbar_plugins: Dict[str, Type[Any]] = {}
        self._service_plugins: Dict[str, Type[Any]] = {}
        self._event_subscriber_plugins: Dict[str, Type[Any]] = {}
        
        # Rejected plugins tracking
        self._rejected_plugins: Dict[str, Tuple[Type[Any], str]] = {}
    
    def set_container(self, container: "ServiceContainer") -> None:
        """Set the service container for plugin instantiation.
        
        Args:
            container: The application's service container
        """
        self._container = container
        # Clear instance cache when container changes
        self._plugin_instances.clear()

    def register_plugin(self, plugin_class: Type[Any], is_core: bool = False) -> None:
        """Register a plugin class in the registry.

        Args:
            plugin_class: The plugin class to register
            is_core: Whether this is a core plugin
        """
        # Get plugin name - check for non-default values
        # Legacy plugins use tab_name, new ones use plugin_name
        plugin_name = None
        
        # First check tab_name (legacy) - prefer this for backward compat
        tab_name = getattr(plugin_class, 'tab_name', None)
        if tab_name and tab_name != "Unnamed Tab":
            plugin_name = tab_name
        
        # If no valid tab_name, check plugin_name (v4.0)
        if not plugin_name:
            pn = getattr(plugin_class, 'plugin_name', None)
            if pn and pn != "Unnamed Plugin":
                plugin_name = pn
        
        # Fallback to class name
        if not plugin_name:
            plugin_name = plugin_class.__name__

        # Validate plugin
        if hasattr(plugin_class, 'validate_plugin'):
            errors = plugin_class.validate_plugin()
            if errors:
                raise ValueError(f"Invalid plugin '{plugin_name}': {', '.join(errors)}")
        else:
            errors = self._validate_extension_plugin(plugin_class, plugin_name)
            if errors:
                raise ValueError(f"Invalid plugin '{plugin_name}': {', '.join(errors)}")

        # Check platform compatibility
        show_all = _is_show_all_platforms()
        if hasattr(plugin_class, 'is_compatible'):
            is_compatible = plugin_class.is_compatible()
        else:
            is_compatible = self._check_extension_plugin_compatibility(plugin_class)
        
        supported_platforms = getattr(plugin_class, 'supported_platforms', [])
        
        if not show_all and not is_compatible:
            logger.debug(f"Skipping plugin '{plugin_name}' - not compatible with current platform.")
            return

        if show_all and not is_compatible:
            logger.info(f"Loading cross-platform plugin '{plugin_name}' (supported: {supported_platforms})")

        # Check version compatibility
        if not self._check_plugin_compatibility(plugin_class, plugin_name):
            return

        # Handle name conflicts
        if not self._handle_plugin_conflicts(plugin_name, is_core):
            return

        # Register the plugin class
        self._add_plugin_to_registry(plugin_name, plugin_class, is_core)
        self._apply_default_disabled_state(plugin_class, plugin_name)
        self._seen_plugins.add(plugin_name)
        
        logger.debug(f"Registered plugin: {plugin_name} (core={is_core})")

    def get_plugin_instance(self, name: str) -> Any:
        """Get or create a plugin instance by name.
        
        v4.0.0: Creates instances on first access, caches them for reuse.
        Legacy plugins are wrapped via LegacyPluginAdapter.
        
        Args:
            name: Plugin name
            
        Returns:
            Plugin instance (either v4.0.0 instance or LegacyPluginAdapter)
            
        Raises:
            ValueError: If plugin not found or container not set
        """
        if name in self._plugin_instances:
            return self._plugin_instances[name]
        
        plugin_class = self._plugins.get(name)
        if not plugin_class:
            raise ValueError(f"Plugin '{name}' not found in registry")
        
        if not self._container:
            raise ValueError("ServiceContainer not set - call set_container() first")
        
        # Use compatibility utility to wrap legacy or instantiate new
        from .compatibility import wrap_legacy_plugin
        instance = wrap_legacy_plugin(plugin_class, self._container)
        self._plugin_instances[name] = instance
        
        logger.debug(f"Created instance for plugin: {name}")
        return instance
    
    def get_plugin_instances(self, enabled_only: bool = True) -> Dict[str, Any]:
        """Get instances for all (or enabled) plugins.
        
        Args:
            enabled_only: If True, only instantiate enabled plugins
            
        Returns:
            Dict mapping plugin name to instance
        """
        result = {}
        for name in self._plugins:
            if enabled_only and not self.is_enabled(name):
                continue
            try:
                result[name] = self.get_plugin_instance(name)
            except Exception as e:
                logger.error(f"Failed to instantiate plugin '{name}': {e}")
        return result

    def has_plugin_instance(self, name: str) -> bool:
        """Check if a plugin instance is cached."""
        return name in self._plugin_instances

    def _validate_extension_plugin(self, plugin_class: Type[Any], plugin_name: str) -> List[str]:
        """Validate an extension plugin."""
        errors = []
        
        # Check that plugin has a valid (non-default) name
        tab_name = getattr(plugin_class, 'tab_name', None)
        pn = getattr(plugin_class, 'plugin_name', None)
        has_valid_name = (
            (tab_name and tab_name != "Unnamed Tab") or
            (pn and pn != "Unnamed Plugin")
        )
        if not has_valid_name:
            errors.append("Plugin must define plugin_name or tab_name")
        
        # Check that plugin implements at least one extension interface
        has_interface = any([
            _check_implements_interface(plugin_class, TabExtension),
            _check_implements_interface(plugin_class, MenuExtension),
            _check_implements_interface(plugin_class, StatusExtension),
            _check_implements_interface(plugin_class, ToolbarExtension),
            _check_implements_interface(plugin_class, ServiceExtension),
            _check_implements_interface(plugin_class, EventSubscriberExtension),
            _check_implements_interface(plugin_class, SettingsExtension),
        ])
        
        if not has_interface:
            errors.append("Plugin must implement at least one extension interface")
        
        return errors
    
    def _check_extension_plugin_compatibility(self, plugin_class: Type[Any]) -> bool:
        """Check platform compatibility for plugins."""
        import platform
        current_platform = platform.system()
        supported_platforms = getattr(plugin_class, 'supported_platforms', [])
        
        if not supported_platforms:
            return True
        
        normalized_current = current_platform.capitalize()
        normalized_supported = [p.capitalize() for p in supported_platforms]
        
        return normalized_current in normalized_supported
    
    def _check_plugin_compatibility(self, plugin_class: Type[Any], plugin_name: str) -> bool:
        """Check if plugin version is compatible with GUI version."""
        gui_version = get_gui_version()
        min_version = getattr(plugin_class, 'min_gui_version', None)
        required_version = getattr(plugin_class, 'required_gui_version', None)
        
        if not min_version and not required_version:
            return True
        
        is_compatible, error_msg = check_version_compatibility(
            gui_version, 
            min_gui_version=min_version,
            required_gui_version=required_version
        )
        
        if not is_compatible:
            self._version_incompatibilities[plugin_name] = error_msg or "Version incompatible"
            self._rejected_plugins[plugin_name] = (plugin_class, error_msg or "Version incompatible")
            logger.warning(f"Plugin '{plugin_name}' version requirement not met: {error_msg}")
            return False
        
        return True

    def _handle_plugin_conflicts(self, plugin_name: str, is_core: bool) -> bool:
        """Handle plugin name conflicts."""
        if plugin_name not in self._plugins:
            return True
        
        existing_is_core = plugin_name in self._core_plugins
        if existing_is_core and not is_core:
            logger.warning(f"Skipping external plugin '{plugin_name}' - conflicts with core plugin")
            return False
        
        if not existing_is_core and is_core:
            logger.info(f"Replacing external plugin '{plugin_name}' with core plugin")
            if plugin_name in self._external_plugins:
                del self._external_plugins[plugin_name]
            # Clear cached instance
            self._plugin_instances.pop(plugin_name, None)
        
        return True

    def _add_plugin_to_registry(self, plugin_name: str, plugin_class: Type[Any], is_core: bool) -> None:
        """Add plugin to the appropriate registry dictionaries."""
        self._plugins[plugin_name] = plugin_class
        if is_core:
            self._core_plugins[plugin_name] = plugin_class
        else:
            self._external_plugins[plugin_name] = plugin_class
        
        self._categorize_plugin_by_interface(plugin_name, plugin_class)
    
    def _categorize_plugin_by_interface(self, plugin_name: str, plugin_class: Type[Any]) -> None:
        """Categorize a plugin by which interfaces it implements."""
        if _check_implements_interface(plugin_class, TabExtension):
            self._tab_plugins[plugin_name] = plugin_class
        if _check_implements_interface(plugin_class, MenuExtension):
            self._menu_plugins[plugin_name] = plugin_class
        if _check_implements_interface(plugin_class, StatusExtension):
            self._status_plugins[plugin_name] = plugin_class
        if _check_implements_interface(plugin_class, ToolbarExtension):
            self._toolbar_plugins[plugin_name] = plugin_class
        if _check_implements_interface(plugin_class, ServiceExtension):
            self._service_plugins[plugin_name] = plugin_class
        if _check_implements_interface(plugin_class, EventSubscriberExtension):
            self._event_subscriber_plugins[plugin_name] = plugin_class

    def _apply_default_disabled_state(self, plugin_class: Type[Any], plugin_name: str) -> None:
        """Apply default disabled state if plugin has disabled_by_default flag."""
        try:
            if (
                getattr(plugin_class, 'disabled_by_default', False)
                and plugin_name not in self._seen_plugins
                and plugin_name not in self._disabled_plugins
            ):
                self._disabled_plugins.add(plugin_name)
        except Exception:
            pass

    # =========================================================================
    # Query methods
    # =========================================================================

    def get_all_plugins(self) -> Dict[str, Type[Any]]:
        """Get all registered plugin classes."""
        return self._plugins.copy()

    def get_core_plugins(self) -> Dict[str, Type[Any]]:
        """Get core plugin classes only."""
        return self._core_plugins.copy()

    def get_external_plugins(self) -> Dict[str, Type[Any]]:
        """Get external plugin classes only."""
        return self._external_plugins.copy()

    def get_plugin(self, name: str) -> Optional[Type[Any]]:
        """Get a specific plugin class by name."""
        return self._plugins.get(name)

    def list_plugin_names(self) -> List[str]:
        """Get list of all plugin names."""
        return list(self._plugins.keys())

    def clear(self) -> None:
        """Clear all registered plugins and cached instances."""
        self._plugins.clear()
        self._core_plugins.clear()
        self._external_plugins.clear()
        self._disabled_plugins.clear()
        self._plugin_instances.clear()
        self._version_incompatibilities.clear()
        self._seen_plugins.clear()
        self._tab_plugins.clear()
        self._menu_plugins.clear()
        self._status_plugins.clear()
        self._toolbar_plugins.clear()
        self._service_plugins.clear()
        self._event_subscriber_plugins.clear()
        self._rejected_plugins.clear()
        self._shutdown_event_executor()

    def _get_event_executor(self) -> ThreadPoolExecutor:
        """Get/create the bounded executor used for async event delivery."""
        with self._event_executor_lock:
            if self._event_executor is None:
                # Keep this small; event callbacks may touch non-thread-safe UI.
                self._event_executor = ThreadPoolExecutor(
                    max_workers=4,
                    thread_name_prefix="plugin_events",
                )
            return self._event_executor

    def _shutdown_event_executor(self) -> None:
        """Shutdown the async event executor if it exists."""
        with self._event_executor_lock:
            if self._event_executor is not None:
                try:
                    self._event_executor.shutdown(wait=False, cancel_futures=True)
                except TypeError:
                    # Python <3.9 doesn't support cancel_futures
                    self._event_executor.shutdown(wait=False)
                self._event_executor = None

    def get_version_incompatibility(self, name: str) -> Optional[str]:
        """Get the version incompatibility reason for a plugin, if any."""
        return self._version_incompatibilities.get(name)
    
    def get_rejected_plugins(self) -> Dict[str, Tuple[Type[Any], str]]:
        """Get plugins that were rejected during registration."""
        return self._rejected_plugins.copy()

    # =========================================================================
    # Enable/Disable
    # =========================================================================

    def disable_plugin(self, name: str) -> None:
        """Disable a plugin by name."""
        self._disabled_plugins.add(name)

    def enable_plugin(self, name: str) -> None:
        """Enable a plugin by name."""
        self._disabled_plugins.discard(name)

    def is_enabled(self, name: str) -> bool:
        """Check if a plugin is enabled."""
        return name not in self._disabled_plugins

    def get_enabled_plugins(self) -> Dict[str, Type[Any]]:
        """Get all enabled plugin classes."""
        return {k: v for k, v in self._plugins.items() if self.is_enabled(k)}
    
    # =========================================================================
    # Interface-based query methods
    # =========================================================================
    
    def get_tab_extensions(self, enabled_only: bool = True) -> Dict[str, Type[Any]]:
        """Get plugin classes that implement TabExtension."""
        if enabled_only:
            return {k: v for k, v in self._tab_plugins.items() if self.is_enabled(k)}
        return self._tab_plugins.copy()
    
    def get_menu_extensions(self, enabled_only: bool = True) -> Dict[str, Type[Any]]:
        """Get plugin classes that implement MenuExtension."""
        if enabled_only:
            return {k: v for k, v in self._menu_plugins.items() if self.is_enabled(k)}
        return self._menu_plugins.copy()
    
    def get_status_extensions(self, enabled_only: bool = True) -> Dict[str, Type[Any]]:
        """Get plugin classes that implement StatusExtension."""
        if enabled_only:
            return {k: v for k, v in self._status_plugins.items() if self.is_enabled(k)}
        return self._status_plugins.copy()
    
    def get_toolbar_extensions(self, enabled_only: bool = True) -> Dict[str, Type[Any]]:
        """Get plugin classes that implement ToolbarExtension."""
        if enabled_only:
            return {k: v for k, v in self._toolbar_plugins.items() if self.is_enabled(k)}
        return self._toolbar_plugins.copy()
    
    def get_service_extensions(self, enabled_only: bool = True) -> Dict[str, Type[Any]]:
        """Get plugin classes that implement ServiceExtension."""
        if enabled_only:
            return {k: v for k, v in self._service_plugins.items() if self.is_enabled(k)}
        return self._service_plugins.copy()
    
    def get_event_subscriber_extensions(self, enabled_only: bool = True) -> Dict[str, Type[Any]]:
        """Get plugin classes that implement EventSubscriberExtension."""
        if enabled_only:
            return {k: v for k, v in self._event_subscriber_plugins.items() if self.is_enabled(k)}
        return self._event_subscriber_plugins.copy()
    
    # =========================================================================
    # Event Bus
    # =========================================================================
    
    def publish_event(self, event_name: str, event_data: Dict[str, Any] = None) -> None:
        """Publish an event to all subscribed plugins.
        
        Args:
            event_name: Name of the event
            event_data: Optional data associated with the event

        Notes:
            This is synchronous. If a subscriber is slow, it will slow the publisher.
            For best-effort non-blocking delivery, use publish_event_async().
            UI-touching callbacks must marshal back to the Qt main thread.
        """
        if event_data is None:
            event_data = {}
        
        subscribers = self.get_event_subscriber_extensions(enabled_only=True)
        
        for plugin_name, plugin_class in subscribers.items():
            try:
                # Try to get instance first (v4.0.0)
                try:
                    instance = self.get_plugin_instance(plugin_name)
                    subscriptions = instance.get_event_subscriptions()
                except (ValueError, AttributeError):
                    # Fallback to classmethod (legacy)
                    subscriptions = plugin_class.get_event_subscriptions()
                
                if event_name in subscriptions:
                    callback = subscriptions[event_name]
                    callback(event_data)
            except Exception as e:
                logger.error(f"Error delivering event '{event_name}' to '{plugin_name}': {e}")

    def publish_event_async(self, event_name: str, event_data: Dict[str, Any] = None) -> List["Future[None]"]:
        """Publish an event asynchronously to subscribed plugins (opt-in).

        This prevents slow subscribers from blocking the caller. Callbacks are
        executed on a thread pool. Any UI work must marshal back to the Qt thread.
        """
        if event_data is None:
            event_data = {}

        subscribers = self.get_event_subscriber_extensions(enabled_only=True)
        executor = self._get_event_executor()
        futures: List[Future] = []

        for plugin_name, plugin_class in subscribers.items():
            try:
                try:
                    instance = self.get_plugin_instance(plugin_name)
                    subscriptions = instance.get_event_subscriptions()
                except (ValueError, AttributeError):
                    subscriptions = plugin_class.get_event_subscriptions()

                if event_name not in subscriptions:
                    continue

                callback = subscriptions[event_name]

                def _run(cb=callback, data=event_data, name=plugin_name, ev=event_name):
                    try:
                        cb(data)
                    except Exception as e:
                        logger.error("Error delivering async event '%s' to '%s': %s", ev, name, e)

                futures.append(executor.submit(_run))
            except Exception as e:
                logger.error("Error scheduling event '%s' to '%s': %s", event_name, plugin_name, e)

        return futures


# Global plugin registry instance
# Note: Container should be set via set_container() before instantiating plugins
plugin_registry = PluginRegistry()


__all__ = ['PluginRegistry', 'plugin_registry']