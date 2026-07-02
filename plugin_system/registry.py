"""
Plugin registry system for managing discovered and loaded plugins.

The registry maintains both plugin classes (for compatibility) and 
plugin instances (for the new instance-based architecture).
"""

from __future__ import annotations

import inspect
import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Optional, List, Dict, Tuple, Type, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from ..app.services.container import ServiceContainer
    from .interfaces import IServiceContainer, ISettingsService

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
    IServiceContainer,
    ISettingsService,
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


def _create_prefixed_plugin(original_class: Type[Any], platform_prefix: str) -> Type[Any]:
    """Create a wrapper plugin class with a prefixed plugin_name."""
    original_name = getattr(original_class, 'plugin_name', None)
    if not original_name or original_name == "Unnamed Plugin":
        original_name = original_class.__name__

    original_title = getattr(original_class, 'tab_title', original_name)

    prefixed_name = f"{platform_prefix} {original_name}"
    prefixed_title = f"{platform_prefix} {original_title}"

    new_class = type(
        f"CrossPlatform_{original_class.__name__}",
        (original_class,),
        {
            'plugin_name': prefixed_name,
            'tab_title': prefixed_title,
            '_original_tab_name': original_title,
            '_is_cross_platform': True,
        }
    )
    return new_class


def _check_implements_interface(plugin_class: Type[Any], interface: Type) -> bool:
    """Check if a plugin class implements an interface.

    Protocol types don't work with issubclass() reliably for classes, so we use
    the centralized ExtensionPoint registry with a fallback.
    """
    from .extensions import get_extension_point_by_interface

    ep = get_extension_point_by_interface(interface)
    if ep:
        return ep.check_implements(plugin_class)

    # Fallback: try ABC-style check (best-effort)
    try:
        if isinstance(interface, type) and issubclass(plugin_class, interface):
            return True
    except TypeError:
        pass
    return False
def _get_platform_prefix(supported_platforms: List[str]) -> str:
    """Determine the platform prefix for display/registration name mapping."""
    if supported_platforms:
        sp = supported_platforms[0].lower()
        if "win" in sp:
            return "[Win]"
        elif "linux" in sp:
            return "[Linux]"
        elif "darwin" in sp or "mac" in sp:
            return "[macOS]"
        else:
            return f"[{supported_platforms[0].capitalize()}]"
    return "[XPlatform]"


class PluginRegistry:
    """Registry for managing discovered plugins.
    
    Now supports instance-based plugins with ServiceContainer injection.
    Plugin classes are still registered, but instances are created on-demand.
    
    Supports multiple extension interfaces:
    - TabExtension: Plugins that provide a tab widget
    - MenuExtension: Plugins that contribute menu items
    - StatusExtension: Plugins that contribute status bar widgets
    - ToolbarExtension: Plugins that contribute toolbar actions
    - ServiceExtension: Plugins that provide background services
    - EventSubscriberExtension: Plugins that subscribe to events
    """

    def __init__(self, container: Optional[IServiceContainer | ServiceContainer] = None) -> None:
        """Initialize the registry.
        
        Args:
            container: Optional ServiceContainer for instantiating plugins.
                       Can be set later via set_container().
        """
        self._container = container
        
        # Main plugin registry (by name) - stores CLASSES
        self._plugins: Dict[str, Type[Any]] = {}
        self._core_plugins: Dict[str, Type[Any]] = {}
        self._external_plugins: Dict[str, Type[Any]] = {}
        self._disabled_plugins: set = set()
        
        # Plugin instances cache
        self._plugin_instances: Dict[str, Any] = {}
        self._lock = threading.Lock()

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
        
        # Categorized plugin map for generic iterations
        self._extension_category_maps = {
            "Tab": self._tab_plugins,
            "Menu": self._menu_plugins,
            "Status": self._status_plugins,
            "Toolbar": self._toolbar_plugins,
            "Service": self._service_plugins,
            "Events": self._event_subscriber_plugins,
        }
        
        # Rejected plugins tracking
        self._rejected_plugins: Dict[str, Tuple[Type[Any], str]] = {}
    
    def set_container(self, container: IServiceContainer | ServiceContainer) -> None:
        """Set the service container for plugin instantiation.
        
        Args:
            container: The application's service container
        """
        with self._lock:
            self._container = container
            # Clear instance cache when container changes
            self._plugin_instances.clear()

    def register_plugin(self, plugin_class: Type[Any], is_core: bool = False) -> None:
        """Register a plugin class in the registry.

        Args:
            plugin_class: The plugin class to register
            is_core: Whether this is a core plugin
        """
        with self._lock:
            # Get plugin name - check for non-default values
            plugin_name = getattr(plugin_class, 'plugin_name', None)
            if not plugin_name or plugin_name == "Unnamed Plugin":
                plugin_name = plugin_class.__name__

            # Check if in single plugin mode and filter
            from ..app.utils.imports import get_platforms_constants
            constants = get_platforms_constants()
            if getattr(constants, "SINGLE_PLUGIN_MODE", False):
                single_name = getattr(constants, "SINGLE_PLUGIN_NAME", "")
                if single_name:
                    single_name_lower = single_name.lower().strip()
                    class_name = plugin_class.__name__.lower()
                    curr_name = getattr(plugin_class, 'plugin_name', '').lower()
                    curr_title = getattr(plugin_class, 'tab_title', '').lower()
                    
                    if (single_name_lower != class_name and 
                        single_name_lower != curr_name and 
                        single_name_lower != curr_title and 
                        single_name_lower not in class_name and 
                        single_name_lower not in curr_name and 
                        single_name_lower not in curr_title):
                        logger.debug(f"Skipping plugin '{plugin_name}' in single plugin mode (target: '{single_name}')")
                        return
                else:
                    if len(self._plugins) >= 1:
                        logger.debug(f"Skipping plugin '{plugin_name}' in single plugin mode (already registered a plugin)")
                        return

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
                # Determine platform prefix
                platform_prefix = _get_platform_prefix(supported_platforms)

                plugin_class = _create_prefixed_plugin(plugin_class, platform_prefix)
                plugin_name = plugin_class.plugin_name
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

    def get_registered_name(self, plugin_class: Type[Any]) -> str:
        """Get the name this plugin class will be registered under."""
        name = getattr(plugin_class, 'plugin_name', None)
        if not name or name == "Unnamed Plugin":
            name = plugin_class.__name__

        show_all = _is_show_all_platforms()
        if hasattr(plugin_class, 'is_compatible'):
            is_compatible = plugin_class.is_compatible()
        else:
            is_compatible = self._check_extension_plugin_compatibility(plugin_class)

        if show_all and not is_compatible:
            supported_platforms = getattr(plugin_class, 'supported_platforms', [])
            platform_prefix = _get_platform_prefix(supported_platforms)
            
            return f"{platform_prefix} {name}"
        
        return name

    def get_plugin_instance(self, name: str) -> Any:
        """Get or create a plugin instance by name.
        
        Creates instances on first access, caches them for reuse.
        
        Args:
            name: Plugin name
            
        Returns:
            Plugin instance
            
        Raises:
            ValueError: If plugin not found or container not set
        """
        with self._lock:
            if name in self._plugin_instances:
                return self._plugin_instances[name]
            
            plugin_class = self._plugins.get(name)
            if not plugin_class:
                raise ValueError(f"Plugin '{name}' not found in registry")
            
            if not self._container:
                raise ValueError("ServiceContainer not set - call set_container() first")
            # Instantiate strict new-architecture plugin directly
            instance = plugin_class(self._container)
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
        with self._lock:
            return name in self._plugin_instances

    def _validate_extension_plugin(self, plugin_class: Type[Any], plugin_name: str) -> List[str]:
        """Validate an extension plugin."""
        errors = []
        
        # Check that plugin has a valid (non-default) name
        pn = getattr(plugin_class, 'plugin_name', None)
        has_valid_name = bool(pn and pn != "Unnamed Plugin")
        if not has_valid_name:
            errors.append("Plugin must define plugin_name")
        
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
        from .extensions import EXTENSION_POINTS
        for ep in EXTENSION_POINTS:
            if ep.name in self._extension_category_maps and ep.check_implements(plugin_class):
                self._extension_category_maps[ep.name][plugin_name] = plugin_class

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
        with self._lock:
            # Clean up all cached instances before clearing
            for name, instance in list(self._plugin_instances.items()):
                if hasattr(instance, '_cleanup_plugin_resources'):
                    try:
                        instance._cleanup_plugin_resources()
                    except Exception as e:
                        logger.error(f"Error cleaning up resources during clear of '{name}': {e}")
            self._plugins.clear()
            self._core_plugins.clear()
            self._external_plugins.clear()
            self._disabled_plugins.clear()
            self._plugin_instances.clear()
            self._version_incompatibilities.clear()
            self._seen_plugins.clear()
            for category_map in self._extension_category_maps.values():
                category_map.clear()
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

    def register_plugin_force(self, name: str, plugin_class: Type[Any]) -> None:
        """Force-register a previously rejected plugin, bypassing version checks.

        Intended for user-initiated overrides (e.g. the plugin management dialog).
        The plugin is added as an external plugin and enabled immediately.

        Args:
            name: Plugin name (must exist in the rejected plugins dict).
            plugin_class: The plugin class to register.

        Raises:
            KeyError: If *name* is not in the rejected plugins list.
        """
        with self._lock:
            if name not in self._rejected_plugins:
                raise KeyError(f"Plugin '{name}' is not in the rejected plugins list")

            self._add_plugin_to_registry(name, plugin_class, is_core=False)
            self.enable_plugin(name)
            del self._rejected_plugins[name]
            self._version_incompatibilities.pop(name, None)
            logger.info(f"Force-registered rejected plugin: {name}")

    # =========================================================================
    # Enable/Disable
    # =========================================================================

    def disable_plugin(self, name: str) -> None:
        """Disable a plugin by name."""
        self._disabled_plugins.add(name)

    def unload_plugin_instance(self, name: str) -> None:
        """Remove a plugin instance from the cache and trigger its framework cleanup."""
        with self._lock:
            instance = self._plugin_instances.pop(name, None)
            if instance is not None:
                if hasattr(instance, '_cleanup_plugin_resources'):
                    try:
                        instance._cleanup_plugin_resources()
                    except Exception as e:
                        logger.error(f"Error cleaning up resources during unload of '{name}': {e}")
                logger.debug(f"Unloaded plugin instance: {name}")

    def enable_plugin(self, name: str) -> None:
        """Enable a plugin by name."""
        self._disabled_plugins.discard(name)

    def is_enabled(self, name: str) -> bool:
        """Check if a plugin is enabled."""
        return name in self._plugins and name not in self._disabled_plugins

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
    
    def _get_plugin_event_subscriptions(self, plugin_name: str, plugin_class: type) -> Optional[Dict[str, Any]]:
        """Get event subscriptions for a plugin if the Events extension is enabled."""
        try:
            if self._container:
                try:
                    settings_svc = self._container.get(ISettingsService)
                except (ValueError, KeyError, TypeError):
                    from ..app.services.settings_service import SettingsService
                    settings_svc = self._container.get(SettingsService)
                if settings_svc and not settings_svc.is_extension_enabled(plugin_name, "Events"):
                    return None
        except Exception:
            pass

        try:
            try:
                instance = self.get_plugin_instance(plugin_name)
                return instance.get_event_subscriptions()
            except (ValueError, AttributeError):
                # Fallback to classmethod (legacy)
                return plugin_class.get_event_subscriptions()
        except Exception:
            return None

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
            subscriptions = self._get_plugin_event_subscriptions(plugin_name, plugin_class)
            if subscriptions and event_name in subscriptions:
                try:
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
            subscriptions = self._get_plugin_event_subscriptions(plugin_name, plugin_class)
            if not subscriptions or event_name not in subscriptions:
                continue

            try:
                callback = subscriptions[event_name]
    
                def _run(cb=callback, data=event_data, name=plugin_name, ev=event_name):
                    try:
                        # Check if the callback explicitly requests execution on the UI thread
                        run_on_ui = getattr(cb, "_run_on_ui_thread", False) or getattr(getattr(cb, "__func__", None), "_run_on_ui_thread", False)
                        
                        if run_on_ui:
                            # CRITICAL: We check if there is an active Qt application loop running.
                            # If a Qt event loop is active, we MUST marshal the execution back onto the Qt Main Thread.
                            from ..app.qt_bindings import QtCore
                            app = QtCore.QCoreApplication.instance()
                            if app is not None:
                                # Route execution through our Qt main-thread event dispatcher.
                                QtEventDispatcher.get_instance().dispatch(cb, data)
                                return
                                
                        # Otherwise run directly in background thread (Option C / default fallback)
                        cb(data)
                    except Exception as e:
                        logger.error(f"Error delivering async event '{ev}' to '{name}': {e}")
    
                futures.append(executor.submit(_run))
            except Exception as e:
                logger.error(f"Error scheduling event '{event_name}' to '{plugin_name}': {e}")

        return futures


class QtEventDispatcher:
    """Helper to route arbitrary background thread callbacks onto the Qt Main Thread.

    WHY THIS IS NEEDED:
    Qt's UI system is not thread-safe. If any background thread tries to read/write UI widgets, 
    it causes segmentation faults or undefined behavior. To prevent this, this class uses Qt's 
    internal signal/slot event delivery system. When a signal is emitted across thread boundaries, 
    Qt automatically routes it via a QueuedConnection, executing the connected slot (our callback) 
    safely on the thread that created the QObject (which is the Main Thread where this dispatcher 
    is initialized).
    """
    _instance = None

    def __init__(self) -> None:
        from ..app.qt_bindings import QtCore
        
        # We define a helper QObject subclass locally to declare a Qt Signal.
        # This QObject is created on the main thread (during get_instance() lazy initialization).
        class _DispatcherQObject(QtCore.QObject):
            # The signal carries (callable_function, arguments_tuple, keyword_arguments_dict)
            dispatch_signal = QtCore.Signal(object, tuple, dict)

            def __init__(self) -> None:
                super().__init__()
                # The connection is made on the main thread.
                self.dispatch_signal.connect(self._execute)

            def _execute(self, func: Callable, args: tuple, kwargs: dict) -> None:
                # This method executes in the event loop of the Main Thread.
                try:
                    func(*args, **kwargs)
                except Exception as e:
                    logging.getLogger(__name__).error(f"Error executing dispatched callback on Main Thread: {e}", exc_info=True)

        self._qobject = _DispatcherQObject()

    @classmethod
    def get_instance(cls) -> "QtEventDispatcher":
        """Get the singleton event dispatcher instance.

        MUST be called for the first time from the Main GUI Thread (e.g., during app startup)
        to guarantee that the underlying QObject is assigned to the Main Thread event loop.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def dispatch(self, func: Callable, *args: Any, **kwargs: Any) -> None:
        """Post a callback to be executed on the Qt Main Thread.

        Can be safely called from any background thread.
        """
        self._qobject.dispatch_signal.emit(func, args, kwargs)


__all__ = ['PluginRegistry']
