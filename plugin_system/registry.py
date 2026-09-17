"""
Plugin registry system for managing discovered and loaded plugins.

The registry maintains both plugin classes (for compatibility) and 
plugin instances (for the new instance-based architecture).
"""

from __future__ import annotations

import inspect
import logging
import threading
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from types import MappingProxyType
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
from .identity import UNNAMED_PLUGIN, plugin_display_name, plugin_identity, plugin_ui_label
from .dependencies import (
    resolve_dependency_graph,
    transitive_dependents,
)
from ..app.utils.imports import get_platforms_constants

logger = logging.getLogger(__name__)

# Bound queued async event deliveries per plugin (drop oldest when exceeded).
MAX_PENDING_EVENTS_PER_PLUGIN = 32


def _is_show_all_platforms() -> bool:
    """Check if show all platforms mode is enabled (cached per discovery pass)."""
    cached = getattr(_is_show_all_platforms, "_cache", None)
    if cached is not None:
        return cached
    try:
        from ..app.utils.admin import is_show_all_platforms
        result = is_show_all_platforms()
        if result:
            logger.info("Show all platforms mode is ENABLED - bypassing platform filtering")
    except Exception as e:
        logger.debug(f"Could not check show_all_platforms flag: {e}")
        result = False
    _is_show_all_platforms._cache = result  # type: ignore[attr-defined]
    return result


def clear_registration_caches() -> None:
    """Clear per-discovery-pass caches used during plugin registration."""
    if hasattr(_is_show_all_platforms, "_cache"):
        delattr(_is_show_all_platforms, "_cache")


def _create_prefixed_plugin(original_class: Type[Any], platform_prefix: str) -> Type[Any]:
    """Wrap an off-platform plugin: prefix tab chrome, keep plugin_name and id."""
    original_title = getattr(original_class, "tab_title", None)
    if not original_title or original_title == "Unnamed Tab":
        original_title = plugin_display_name(original_class)
    prefixed_title = f"{platform_prefix} {original_title}"
    original_id = plugin_identity(original_class)

    return type(
        f"CrossPlatform_{original_class.__name__}",
        (original_class,),
        {
            "plugin_id": original_id,
            "tab_title": prefixed_title,
            "_show_all_prefix": platform_prefix,
            "_is_cross_platform": True,
        },
    )


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
    """Determine the Show-All display prefix for an off-platform plugin."""
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
        
        # Plugin instances cache (keyed by plugin_id)
        self._plugin_instances: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._generations: Dict[str, int] = {}
        self._in_flight: Dict[str, Future] = {}
        self._tls = threading.local()

        # Optional async event delivery executor (opt-in)
        self._event_executor: Optional[ThreadPoolExecutor] = None
        self._event_executor_lock = threading.Lock()
        self._pending_events: Dict[str, deque] = {}
        self._event_pending_lock = threading.Lock()

        # Dependency graph (plugin_id -> provider ids); filled by finalize_dependency_graph
        self._dependency_edges: Dict[str, List[str]] = {}
        self._startup_order: List[str] = []
        self._graph_errors: Dict[str, str] = {}
        
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
        self._pending_replaced_instances: List[Tuple[str, Any]] = []

        # Lifecycle subscribers (IPluginLifecycle)
        self._lifecycle_subscribers: List[Any] = []
    
    def set_container(self, container: IServiceContainer | ServiceContainer) -> None:
        """Set the service container for plugin instantiation."""
        with self._lock:
            self._container = container
            unloaded = list(self._plugin_instances.keys())
            self._plugin_instances.clear()
        if unloaded:
            self._notify_plugins_unloaded(unloaded)

    def subscribe_lifecycle(self, subscriber: Any) -> None:
        """Register a lifecycle event subscriber."""
        if subscriber not in self._lifecycle_subscribers:
            self._lifecycle_subscribers.append(subscriber)

    def unsubscribe_lifecycle(self, subscriber: Any) -> None:
        """Remove a lifecycle subscriber."""
        if subscriber in self._lifecycle_subscribers:
            self._lifecycle_subscribers.remove(subscriber)

    def _notify_plugins_unloaded(self, plugin_names: List[str]) -> None:
        if not plugin_names:
            return
        for subscriber in list(self._lifecycle_subscribers):
            try:
                subscriber.on_plugins_unloaded(plugin_names)
            except Exception as e:
                logger.error(f"Lifecycle subscriber error on_plugins_unloaded: {e}")

    def _notify_plugins_discovered(self, plugin_names: List[str]) -> None:
        if not plugin_names:
            return
        for subscriber in list(self._lifecycle_subscribers):
            try:
                subscriber.on_plugins_discovered(plugin_names)
            except Exception as e:
                logger.error(f"Lifecycle subscriber error on_plugins_discovered: {e}")

    def _notify_plugin_state_changed(self, plugin_name: str, enabled: bool) -> None:
        for subscriber in list(self._lifecycle_subscribers):
            try:
                subscriber.on_plugin_state_changed(plugin_name, enabled)
            except Exception as e:
                logger.error(f"Lifecycle subscriber error on_plugin_state_changed: {e}")

    def register_plugin(self, plugin_class: Type[Any], is_core: bool = False) -> None:
        """Register a plugin class in the registry.

        Args:
            plugin_class: The plugin class to register
            is_core: Whether this is a core plugin
        """
        discovered: Optional[str] = None
        with self._lock:
            plugin_name = plugin_identity(plugin_class)

            # Check if in single plugin mode and filter
            constants = get_platforms_constants()
            if getattr(constants, "SINGLE_PLUGIN_MODE", False):
                single_name = getattr(constants, "SINGLE_PLUGIN_NAME", "")
                if single_name:
                    single_name_lower = single_name.lower().strip()
                    class_name = plugin_class.__name__.lower()
                    curr_name = getattr(plugin_class, 'plugin_name', '').lower()
                    curr_title = getattr(plugin_class, 'tab_title', '').lower()
                    curr_id = plugin_identity(plugin_class).lower()
                    
                    if (single_name_lower != class_name and 
                        single_name_lower != curr_name and 
                        single_name_lower != curr_title and 
                        single_name_lower != curr_id and
                        single_name_lower not in class_name and 
                        single_name_lower not in curr_name and 
                        single_name_lower not in curr_title and
                        single_name_lower not in curr_id):
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
                plugin_name = plugin_identity(plugin_class)
                logger.info(
                    f"Loading cross-platform plugin '{plugin_ui_label(plugin_class)}' "
                    f"(supported: {supported_platforms})"
                )

            # Check version compatibility
            if not self._check_plugin_compatibility(plugin_class, plugin_name):
                return

            # Handle name conflicts
            if not self._handle_plugin_conflicts(plugin_name, is_core):
                return

            # Register the plugin class (maps only; notify after releasing the lock)
            self._add_plugin_to_registry(plugin_name, plugin_class, is_core)
            self._apply_default_disabled_state(plugin_class, plugin_name)
            self._seen_plugins.add(plugin_name)
            discovered = plugin_name

            logger.debug(f"Registered plugin: {plugin_name} (core={is_core})")

        self._flush_replaced_instances()
        if discovered is not None:
            self._notify_plugins_discovered([discovered])

    def get_registered_name(self, plugin_class: Type[Any]) -> str:
        """Get the identity this plugin class will be registered under."""
        return plugin_identity(plugin_class)

    def resolve_plugin_key(self, name_or_id: str) -> Optional[str]:
        """Resolve a plugin_id or unique display name to a registry key.

        Raises:
            ValueError: If *name_or_id* is an ambiguous display name.
        """
        with self._lock:
            return self._resolve_plugin_key_unlocked(name_or_id)

    def _resolve_plugin_key_unlocked(self, name_or_id: str) -> Optional[str]:
        if name_or_id in self._plugins:
            return name_or_id
        matches = []
        for pid, cls in self._plugins.items():
            if plugin_display_name(cls) == name_or_id:
                matches.append(pid)
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValueError(
                f"Ambiguous plugin display name {name_or_id!r}; use plugin_id "
                f"(matches: {', '.join(sorted(matches))})"
            )
        return None

    def _construction_stack(self) -> List[str]:
        stack = getattr(self._tls, "stack", None)
        if stack is None:
            stack = []
            self._tls.stack = stack
        return stack

    def _bump_generation(self, name: str) -> int:
        nxt = self._generations.get(name, 0) + 1
        self._generations[name] = nxt
        return nxt

    def _cleanup_instance(self, name: str, instance: Any) -> None:
        if instance is None:
            return
        if hasattr(instance, "_cleanup_plugin_resources"):
            try:
                instance._cleanup_plugin_resources()
            except Exception as e:
                logger.error(
                    f"Error cleaning up resources of '{name}': {e}"
                )

    def get_plugin_instance(self, name: str) -> Any:
        """Get or create a plugin instance by id or unique display name.

        Construction is single-flight per plugin and runs *outside* the
        registry lock. Publication is refused if the plugin's generation
        changed, the class was replaced, or the name was unregistered.
        Re-entrant or cyclic construction on the same thread raises.
        """
        wait_future: Optional[Future] = None
        construct_future: Optional[Future] = None
        plugin_class: Optional[Type[Any]] = None
        container = None
        generation = 0
        key = name

        with self._lock:
            resolved = self._resolve_plugin_key_unlocked(name)
            if not resolved:
                raise ValueError(f"Plugin '{name}' not found in registry")
            key = resolved
            cached = self._plugin_instances.get(key)
            if cached is not None:
                return cached

            stack = self._construction_stack()
            if key in stack:
                path = " -> ".join(stack + [key])
                raise RuntimeError(
                    f"Re-entrant or cyclic plugin construction: {path}"
                )

            inflight = self._in_flight.get(key)
            if inflight is not None:
                wait_future = inflight
            else:
                plugin_class = self._plugins.get(key)
                container = self._container
                if not plugin_class:
                    raise ValueError(f"Plugin '{key}' not found in registry")
                if not container:
                    raise ValueError(
                        "ServiceContainer not set - call set_container() first"
                    )
                generation = self._generations.get(key, 0)
                construct_future = Future()
                self._in_flight[key] = construct_future

        if wait_future is not None:
            return wait_future.result()

        assert construct_future is not None and plugin_class is not None
        stack = self._construction_stack()
        stack.append(key)
        discarded = None
        published = None
        error: Optional[BaseException] = None
        try:
            instance = plugin_class(container)
        except BaseException as exc:
            error = exc
            instance = None
        finally:
            if stack and stack[-1] == key:
                stack.pop()

        with self._lock:
            self._in_flight.pop(key, None)
            if error is not None:
                if not construct_future.done():
                    construct_future.set_exception(error)
            else:
                existing = self._plugin_instances.get(key)
                current_gen = self._generations.get(key, 0)
                registered_class = self._plugins.get(key)
                if existing is not None:
                    discarded = instance
                    published = existing
                elif (
                    current_gen != generation
                    or registered_class is not plugin_class
                    or key not in self._plugins
                ):
                    discarded = instance
                    error = ValueError(
                        f"Plugin '{key}' construction was invalidated"
                    )
                else:
                    self._plugin_instances[key] = instance
                    published = instance
                    logger.debug(f"Created instance for plugin: {key}")
                if error is not None:
                    if not construct_future.done():
                        construct_future.set_exception(error)
                elif not construct_future.done():
                    construct_future.set_result(published)

        if discarded is not None:
            self._cleanup_instance(key, discarded)
        if error is not None:
            raise error
        return published
    
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
        return self.peek_plugin_instance(name) is not None

    def peek_plugin_instance(self, name: str) -> Optional[Any]:
        """Return a cached instance without constructing a replacement."""
        with self._lock:
            try:
                key = self._resolve_plugin_key_unlocked(name) or name
            except ValueError:
                return None
            return self._plugin_instances.get(key)

    def _validate_extension_plugin(self, plugin_class: Type[Any], plugin_name: str) -> List[str]:
        """Validate an extension plugin."""
        errors = []
        
        # Check that plugin has a valid (non-default) name
        pn = getattr(plugin_class, 'plugin_name', None)
        has_valid_name = bool(pn and pn != UNNAMED_PLUGIN)
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

        # Local import keeps registry -> base off the module import graph.
        from .base import _normalize_platform_name_for_matching

        current_platform = platform.system()
        supported_platforms = getattr(plugin_class, 'supported_platforms', [])
        
        if not supported_platforms:
            return True
        
        # platform.system() returns "Darwin" while plugins declare "macOS", so
        # both sides go through the same normalizer BaseTabPlugin uses.
        normalized_current = _normalize_platform_name_for_matching(current_platform)
        normalized_supported = {
            _normalize_platform_name_for_matching(p) for p in supported_platforms
        }
        
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
        """Handle plugin_id conflicts with an explicit replacement rule.

        Same identity: core replaces external; a second external is skipped.
        Distinct identities with the same display name may both register.
        """
        if plugin_name not in self._plugins:
            return True
        
        existing_is_core = plugin_name in self._core_plugins
        if existing_is_core and not is_core:
            logger.warning(
                f"Skipping plugin '{plugin_name}' - identity already used by a core plugin"
            )
            return False
        
        if not existing_is_core and is_core:
            existing = self._plugins.get(plugin_name)
            label = plugin_ui_label(existing) if existing is not None else plugin_name
            logger.info(f"Replacing external plugin '{label}' with core plugin")
            if plugin_name in self._external_plugins:
                del self._external_plugins[plugin_name]
            self._uncategorize_plugin(plugin_name)
            self._bump_generation(plugin_name)
            dropped = self._plugin_instances.pop(plugin_name, None)
            if dropped is not None:
                self._pending_replaced_instances.append((plugin_name, dropped))
            return True

        logger.warning(
            f"Skipping plugin '{plugin_name}' - identity already used by another plugin"
        )
        return False

    def _add_plugin_to_registry(self, plugin_name: str, plugin_class: Type[Any], is_core: bool) -> None:
        """Add plugin to the appropriate registry dictionaries.

        Callers must invoke ``_notify_plugins_discovered`` *after* releasing
        ``_lock``. Lifecycle callbacks must not run while the registry lock
        is held (subscribers may query the instance cache).
        """
        self._plugins[plugin_name] = plugin_class
        if plugin_name not in self._generations:
            self._generations[plugin_name] = 0
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

    def _uncategorize_plugin(self, plugin_name: str) -> None:
        """Remove a plugin from every extension category map."""
        for mapping in self._extension_category_maps.values():
            mapping.pop(plugin_name, None)

    def _flush_replaced_instances(self) -> None:
        pending = self._pending_replaced_instances
        self._pending_replaced_instances = []
        for name, instance in pending:
            self._cleanup_instance(name, instance)

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

    def get_all_plugins(self) -> MappingProxyType:
        """Get a read-only view of all registered plugin classes."""
        return MappingProxyType(self._plugins)

    def get_core_plugins(self) -> MappingProxyType:
        """Get a read-only view of core plugin classes."""
        return MappingProxyType(self._core_plugins)

    def get_external_plugins(self) -> MappingProxyType:
        """Get a read-only view of external plugin classes."""
        return MappingProxyType(self._external_plugins)

    def get_plugin(self, name: str) -> Optional[Type[Any]]:
        """Get a specific plugin class by plugin_id or unique display name."""
        try:
            key = self.resolve_plugin_key(name)
        except ValueError:
            raise
        if key is None:
            return None
        return self._plugins.get(key)

    def list_plugin_names(self) -> List[str]:
        """Return registry keys (``plugin_id`` values) for all registered plugins."""
        return list(self._plugins.keys())

    def clear(self) -> None:
        """Clear all registered plugins and cached instances."""
        with self._lock:
            instances = list(self._plugin_instances.items())
            in_flight_names = list(self._in_flight.keys())
            for name in set(
                list(self._generations)
                + list(self._plugin_instances)
                + in_flight_names
            ):
                self._bump_generation(name)
            self._plugin_instances.clear()
            unloaded_names = [name for name, _ in instances]
            self._plugins.clear()
            self._core_plugins.clear()
            self._external_plugins.clear()
            self._disabled_plugins.clear()
            self._version_incompatibilities.clear()
            self._seen_plugins.clear()
            for category_map in self._extension_category_maps.values():
                category_map.clear()
            self._rejected_plugins.clear()
            self._dependency_edges.clear()
            self._startup_order.clear()
            self._graph_errors.clear()

        pending_to_cancel = self._take_all_pending_event_futures()
        for fut in pending_to_cancel:
            fut.cancel()

        # Cleanup outside the lock (may wait on QThreads / touch UI)
        for name, instance in instances:
            self._cleanup_instance(name, instance)

        self._shutdown_event_executor()
        if unloaded_names:
            self._notify_plugins_unloaded(unloaded_names)

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
    
    def get_rejected_plugins(self) -> MappingProxyType:
        """Get a read-only view of plugins that were rejected during registration."""
        return MappingProxyType(self._rejected_plugins)

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
        self._register_rejected_plugin(name, plugin_class, enable=True)

    def register_rejected_plugin(self, name: str, plugin_class: Type[Any]) -> None:
        """Bypass version checks without enabling. Activation is the caller's job."""
        self._register_rejected_plugin(name, plugin_class, enable=False)

    def _register_rejected_plugin(
        self, name: str, plugin_class: Type[Any], *, enable: bool
    ) -> None:
        with self._lock:
            if name not in self._rejected_plugins:
                raise KeyError(f"Plugin '{name}' is not in the rejected plugins list")

            self._add_plugin_to_registry(name, plugin_class, is_core=False)
            if enable:
                self._disabled_plugins.discard(name)
            else:
                self._disabled_plugins.add(name)
            del self._rejected_plugins[name]
            self._version_incompatibilities.pop(name, None)
            logger.info(
                f"Force-registered rejected plugin: {plugin_ui_label(plugin_class)}"
            )

        self._notify_plugins_discovered([name])
        if enable:
            self._notify_plugin_state_changed(name, True)

    # =========================================================================
    # Enable/Disable
    # =========================================================================

    def unload_plugin_instance(self, name: str) -> None:
        """Remove a plugin instance from the cache and trigger its framework cleanup.

        Bumps the plugin generation, cancels queued async events, then cleans
        the object *outside* the registry lock.
        """
        try:
            key = self.resolve_plugin_key(name) or name
        except ValueError:
            key = name
        with self._lock:
            self._bump_generation(key)
            instance = self._plugin_instances.pop(key, None)
        pending = self._take_pending_event_futures(key)
        for fut in pending:
            fut.cancel()

        if instance is None:
            return

        self._cleanup_instance(key, instance)
        logger.debug(f"Unloaded plugin instance: {key}")
        self._notify_plugins_unloaded([key])

    def enable_plugin(self, name: str) -> None:
        """Enable a plugin by id or unique display name."""
        key = self.resolve_plugin_key(name) or name
        self._disabled_plugins.discard(key)
        self._notify_plugin_state_changed(key, True)

    def disable_plugin(self, name: str) -> None:
        """Disable a plugin by id or unique display name."""
        key = self.resolve_plugin_key(name) or name
        self._disabled_plugins.add(key)
        self._notify_plugin_state_changed(key, False)

    def is_enabled(self, name: str) -> bool:
        """Check if a plugin is enabled."""
        try:
            key = self.resolve_plugin_key(name)
        except ValueError:
            return False
        if key is None:
            return False
        return key in self._plugins and key not in self._disabled_plugins

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
        return MappingProxyType(self._tab_plugins)
    
    def get_menu_extensions(self, enabled_only: bool = True) -> Dict[str, Type[Any]]:
        """Get plugin classes that implement MenuExtension."""
        if enabled_only:
            return {k: v for k, v in self._menu_plugins.items() if self.is_enabled(k)}
        return MappingProxyType(self._menu_plugins)
    
    def get_status_extensions(self, enabled_only: bool = True) -> Dict[str, Type[Any]]:
        """Get plugin classes that implement StatusExtension."""
        if enabled_only:
            return {k: v for k, v in self._status_plugins.items() if self.is_enabled(k)}
        return MappingProxyType(self._status_plugins)
    
    def get_toolbar_extensions(self, enabled_only: bool = True) -> Dict[str, Type[Any]]:
        """Get plugin classes that implement ToolbarExtension."""
        if enabled_only:
            return {k: v for k, v in self._toolbar_plugins.items() if self.is_enabled(k)}
        return MappingProxyType(self._toolbar_plugins)
    
    def get_service_extensions(self, enabled_only: bool = True) -> Dict[str, Type[Any]]:
        """Get plugin classes that implement ServiceExtension."""
        if enabled_only:
            return {k: v for k, v in self._service_plugins.items() if self.is_enabled(k)}
        return MappingProxyType(self._service_plugins)
    
    def get_event_subscriber_extensions(self, enabled_only: bool = True) -> Dict[str, Type[Any]]:
        """Get plugin classes that implement EventSubscriberExtension."""
        if enabled_only:
            return {k: v for k, v in self._event_subscriber_plugins.items() if self.is_enabled(k)}
        return MappingProxyType(self._event_subscriber_plugins)

    def get_startup_order(self) -> List[str]:
        """Provider-first plugin ids from the last ``finalize_dependency_graph``."""
        if self._startup_order:
            return list(self._startup_order)
        return self.list_plugin_names()

    def get_shutdown_order(self) -> List[str]:
        """Consumer-first plugin ids."""
        return list(reversed(self.get_startup_order()))

    def get_dependency_edges(self) -> Dict[str, List[str]]:
        return {k: list(v) for k, v in self._dependency_edges.items()}

    def get_graph_errors(self) -> Dict[str, str]:
        return dict(self._graph_errors)

    def get_enabled_dependents(self, name: str) -> List[str]:
        """Enabled plugins that transitively depend on *name*, consumers first."""
        try:
            key = self.resolve_plugin_key(name)
        except ValueError:
            return []
        if key is None:
            return []
        deps = set(transitive_dependents(key, self._dependency_edges))
        order = [pid for pid in self.get_shutdown_order() if pid in deps and self.is_enabled(pid)]
        extra = [pid for pid in deps if pid not in order and self.is_enabled(pid)]
        return order + extra

    def reject_registered_plugin(self, name: str, reason: str) -> None:
        """Move a registered plugin to the rejected list and drop its maps."""
        with self._lock:
            plugin_class = self._plugins.pop(name, None)
            if plugin_class is None:
                return
            self._core_plugins.pop(name, None)
            self._external_plugins.pop(name, None)
            self._disabled_plugins.add(name)
            for category_map in self._extension_category_maps.values():
                category_map.pop(name, None)
            self._rejected_plugins[name] = (plugin_class, reason)
            logger.warning("Rejected plugin '%s': %s", name, reason)
            instance = self._plugin_instances.pop(name, None)
            self._bump_generation(name)

        if instance is not None:
            self._cleanup_instance(name, instance)
            self._notify_plugins_unloaded([name])

    def finalize_dependency_graph(self) -> Dict[str, str]:
        """Resolve dependencies after discovery. Reject missing/cyclic plugins.

        Returns the error map (plugin id -> diagnostic).
        """
        plugins = dict(self.get_all_plugins())
        order, errors, edges = resolve_dependency_graph(plugins)
        self._startup_order = order
        self._dependency_edges = edges
        self._graph_errors = dict(errors)
        for plugin_id, reason in list(errors.items()):
            if plugin_id in self._plugins:
                self.reject_registered_plugin(plugin_id, reason)
        return dict(errors)

    def _take_pending_event_futures(self, name: str) -> List[Future]:
        with self._event_pending_lock:
            q = self._pending_events.pop(name, deque())
            return list(q)

    def _take_all_pending_event_futures(self) -> List[Future]:
        with self._event_pending_lock:
            futures: List[Future] = []
            for q in self._pending_events.values():
                futures.extend(q)
            self._pending_events.clear()
            return futures

    def _track_event_future(self, name: str, fut: Future) -> None:
        with self._event_pending_lock:
            q = self._pending_events.setdefault(name, deque())
            while len(q) >= MAX_PENDING_EVENTS_PER_PLUGIN:
                old = q.popleft()
                old.cancel()
                logger.warning(
                    "Dropped oldest queued event for '%s' (pending cap %s)",
                    name,
                    MAX_PENDING_EVENTS_PER_PLUGIN,
                )
            q.append(fut)

        def _done(finished: Future, plugin_id: str = name) -> None:
            with self._event_pending_lock:
                pending = self._pending_events.get(plugin_id)
                if pending is None:
                    return
                try:
                    pending.remove(finished)
                except ValueError:
                    pass

        fut.add_done_callback(_done)

    def _event_delivery_allowed(self, name: str, generation: int) -> bool:
        with self._lock:
            if self._generations.get(name, 0) != generation:
                return False
            if name not in self._plugin_instances:
                return False
            if name in self._disabled_plugins:
                return False
            return True
    
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
                    settings_svc = None
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

        Callbacks run on a bounded thread pool. Delivery is dropped if the
        plugin's generation changed, it was disabled, or its instance was
        unloaded before the worker ran. UI work must marshal to the main
        thread via ``IUIEventLoop``.
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
                with self._lock:
                    generation = self._generations.get(plugin_name, 0)

                def _run(
                    cb=callback,
                    data=event_data,
                    name=plugin_name,
                    ev=event_name,
                    gen=generation,
                ):
                    if not self._event_delivery_allowed(name, gen):
                        return
                    try:
                        run_on_ui = getattr(cb, "_run_on_ui_thread", False) or getattr(
                            getattr(cb, "__func__", None), "_run_on_ui_thread", False
                        )

                        if run_on_ui:
                            event_loop = self._get_ui_event_loop()
                            if event_loop is not None:
                                event_loop.invoke_on_main(cb, data)
                                return

                        cb(data)
                    except Exception as e:
                        logger.error(f"Error delivering async event '{ev}' to '{name}': {e}")

                fut = executor.submit(_run)
                self._track_event_future(plugin_name, fut)
                futures.append(fut)
            except Exception as e:
                logger.error(f"Error scheduling event '{event_name}' to '{plugin_name}': {e}")

        return futures

    def _get_ui_event_loop(self) -> Any:
        """Get IUIEventLoop from container if registered."""
        if self._container is None:
            return None
        try:
            from ..app.ui.abstractions.event_loop import IUIEventLoop
            return self._container.get(IUIEventLoop)
        except Exception:
            return None


__all__ = ['PluginRegistry', 'clear_registration_caches']
