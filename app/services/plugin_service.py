"""
Plugin service for managing plugin discovery and registry access.

This module provides the PluginService class which wraps a PluginRegistry
instance, enabling dependency injection and easier testing. It handles:
- Plugin discovery from multiple sources
- Plugin registration and state management
- Access to plugin registry methods

The PluginRegistry is an internal detail of this service. UI code should
use PluginService only.
"""

from __future__ import annotations

import logging
import os
import sys
import importlib.util
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type, TYPE_CHECKING

from ...plugin_system.registry import PluginRegistry
from ...plugin_system.base import BaseTabPlugin
from ...plugin_system.identity import plugin_ui_label
from ...plugin_system.dependencies import declared_dependencies, resolve_dep_token
from ...plugin_system.discovery import PluginDiscovery
from ...plugin_system.sources import PluginSource
from ..utils.paths import parent_has_gui_plugin_dirs

if TYPE_CHECKING:
    from .settings_service import SettingsService
    from ...plugin_system.interfaces import IServiceContainer

logger = logging.getLogger(__name__)


def _ensure_parent_project_on_path() -> None:
    """Ensure the parent project root (sibling to GUI/) is on sys.path so app_plugins/platforms can be imported.

    Main plugin loading uses 'from app_plugins.core_plugins import ...' and
    'from platforms.core_plugins import ...', which require the repo root on path.
    - When not standalone: always add parent so plugins work regardless of cwd.
    - When standalone: add parent only if app_plugins or platforms exists there,
      so that running from GUI/ (run.py) with the full repo layout still loads
      native plugins (e.g. Linux app_plugins core), not just cross-platform dev tabs.
    """
    # This file is at GUI/app/services/plugin_service.py -> 4 levels up = repo root
    current_file = Path(__file__).resolve()
    parent_project = current_file.parent.parent.parent.parent
    if os.environ.get("GUI_STANDALONE_MODE") == "1":
        # In standalone, only add path if the parent has our plugin trees (not an unrelated folder)
        if not parent_has_gui_plugin_dirs(parent_project):
            return
    parent_str = str(parent_project)
    if parent_str not in sys.path:
        sys.path.insert(0, parent_str)


class PluginService:
    """Service for plugin discovery and registry management.

    Owns a PluginRegistry instance. All UI and controller access should go
    through this service when using the ServiceContainer.
    """

    def __init__(
        self,
        settings_service: Optional["SettingsService"] = None,
        registry: Optional[PluginRegistry] = None,
        container: Optional[Any] = None,
    ) -> None:
        """Initialize the plugin service.

        Args:
            settings_service: Optional settings service for plugin state persistence
            registry: Optional PluginRegistry (tests); normally created internally
            container: Optional service container for plugin DI
        """
        self.settings_service = settings_service
        self._registry = registry or PluginRegistry()
        self._discovery_complete = False
        self._startup_dependency_blocks: set[str] = set()
        self._last_activation_error: Optional[str] = None
        if container is not None:
            self.bind_container(container)

    def bind_container(self, container: "IServiceContainer | Any") -> None:
        """Attach the service container to the underlying registry."""
        self._registry.set_container(container)

    # =========================================================================
    # Registry Access Methods (delegating to owned registry)
    # =========================================================================

    def get_all_plugins(self) -> Dict[str, Type[BaseTabPlugin]]:
        """Get all registered plugins."""
        return self._registry.get_all_plugins()

    def get_core_plugins(self) -> Dict[str, Type[BaseTabPlugin]]:
        """Get core plugins only."""
        return self._registry.get_core_plugins()

    def get_external_plugins(self) -> Dict[str, Type[BaseTabPlugin]]:
        """Get external plugins only."""
        return self._registry.get_external_plugins()

    def get_plugin(self, name: str) -> Optional[Type[BaseTabPlugin]]:
        """Get a specific plugin by plugin_id or unique display name."""
        return self._registry.get_plugin(name)

    def plugin_label(self, name_or_id: str) -> str:
        """Display name for INFO logs and UI; falls back to *name_or_id*."""
        try:
            plugin_class = self.get_plugin(name_or_id)
        except ValueError:
            plugin_class = None
        if plugin_class is not None:
            return plugin_ui_label(plugin_class)
        return name_or_id

    def resolve_plugin_key(self, name: str) -> Optional[str]:
        """Resolve a display name or id to the registry key."""
        return self._registry.resolve_plugin_key(name)

    def get_last_activation_error(self) -> Optional[str]:
        return self._last_activation_error

    def get_plugin_instance(self, name: str) -> Any:
        """Get or create a plugin instance by name."""
        return self._registry.get_plugin_instance(name)

    def unload_plugin_instance(self, name: str) -> None:
        """Remove a plugin instance from the cache."""
        self._registry.unload_plugin_instance(name)

    def has_plugin_instance(self, name: str) -> bool:
        """Check if a plugin instance is cached."""
        return self._registry.has_plugin_instance(name)

    def peek_plugin_instance(self, name: str) -> Optional[Any]:
        """Return a cached instance without constructing a replacement."""
        return self._registry.peek_plugin_instance(name)

    def list_plugin_names(self) -> List[str]:
        """Return registry keys (``plugin_id`` values) for all registered plugins."""
        return self._registry.list_plugin_names()

    def register_plugin(self, plugin_class: Type[BaseTabPlugin], is_core: bool = False) -> None:
        """Register a plugin in the registry."""
        self._registry.register_plugin(plugin_class, is_core=is_core)

    def clear(self) -> None:
        """Clear all registered plugins."""
        self._registry.clear()
        self._startup_dependency_blocks.clear()
        self._discovery_complete = False

        self._invalidate_core_plugin_modules()
        try:
            from ...plugin_system.registry import clear_registration_caches
            clear_registration_caches()
        except Exception:
            pass

    def disable_plugin(self, name: str) -> None:
        """Disable a plugin by name."""
        self._startup_dependency_blocks.discard(self.resolve_plugin_key(name) or name)
        self._registry.disable_plugin(name)

    def enable_plugin(self, name: str) -> None:
        """Enable a plugin by name."""
        self._startup_dependency_blocks.discard(self.resolve_plugin_key(name) or name)
        self._registry.enable_plugin(name)

    def _is_requested_enabled(self, name: str) -> bool:
        """Keep temporary startup dependency blocks out of saved user overrides."""
        return name in self._startup_dependency_blocks or self.is_enabled(name)

    def is_enabled(self, name: str) -> bool:
        """Check if a plugin is enabled."""
        return self._registry.is_enabled(name)

    def get_enabled_plugins(self) -> Dict[str, Type[BaseTabPlugin]]:
        """Get all enabled plugins."""
        return self._registry.get_enabled_plugins()

    def get_enabled_dependents(self, name: str) -> List[str]:
        """Enabled plugins that transitively depend on *name* (not including it)."""
        return self._registry.get_enabled_dependents(name)

    def get_startup_order(self) -> List[str]:
        return self._registry.get_startup_order()

    def get_shutdown_order(self) -> List[str]:
        return self._registry.get_shutdown_order()

    def finalize_plugin_graph(self) -> Dict[str, str]:
        """Reject plugins with missing or cyclic dependencies after discovery."""
        errors = self._registry.finalize_dependency_graph()
        if errors:
            logger.warning(
                "Rejected %s plugin(s) due to dependency errors", len(errors)
            )
        return errors

    def _unsatisfied_dependencies(self, name: str) -> List[str]:
        plugin_class = self.get_plugin(name)
        if plugin_class is None:
            return []
        plugins = dict(self._registry.get_all_plugins())
        unsat: List[str] = []
        for token in declared_dependencies(plugin_class):
            dep_id, err = resolve_dep_token(token, plugins)
            if err or dep_id is None or not self.is_enabled(dep_id):
                unsat.append(token)
        return unsat

    def activate_plugin(self, name: str) -> bool:
        """Construct, run ``on_plugin_enabled``, then commit enablement.

        Returns False and leaves the plugin disabled when construction or the
        enable hook fails, or when dependencies are missing/disabled.
        """
        self._last_activation_error = None
        key = self.resolve_plugin_key(name)
        if not key:
            self._last_activation_error = f"Plugin '{name}' not found"
            logger.warning(self._last_activation_error)
            return False
        if self.is_enabled(key) and self.has_plugin_instance(key):
            return True
        unsat = self._unsatisfied_dependencies(key)
        if unsat:
            plugin_class = self.get_plugin(key)
            display = plugin_ui_label(plugin_class) if plugin_class else key
            self._last_activation_error = (
                f"Plugin '{display}' has unsatisfied dependencies: {', '.join(unsat)}"
            )
            logger.error(self._last_activation_error)
            return False
        try:
            instance = self.get_plugin_instance(key)
        except Exception as e:
            self._last_activation_error = str(e)
            logger.error("Failed to construct plugin '%s': %s", key, e)
            try:
                self.unload_plugin_instance(key)
            except Exception:
                pass
            return False
        was_enabled = self.is_enabled(key)
        if not was_enabled:
            self.enable_plugin(key)
        try:
            if hasattr(instance, "on_plugin_enabled"):
                instance.on_plugin_enabled()
        except Exception as e:
            self._last_activation_error = str(e)
            logger.error("Error calling on_plugin_enabled for '%s': %s", key, e)
            self.disable_plugin(key)
            try:
                self.unload_plugin_instance(key)
            except Exception:
                pass
            return False
        display = plugin_ui_label(self.get_plugin(key) or type(instance))
        self.publish_event(
            "plugin_enabled",
            {"plugin_id": key, "plugin_name": display},
        )
        return True

    def deactivate_plugin(self, name: str, *, cascade: bool = True) -> List[str]:
        """Disable a plugin, optionally cascading to enabled dependents.

        Consumers are stopped before providers. Each target gets
        ``on_plugin_disabled``, is marked disabled, then unloaded.
        Returns the plugin ids that were deactivated.
        """
        targets = self.list_deactivation_targets(name, cascade=cascade)
        deactivated: List[str] = []
        for tid in targets:
            try:
                if self.has_plugin_instance(tid):
                    instance = self.get_plugin_instance(tid)
                    if hasattr(instance, "on_plugin_disabled"):
                        instance.on_plugin_disabled()
            except Exception as e:
                logger.error(
                    "Error calling on_plugin_disabled for '%s': %s", tid, e
                )
            plugin_class = self.get_plugin(tid)
            display = plugin_ui_label(plugin_class) if plugin_class else tid
            self.disable_plugin(tid)
            logger.info("Disabled plugin: %s", display)
            self.publish_event(
                "plugin_disabled",
                {"plugin_id": tid, "plugin_name": display},
            )
            try:
                self.unload_plugin_instance(tid)
            except Exception as e:
                logger.error("Error unloading plugin instance '%s': %s", tid, e)
            deactivated.append(tid)
        return deactivated

    def list_deactivation_targets(self, name: str, *, cascade: bool = True) -> List[str]:
        """Return plugin ids that ``deactivate_plugin`` would stop, without unloading."""
        key = self.resolve_plugin_key(name) or name
        targets: List[str] = []
        if cascade:
            targets.extend(self.get_enabled_dependents(key))
        if self.is_enabled(key) or self.has_plugin_instance(key):
            targets.append(key)
        return targets

    def publish_event_async(
        self, event_name: str, event_data: Dict[str, Any] | None = None
    ) -> Any:
        """Publish a plugin event asynchronously."""
        return self._registry.publish_event_async(event_name, event_data or {})

    def get_version_incompatibility(self, name: str) -> Optional[str]:
        """Get the version incompatibility reason for a plugin, if any."""
        return self._registry.get_version_incompatibility(name)

    def get_rejected_plugins(self) -> Dict[str, Tuple[Type[Any], str]]:
        """Get rejected plugins and reasons."""
        return self._registry.get_rejected_plugins()

    def register_plugin_force(self, name: str, plugin_class: Type[Any]) -> None:
        """Force register a version-incompatible plugin and enable it immediately."""
        self._registry.register_plugin_force(name, plugin_class)

    def register_rejected_plugin(self, name: str, plugin_class: Type[Any]) -> None:
        """Bypass version checks without enabling. Activation is the caller's job."""
        self._registry.register_rejected_plugin(name, plugin_class)

    def publish_event(self, event_name: str, event_data: Dict[str, Any] | None = None) -> None:
        """Publish a plugin event to subscribers."""
        self._registry.publish_event(event_name, event_data)

    def get_tab_extensions(self, enabled_only: bool = True) -> Dict[str, Type[Any]]:
        """Get TabExtension plugin classes."""
        return self._registry.get_tab_extensions(enabled_only=enabled_only)

    def get_menu_extensions(self, enabled_only: bool = True) -> Dict[str, Type[Any]]:
        """Get MenuExtension plugin classes."""
        return self._registry.get_menu_extensions(enabled_only=enabled_only)

    def get_status_extensions(self, enabled_only: bool = True) -> Dict[str, Type[Any]]:
        """Get StatusExtension plugin classes."""
        return self._registry.get_status_extensions(enabled_only=enabled_only)

    def get_toolbar_extensions(self, enabled_only: bool = True) -> Dict[str, Type[Any]]:
        """Get ToolbarExtension plugin classes."""
        return self._registry.get_toolbar_extensions(enabled_only=enabled_only)

    def get_service_extensions(self, enabled_only: bool = True) -> Dict[str, Type[Any]]:
        """Get ServiceExtension plugin classes."""
        return self._registry.get_service_extensions(enabled_only=enabled_only)

    def subscribe_lifecycle(self, subscriber: Any) -> None:
        """Register a plugin lifecycle subscriber."""
        self._registry.subscribe_lifecycle(subscriber)

    def shutdown_event_executor(self) -> None:
        """Shut down the registry background event executor."""
        self._registry._shutdown_event_executor()

    # =========================================================================
    # Discovery Methods
    # =========================================================================
    
    def _invalidate_core_plugin_modules(self) -> None:
        """Drop cached plugin package modules so the next discovery reloads them."""
        prefixes = (
            "app_plugins.",
            "platforms.",
            "GUI.plugins.",
        )
        exact = {
            "app_plugins",
            "app_plugins.core_plugins",
            "platforms",
            "platforms.core_plugins",
            "GUI.plugin_system.core_plugins",
            "GUI.plugins",
        }
        to_drop = [
            name
            for name in list(sys.modules)
            if name in exact or any(name.startswith(prefix) for prefix in prefixes)
        ]
        for mod_name in to_drop:
            del sys.modules[mod_name]
        # Optional hook if a core_plugins module exposes it after re-import
        try:
            from app_plugins.core_plugins import invalidate_core_plugins_cache  # type: ignore
            invalidate_core_plugins_cache()
        except ImportError:
            pass

    def _install_cross_platform_mocks(self) -> None:
        """Install OS API mocks when loading foreign-platform plugins in dev mode."""
        try:
            from ..utils.admin import is_show_all_platforms
            if not is_show_all_platforms():
                return
            from ..constants import CURRENT_PLATFORM
            if CURRENT_PLATFORM == "linux":
                from ..utils.dev_mode_utils.win32_mocks import install_win32_mocks
                install_win32_mocks()
            elif CURRENT_PLATFORM == "windows":
                from ..utils.dev_mode_utils.linux_mocks import install_linux_mocks
                install_linux_mocks()
            elif CURRENT_PLATFORM == "darwin":
                from ..utils.dev_mode_utils.win32_mocks import install_win32_mocks
                from ..utils.dev_mode_utils.linux_mocks import (
                    DARWIN_MISSING_MODULES,
                    install_linux_mocks,
                )
                install_win32_mocks()
                # macOS has real pwd/grp/fcntl and the rest of the POSIX set, so
                # only the modules it actually lacks get stubbed.
                install_linux_mocks(DARWIN_MISSING_MODULES)
        except Exception as e:
            logger.warning(f"Could not install cross-platform mocks: {e}")

    def discover_and_register_all_plugins(self) -> Tuple[List[Type[Any]], Dict[str, Any]]:
        """Discover and register core and external plugins.
        
        Core plugins are loaded from (in priority order):
        1. app_plugins/core_plugins.py (highest)
        2. platforms/core_plugins.py (middle)
        3. GUI/plugin_system/core_plugins.py (lowest)
        
        Non-core plugins are discovered from (in priority order) as *packages*:
        1. app_plugins.{platform}.plugins and app_plugins.common.plugins
        2. platforms.{platform}.plugins and platforms.common.plugins
        3. GUI.plugins (sample plugins; source trees only, not frozen builds)
        
        Returns (registered_core_plugins, summary) where summary may contain counts/metadata.
        """
        registered_core: List[Type[Any]] = []
        summary: Dict[str, Any] = {"total_discovered": 0}

        try:
            self._install_cross_platform_mocks()
            # Do not invalidate modules on normal startup — Reload Plugins uses clear().
            from ...plugin_system.registry import clear_registration_caches
            clear_registration_caches()

            # Load core plugins from all three sources in priority order
            logger.info("Attempting to load core plugins from all sources...")
            app_plugins = self._load_core_plugins_from_source("app_plugins")
            platforms_available = importlib.util.find_spec("platforms") is not None
            platforms_plugins = (
                self._load_core_plugins_from_source("platforms")
                if platforms_available
                else []
            )
            if not platforms_available:
                logger.debug("Skipping platforms core plugins: package not found")
            gui_plugins = self._load_core_plugins_from_source("gui")
            
            all_core_plugins = self._merge_plugins_with_priority(
                [
                    app_plugins,       # Highest priority
                    platforms_plugins, # Middle priority
                    gui_plugins,       # Lowest priority
                ]
            )
            logger.info(f"Total core plugins to register after merge: {len(all_core_plugins)} plugins")
            registered_core = self._register_core_plugins(all_core_plugins)

            # Discover non-core plugins from multiple locations in priority order
            try:
                from ..constants import CURRENT_PLATFORM
                from ..utils.admin import is_show_all_platforms
                
                # Determine target platforms to load plugins from
                target_platforms = [CURRENT_PLATFORM]
                if is_show_all_platforms():
                    all_platforms = ["windows", "linux", "darwin"]
                    target_platforms = list(set(all_platforms + [CURRENT_PLATFORM]))
                
                sources: List[PluginSource] = []
                
                # Add platform-specific plugin sources
                for plat in target_platforms:
                    is_current = (plat == CURRENT_PLATFORM)
                    sources.append(PluginSource(
                        source_id=f"app_plugins.{plat}.plugins",
                        package=f"app_plugins.{plat}.plugins",
                        priority=300 if is_current else 250,
                    ))
                    if platforms_available:
                        sources.append(PluginSource(
                            source_id=f"platforms.{plat}.plugins",
                            package=f"platforms.{plat}.plugins",
                            priority=200 if is_current else 150,
                        ))
                
                # Add common plugin sources
                sources.append(PluginSource(
                    source_id="app_plugins.common.plugins",
                    package="app_plugins.common.plugins",
                    priority=290,
                ))
                if platforms_available:
                    sources.append(PluginSource(
                        source_id="platforms.common.plugins",
                        package="platforms.common.plugins",
                        priority=190,
                    ))
                # Sample plugins under GUI.plugins when runtime is_dev_mode() is on
                # (CLI --dev/-dev, persisted settings, or host VERSION containing -dev),
                # or when GUI_LOAD_SAMPLE_PLUGINS=1. Never load in frozen builds;
                # force off with GUI_LOAD_SAMPLE_PLUGINS=0.
                gui_pkg = __package__.split('.')[0]
                env_samples = os.environ.get("GUI_LOAD_SAMPLE_PLUGINS")
                try:
                    from ..utils.admin import is_dev_mode
                    runtime_dev = bool(is_dev_mode())
                except Exception:
                    runtime_dev = ("--dev" in sys.argv) or ("-dev" in sys.argv)
                if env_samples is not None:
                    load_samples = env_samples != "0" and not getattr(sys, "frozen", False)
                else:
                    load_samples = (
                        not getattr(sys, "frozen", False) and runtime_dev
                    )
                if load_samples:
                    sources.append(PluginSource(
                        source_id=f"{gui_pkg}.plugins",
                        package=f"{gui_pkg}.plugins",
                        priority=100,
                    ))

                from ..host_config import get_host_config
                plugins_dir = get_host_config().plugins_dir()
                discovery = PluginDiscovery(plugins_dir=str(plugins_dir))
                total_registered = 0
                builtin_registered = 0
                sample_pkg = f"{gui_pkg}.plugins"

                # Sort by priority DESC to ensure earlier sources win.
                for source in sorted(sources, key=lambda s: s.priority, reverse=True):
                    discovered = discovery.discover_from_packages([source])
                    if not discovered:
                        continue

                    for plugin_name, plugin_class, _src in discovered:
                        # Determine the name this plugin will be registered under
                        registered_name = self._registry.get_registered_name(plugin_class)
                        # Preserve priority: if already registered, don't override.
                        if self._registry.get_plugin(registered_name) is not None:
                            logger.debug(f"Skipping plugin '{registered_name}' from {source.source_id} due to higher-priority registration")
                            continue
                        try:
                            self._registry.register_plugin(plugin_class, is_core=False)
                            total_registered += 1
                            if source.package == sample_pkg:
                                builtin_registered += 1
                        except Exception as e:
                            logger.warning(f"Failed to register plugin '{plugin_name}' from {source.source_id}: {e}")

                # Discover external plugins from the plugins directory.
                # Skip in-tree GUI/plugins when samples were already loaded as a package,
                # or when samples are disabled for that directory.
                local_discovered: List[Tuple[str, Type[Any], str]] = []
                plugins_path = Path(plugins_dir)
                is_gui_plugins_dir = discovery._is_gui_plugins_directory(plugins_path)
                if is_gui_plugins_dir:
                    # Package discovery already covered GUI.plugins when load_samples.
                    if load_samples:
                        logger.debug("Skipping local GUI/plugins scan; package discovery already ran")
                    # else: samples disabled — skip in-tree samples entirely
                else:
                    local_discovered = discovery.discover_local_plugins()
                local_registered = 0
                for plugin_name, plugin_class, _src in local_discovered:
                    registered_name = self._registry.get_registered_name(plugin_class)
                    if self._registry.get_plugin(registered_name) is not None:
                        logger.debug(f"Skipping local plugin '{registered_name}' due to higher-priority registration")
                        continue
                    try:
                        self._registry.register_plugin(plugin_class, is_core=False)
                        local_registered += 1
                    except Exception as e:
                        logger.warning(f"Failed to register local plugin '{registered_name}': {e}")

                summary["total_discovered"] = summary.get("total_discovered", 0) + total_registered + local_registered
                summary["builtin_plugins"] = builtin_registered
                summary["local_plugins"] = local_registered
            except Exception as e:  # pragma: no cover - optional discovery
                logger.warning(f"Plugin discovery failed: {e}")
        except Exception as e:
            logger.error(f"Error during plugin discovery: {e}")
            raise

        self._discovery_complete = True
        self.finalize_plugin_graph()
        
        # PERF: Clear the discovery object's accumulated list — all plugins have
        # been registered into the registry, so these (name, class, source) tuples
        # are dead weight.
        try:
            discovery.discovered_plugins.clear()
        except (NameError, AttributeError):
            pass  # discovery may not have been created if an early exception occurred
        
        return registered_core, summary
    
    def _load_core_plugins_from_source(self, source: str) -> List[Type[Any]]:
        """Load core plugins from a specific source.
        
        Args:
            source: One of 'app_plugins', 'platforms', or 'gui'
            
        Returns:
            List of plugin classes, empty list on error
        """
        try:
            if source in ("app_plugins", "platforms"):
                _ensure_parent_project_on_path()
            if source == "app_plugins":
                from app_plugins.core_plugins import get_core_plugins  # type: ignore
                plugins = get_core_plugins()
                logger.info(f"app_plugins core plugins retrieved: {len(plugins)} plugins")
                return plugins
            elif source == "platforms":
                from platforms.core_plugins import get_core_plugins  # type: ignore
                plugins = get_core_plugins()
                logger.info(f"platforms core plugins retrieved: {len(plugins)} plugins")
                return plugins
            elif source == "gui":
                from ...plugin_system.core_plugins import get_core_plugins
                plugins = get_core_plugins()
                logger.info(f"GUI core plugins retrieved: {len(plugins)} plugins")
                return plugins
            else:
                logger.warning(f"Unknown core plugin source: {source}")
                return []
        except Exception as e:
            logger.info(f"Failed to load {source} core plugins: {e}")
            return []
    
    def _merge_plugins_with_priority(
        self,
        plugin_lists: List[List[Type[Any]]]
    ) -> List[Type[Any]]:
        """Merge plugin lists with earlier lists taking priority on conflicts.
        
        Args:
            plugin_lists: List of plugin class lists, ordered by priority (highest first)
            
        Returns:
            Merged list of plugin classes with duplicates resolved by priority
        """
        seen_keys: Dict[str, Type[Any]] = {}
        
        for plugin_list in plugin_lists:
            for plugin_class in plugin_list:
                key = self._registry.get_registered_name(plugin_class)
                if key not in seen_keys:
                    seen_keys[key] = plugin_class
                else:
                    logger.debug(f"Skipping duplicate plugin '{key}' from lower priority source")
        
        return list(seen_keys.values())
    
    def _register_core_plugins(self, plugin_classes: List[Type[Any]]) -> List[Type[Any]]:
        """Register a list of core plugin classes.
        
        Args:
            plugin_classes: List of plugin classes to register
            
        Returns:
            List of successfully registered plugin classes
        """
        registered: List[Type[Any]] = []
        for plugin_class in plugin_classes:
            try:
                self.register_plugin(plugin_class, is_core=True)
                registered.append(plugin_class)
                
                logger.info(f"Registered core plugin: {plugin_ui_label(plugin_class)}")
            except Exception as e:
                logger.error(f"Failed to register core plugin {plugin_class.__name__}: {e}")
        return registered
    
    # =========================================================================
    # Plugin State Management Methods
    # =========================================================================
    
    def load_saved_plugin_states(self) -> None:
        """Load and apply saved plugin states from settings.
        
        This is the main entry point for loading plugin states after discovery.
        It handles both first-run scenarios and loading saved user preferences.
        Default-off plugins the user enabled are restored from ``enabled_plugins``.
        Consumers with disabled providers are blocked for this startup without
        recording that temporary block as a user-disabled override.
        """
        if not self.settings_service:
            logger.debug("No settings service, skipping plugin state loading")
            self._block_unavailable_startup_dependencies()
            return

        try:
            saved_disabled = self.settings_service.get_disabled_plugins()
            saved_enabled = self.settings_service.get_enabled_plugins()
            has_override_keys = True
            present = getattr(self.settings_service, "has_plugin_override_keys", None)
            if callable(present):
                has_override_keys = present()
            if saved_disabled:
                self._apply_user_disabled_plugins(saved_disabled)
            if saved_enabled:
                self._apply_user_enabled_plugins(saved_enabled)
            if not saved_disabled and not saved_enabled and not has_override_keys:
                self._handle_first_run()
        except Exception as e:
            logger.warning(f"Failed to load saved plugin states: {e}")
        self._block_unavailable_startup_dependencies()

    def _block_unavailable_startup_dependencies(self) -> None:
        for name in self.get_startup_order():
            if self.is_enabled(name) and self._unsatisfied_dependencies(name):
                self._registry.disable_plugin(name)
                self._startup_dependency_blocks.add(name)
                logger.warning("Disabled '%s' for this startup: required provider is disabled", name)
    
    def _apply_user_disabled_plugins(self, disabled_plugins: List[str]) -> None:
        """Apply user-disabled plugins from settings.
        
        Also cleans up any disabled_by_default plugins that were incorrectly saved.
        
        Args:
            disabled_plugins: List of plugin ids that user has disabled
        """
        logger.info(
            f"Loading saved user-disabled plugins: "
            f"{[self.plugin_label(p) for p in disabled_plugins]}"
        )
        
        # Filter out plugins that are disabled_by_default (they shouldn't be in settings)
        cleaned_disabled = []
        for plugin_name in disabled_plugins:
            plugin_class = self.get_plugin(plugin_name)
            if plugin_class:
                if getattr(plugin_class, 'disabled_by_default', False):
                    logger.debug(f"Removing disabled_by_default plugin from settings: {plugin_name}")
                else:
                    self.disable_plugin(plugin_name)
                    cleaned_disabled.append(plugin_name)
                    logger.debug(f"Applied user preference: {plugin_name} disabled")
            else:
                # Plugin no longer exists, don't include in cleaned list
                logger.debug(f"Skipping non-existent plugin: {plugin_name}")
        
        # Re-save if we cleaned up any entries
        if len(cleaned_disabled) != len(disabled_plugins) and self.settings_service:
            logger.info(f"Cleaning up settings: removed {len(disabled_plugins) - len(cleaned_disabled)} disabled_by_default plugins")
            self.settings_service.save_disabled_plugins(cleaned_disabled)

    def _apply_user_enabled_plugins(self, enabled_plugins: List[str]) -> None:
        """Apply user-enabled overrides for plugins that are disabled_by_default."""
        logger.info(
            f"Loading saved user-enabled plugins: "
            f"{[self.plugin_label(p) for p in enabled_plugins]}"
        )
        cleaned_enabled = []
        for plugin_name in enabled_plugins:
            plugin_class = self.get_plugin(plugin_name)
            if plugin_class and getattr(plugin_class, 'disabled_by_default', False):
                self.enable_plugin(plugin_name)
                cleaned_enabled.append(plugin_name)
                logger.debug(f"Applied user preference: {plugin_name} enabled")
            elif plugin_class:
                logger.debug(f"Skipping non-default-off plugin in enabled list: {plugin_name}")
            else:
                logger.debug(f"Skipping non-existent plugin: {plugin_name}")
        if len(cleaned_enabled) != len(enabled_plugins) and self.settings_service:
            self.settings_service.save_enabled_plugins(cleaned_enabled)
    
    def _handle_first_run(self) -> None:
        """Handle first run scenario - log defaults and initialize empty override lists."""
        logger.info("First run detected, applying default plugin states (disabled_by_default flags)")
        # Log default states for information
        enabled_by_default = [name for name in self.list_plugin_names() 
                            if self.is_enabled(name)]
        disabled_by_default = [name for name in self.list_plugin_names() 
                              if not self.is_enabled(name)]
        logger.info(f"Default plugin states: {len(enabled_by_default)} enabled, "
                   f"{len(disabled_by_default)} disabled by default")
        if disabled_by_default:
            logger.info(
                f"Disabled by default: {', '.join(self.plugin_label(p) for p in disabled_by_default)}"
            )
        
        if self.settings_service:
            saver = getattr(self.settings_service, "save_plugin_overrides", None)
            if callable(saver):
                saver([], [])
            else:
                self.settings_service.save_disabled_plugins([])
                self.settings_service.save_enabled_plugins([])
    
    @property
    def is_discovery_complete(self) -> bool:
        """Check if plugin discovery has been completed."""
        return self._discovery_complete



__all__ = ['PluginService']
