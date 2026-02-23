"""
Plugin service for managing plugin discovery and registry access.

This module provides the PluginService class which wraps the plugin_registry
singleton, enabling dependency injection and easier testing. It handles:
- Plugin discovery from multiple sources
- Plugin registration and state management
- Access to plugin registry methods

The underlying plugin_registry singleton is still used for compatibility,
but all access should go through this service when using dependency injection.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type, TYPE_CHECKING

from ...plugin_system import plugin_registry
from ...plugin_system.base import BaseTabPlugin
from ...plugin_system.discovery import PluginDiscovery
from ...plugin_system.sources import PluginSource
from ...plugin_system.import_aliases import install_import_aliases
from ..utils.paths import parent_has_gui_plugin_dirs

if TYPE_CHECKING:
    from .settings_service import SettingsService

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
    
    This service wraps the global plugin_registry singleton to enable
    dependency injection and easier testing. All plugin registry operations
    should go through this service when using the ServiceContainer.
    """
    
    def __init__(self, settings_service: Optional["SettingsService"] = None) -> None:
        """Initialize the plugin service.
        
        Args:
            settings_service: Optional settings service for plugin state persistence
        """
        self.settings_service = settings_service
        self._discovery_complete = False
    
    # =========================================================================
    # Registry Access Methods (delegating to plugin_registry)
    # =========================================================================
    
    def get_all_plugins(self) -> Dict[str, Type[BaseTabPlugin]]:
        """Get all registered plugins."""
        return plugin_registry.get_all_plugins()
    
    def get_core_plugins(self) -> Dict[str, Type[BaseTabPlugin]]:
        """Get core plugins only."""
        return plugin_registry.get_core_plugins()
    
    def get_external_plugins(self) -> Dict[str, Type[BaseTabPlugin]]:
        """Get external plugins only."""
        return plugin_registry.get_external_plugins()
    
    def get_plugin(self, name: str) -> Optional[Type[BaseTabPlugin]]:
        """Get a specific plugin by name."""
        return plugin_registry.get_plugin(name)
    
    def list_plugin_names(self) -> List[str]:
        """Get list of all plugin names."""
        return plugin_registry.list_plugin_names()
    
    def register_plugin(self, plugin_class: Type[BaseTabPlugin], is_core: bool = False) -> None:
        """Register a plugin in the registry."""
        plugin_registry.register_plugin(plugin_class, is_core=is_core)
    
    def clear(self) -> None:
        """Clear all registered plugins."""
        plugin_registry.clear()
        self._discovery_complete = False
    
    def disable_plugin(self, name: str) -> None:
        """Disable a plugin by name."""
        plugin_registry.disable_plugin(name)
    
    def enable_plugin(self, name: str) -> None:
        """Enable a plugin by name."""
        plugin_registry.enable_plugin(name)
    
    def is_enabled(self, name: str) -> bool:
        """Check if a plugin is enabled."""
        return plugin_registry.is_enabled(name)
    
    def get_enabled_plugins(self) -> Dict[str, Type[BaseTabPlugin]]:
        """Get all enabled plugins."""
        return plugin_registry.get_enabled_plugins()
    
    def get_version_incompatibility(self, name: str) -> Optional[str]:
        """Get the version incompatibility reason for a plugin, if any."""
        return plugin_registry.get_version_incompatibility(name)
    
    # =========================================================================
    # Discovery Methods
    # =========================================================================
    
    def discover_and_register_all_plugins(self) -> Tuple[List[Type[Any]], Dict[str, Any]]:
        """Discover and register core and external plugins.
        
        Core plugins are loaded from (in priority order):
        1. app_plugins/core_plugins.py (highest)
        2. platforms/core_plugins.py (middle)
        3. GUI/plugin_system/core_plugins.py (lowest)
        
        Non-core plugins are discovered from (in priority order) as *packages*:
        1. app_plugins.{platform}.plugins and app_plugins.common.plugins
        2. platforms.{platform}.plugins and platforms.common.plugins
        3. GUI.plugins (built-in examples)
        
        Returns (registered_core_plugins, summary) where summary may contain counts/metadata.
        """
        registered_core: List[Type[Any]] = []
        summary: Dict[str, Any] = {"total_discovered": 0}

        try:
            # Ensure legacy imports used by some plugin modules resolve consistently.
            install_import_aliases()

            # Load core plugins from all three sources in priority order
            logger.info("Attempting to load core plugins from all sources...")
            app_plugins = self._load_core_plugins_from_source("app_plugins")
            platforms_plugins = self._load_core_plugins_from_source("platforms")
            gui_plugins = self._load_core_plugins_from_source("gui")
            
            # Merge with priority (app_plugins > platforms > GUI)
            all_core_plugins = self._merge_plugins_with_priority([
                app_plugins,       # Highest priority
                platforms_plugins, # Middle priority
                gui_plugins,       # Lowest priority
            ])
            logger.info("Total core plugins to register after merge: %d plugins", len(all_core_plugins))
            registered_core = self._register_core_plugins(all_core_plugins)

            # In dev mode with show_all_platforms, also load cross-platform plugins
            try:
                from ..utils.admin import is_show_all_platforms
                if is_show_all_platforms():
                    from ..constants import CURRENT_PLATFORM
                    try:
                        if CURRENT_PLATFORM == "linux":
                            from ..utils.dev_mode_utils.win32_mocks import install_win32_mocks
                            install_win32_mocks()
                        elif CURRENT_PLATFORM == "windows":
                            from ..utils.dev_mode_utils.linux_mocks import install_linux_mocks
                            install_linux_mocks()
                    except Exception as e:
                        logger.warning("Could not install cross-platform mocks: %s", e)

                    try:
                        from ..utils.dev_mode_utils.cross_platform_plugins import clear_cross_platform_cache
                        clear_cross_platform_cache()
                    except Exception as e:
                        logger.debug("Could not clear cross-platform plugin cache: %s", e)

                    logger.info("Dev mode: Loading cross-platform plugins...")
                    from ..utils.dev_mode_utils.cross_platform_plugins import load_cross_platform_plugins
                    cross_platform = load_cross_platform_plugins()
                    if cross_platform:
                        registered_cross = self._register_core_plugins(cross_platform)
                        logger.info("Registered %d cross-platform plugins", len(registered_cross))
                        registered_core.extend(registered_cross)
            except ImportError as e:
                logger.debug(f"Cross-platform plugins not available: {e}")

            # Discover non-core plugins from multiple locations in priority order
            try:
                from ..constants import CURRENT_PLATFORM
                
                # Highest priority first (earlier wins on conflicts)
                sources: List[PluginSource] = [
                    PluginSource(
                        source_id=f"app_plugins.{CURRENT_PLATFORM}.plugins",
                        package=f"app_plugins.{CURRENT_PLATFORM}.plugins",
                        priority=300,
                    ),
                    PluginSource(
                        source_id="app_plugins.common.plugins",
                        package="app_plugins.common.plugins",
                        priority=290,
                    ),
                    PluginSource(
                        source_id=f"platforms.{CURRENT_PLATFORM}.plugins",
                        package=f"platforms.{CURRENT_PLATFORM}.plugins",
                        priority=200,
                    ),
                    PluginSource(
                        source_id="platforms.common.plugins",
                        package="platforms.common.plugins",
                        priority=190,
                    ),
                    PluginSource(
                        source_id="GUI.plugins",
                        package="GUI.plugins",
                        priority=100,
                    ),
                ]

                from ..utils.paths import get_plugins_dir
                plugins_dir = get_plugins_dir()
                discovery = PluginDiscovery(plugins_dir=str(plugins_dir))
                total_registered = 0
                builtin_registered = 0

                # Sort by priority DESC to ensure earlier sources win.
                for source in sorted(sources, key=lambda s: s.priority, reverse=True):
                    discovered = discovery.discover_from_packages([source])
                    if not discovered:
                        continue

                    for plugin_name, plugin_class, _src in discovered:
                        # Preserve priority: if already registered, don't override.
                        if plugin_registry.get_plugin(plugin_name) is not None:
                            logger.debug(
                                "Skipping plugin '%s' from %s due to higher-priority registration",
                                plugin_name,
                                source.source_id,
                            )
                            continue
                        try:
                            plugin_registry.register_plugin(plugin_class, is_core=False)
                            total_registered += 1
                            if source.package == "GUI.plugins":
                                builtin_registered += 1
                        except Exception as e:
                            logger.warning(
                                "Failed to register plugin '%s' from %s: %s",
                                plugin_name,
                                source.source_id,
                                e,
                            )

                # Discover and register external plugins from the plugins directory.
                local_discovered = discovery.discover_local_plugins()
                local_registered = 0
                for plugin_name, plugin_class, _src in local_discovered:
                    if plugin_registry.get_plugin(plugin_name) is not None:
                        logger.debug(
                            "Skipping local plugin '%s' due to higher-priority registration",
                            plugin_name,
                        )
                        continue
                    try:
                        plugin_registry.register_plugin(plugin_class, is_core=False)
                        local_registered += 1
                    except Exception as e:
                        logger.warning("Failed to register local plugin '%s': %s", plugin_name, e)

                summary["total_discovered"] = summary.get("total_discovered", 0) + total_registered + local_registered
                summary["builtin_plugins"] = builtin_registered
                summary["local_plugins"] = local_registered
            except Exception as e:  # pragma: no cover - optional discovery
                logger.warning("Plugin discovery failed: %s", e)
        except Exception as e:
            logger.error("Error during plugin discovery: %s", e)
            raise

        self._discovery_complete = True
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
                logger.info("app_plugins core plugins retrieved: %d plugins", len(plugins))
                return plugins
            elif source == "platforms":
                from platforms.core_plugins import get_core_plugins  # type: ignore
                plugins = get_core_plugins()
                logger.info("platforms core plugins retrieved: %d plugins", len(plugins))
                return plugins
            elif source == "gui":
                from ...plugin_system.core_plugins import get_core_plugins
                plugins = get_core_plugins()
                logger.info("GUI core plugins retrieved: %d plugins", len(plugins))
                return plugins
            else:
                logger.warning(f"Unknown core plugin source: {source}")
                return []
        except Exception as e:
            logger.info("Failed to load %s core plugins: %s", source, e)
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
        seen_names: Dict[str, Type[Any]] = {}
        
        for plugin_list in plugin_lists:
            for plugin_class in plugin_list:
                name = getattr(plugin_class, 'tab_name', None)
                if not name or name == "Unnamed Tab":
                    name = getattr(plugin_class, 'plugin_name', None)
                if not name or name == "Unnamed Plugin":
                    name = plugin_class.__name__
                if name not in seen_names:
                    seen_names[name] = plugin_class
                else:
                    logger.debug(f"Skipping duplicate plugin '{name}' from lower priority source")
        
        return list(seen_names.values())
    
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
                logger.info("Registered core plugin: %s", getattr(plugin_class, "tab_name", plugin_class.__name__))
            except Exception as e:
                logger.error("Failed to register core plugin %s: %s", plugin_class.__name__, e)
        return registered
    
    # =========================================================================
    # Plugin State Management Methods
    # =========================================================================
    
    def load_saved_plugin_states(self) -> None:
        """Load and apply saved plugin states from settings.
        
        This is the main entry point for loading plugin states after discovery.
        It handles both first-run scenarios and loading saved user preferences.
        """
        if not self.settings_service:
            logger.debug("No settings service, skipping plugin state loading")
            return

        try:
            saved_disabled = self.settings_service.get_disabled_plugins()
            if saved_disabled:
                self._apply_user_disabled_plugins(saved_disabled)
            else:
                self._handle_first_run()
        except Exception as e:
            logger.warning(f"Failed to load saved plugin states: {e}")
    
    def _apply_user_disabled_plugins(self, disabled_plugins: List[str]) -> None:
        """Apply user-disabled plugins from settings.
        
        Also cleans up any disabled_by_default plugins that were incorrectly saved.
        
        Args:
            disabled_plugins: List of plugin names that user has disabled
        """
        logger.info(f"Loading saved user-disabled plugins: {disabled_plugins}")
        
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
    
    def _handle_first_run(self) -> None:
        """Handle first run scenario - log defaults and initialize empty disabled list."""
        logger.info("First run detected, applying default plugin states (disabled_by_default flags)")
        # Log default states for information
        enabled_by_default = [name for name in self.list_plugin_names() 
                            if self.is_enabled(name)]
        disabled_by_default = [name for name in self.list_plugin_names() 
                              if not self.is_enabled(name)]
        logger.info(f"Default plugin states: {len(enabled_by_default)} enabled, "
                   f"{len(disabled_by_default)} disabled by default")
        if disabled_by_default:
            logger.info(f"Disabled by default: {', '.join(disabled_by_default)}")
        
        # Initialize empty disabled list (user hasn't disabled anything yet)
        if self.settings_service:
            self.settings_service.save_disabled_plugins([])
    
    @property
    def is_discovery_complete(self) -> bool:
        """Check if plugin discovery has been completed."""
        return self._discovery_complete



__all__ = ['PluginService']

