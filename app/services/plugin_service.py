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
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type, TYPE_CHECKING

from ...plugin_system import plugin_registry
from ...plugin_system.base import BaseTabPlugin

if TYPE_CHECKING:
    from .settings_service import SettingsService

logger = logging.getLogger(__name__)


@contextmanager
def _with_sys_path(path: Path):
    """Context manager for temporarily adding a path to sys.path."""
    path_str = str(path)
    was_in_path = path_str in sys.path
    if not was_in_path:
        sys.path.insert(0, path_str)
    try:
        yield
    finally:
        if not was_in_path and path_str in sys.path:
            sys.path.remove(path_str)


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
        
        Non-core plugins are discovered from (in priority order):
        1. app_plugins/{platform}/plugins/ and app_plugins/common/plugins/
        2. platforms/{platform}/plugins/ and platforms/common/plugins/
        3. External plugins directory (project_root/plugins/)
        4. GUI/plugins/ (built-in examples)
        
        Returns (registered_core_plugins, summary) where summary may contain counts/metadata.
        """
        registered_core: List[Type[Any]] = []
        summary: Dict[str, Any] = {"total_discovered": 0}

        try:
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
                from ...plugin_system.discovery import discover_and_register_plugins as discover
                from ..utils.paths import get_plugins_dir
                from ..constants import CURRENT_PLATFORM
                
                # GUI directory (this file is at GUI/app/services/plugin_service.py)
                gui_dir = Path(__file__).parent.parent.parent
                
                def find_external_dir(folder_name: str) -> Optional[Path]:
                    """Find an external directory by checking multiple candidate locations.
                    
                    This handles cases where GUI is used as a submodule or standalone.
                    """
                    candidates = [
                        gui_dir.parent / folder_name,     # Sibling to GUI (most common)
                        gui_dir / folder_name,            # Inside GUI directory
                        Path.cwd() / folder_name,         # Current working directory
                        Path.cwd().parent / folder_name,  # Parent of cwd
                    ]
                    for candidate in candidates:
                        if candidate.exists() and candidate.is_dir():
                            return candidate
                    return None
                
                def discover_from_dir(plugins_dir: Optional[Path], source_name: str) -> int:
                    """Discover plugins from a directory and return count."""
                    if plugins_dir is None or not plugins_dir.exists():
                        logger.debug(f"{source_name} directory not found or does not exist")
                        return 0
                    results, dir_summary = discover(str(plugins_dir))
                    count = dir_summary.get("total_discovered", 0) if isinstance(dir_summary, dict) else 0
                    if count > 0:
                        logger.info(f"{source_name} plugin discovery: {count} plugins found")
                        summary["total_discovered"] = summary.get("total_discovered", 0) + count
                    return count
                
                # Priority 1: app_plugins/{platform}/plugins/ and app_plugins/common/plugins/
                app_plugins_dir = find_external_dir("app_plugins")
                if app_plugins_dir:
                    discover_from_dir(
                        app_plugins_dir / CURRENT_PLATFORM / "plugins",
                        f"app_plugins/{CURRENT_PLATFORM}/plugins"
                    )
                    discover_from_dir(
                        app_plugins_dir / "common" / "plugins",
                        "app_plugins/common/plugins"
                    )
                
                # Priority 2: platforms/{platform}/plugins/ and platforms/common/plugins/
                platforms_dir = find_external_dir("platforms")
                if platforms_dir:
                    discover_from_dir(
                        platforms_dir / CURRENT_PLATFORM / "plugins",
                        f"platforms/{CURRENT_PLATFORM}/plugins"
                    )
                    discover_from_dir(
                        platforms_dir / "common" / "plugins",
                        "platforms/common/plugins"
                    )
                
                # Priority 3: External plugins (in parent project's plugins directory)
                external_plugins_dir = str(get_plugins_dir())
                external_results, external_summary = discover(external_plugins_dir)
                if isinstance(external_summary, dict):
                    summary["total_discovered"] = summary.get("total_discovered", 0) + external_summary.get("total_discovered", 0)
                logger.info("External plugin discovery complete: %s plugins found", external_summary.get("total_discovered", 0))

                # Priority 4: Built-in plugins (in GUI/plugins directory)
                gui_plugins_dir = str(gui_dir / "plugins")
                builtin_results, builtin_summary = discover(gui_plugins_dir)
                if isinstance(builtin_summary, dict):
                    summary["total_discovered"] = summary.get("total_discovered", 0) + builtin_summary.get("total_discovered", 0)
                    summary["builtin_plugins"] = builtin_summary.get("local_plugins", 0)
                logger.info("Built-in plugin discovery complete: %s plugins found", builtin_summary.get("total_discovered", 0))
            except Exception as e:  # pragma: no cover - optional discovery
                logger.warning("Plugin discovery failed: %s", e)
        except Exception as e:
            logger.error("Error during plugin discovery: %s", e)
            raise

        self._discovery_complete = True
        return registered_core, summary
    
    def _find_external_dir(self, folder_name: str) -> Optional[Path]:
        """Find an external directory by checking multiple candidate locations.
        
        This handles cases where GUI is used as a submodule or standalone.
        
        Args:
            folder_name: Name of the directory to find (e.g., 'app_plugins', 'platforms')
            
        Returns:
            Path to the directory if found, None otherwise
        """
        gui_dir = Path(__file__).parent.parent.parent
        candidates = [
            gui_dir.parent / folder_name,     # Sibling to GUI (most common)
            gui_dir / folder_name,            # Inside GUI directory
            Path.cwd() / folder_name,         # Current working directory
            Path.cwd().parent / folder_name,  # Parent of cwd
        ]
        for candidate in candidates:
            if candidate.exists() and candidate.is_dir():
                return candidate
        return None
    
    def _load_core_plugins_from_source(self, source: str) -> List[Type[Any]]:
        """Load core plugins from a specific source.
        
        Args:
            source: One of 'app_plugins', 'platforms', or 'gui'
            
        Returns:
            List of plugin classes, empty list on error
        """
        try:
            # GUI directory (this file is at GUI/app/services/plugin_service.py)
            gui_dir = Path(__file__).parent.parent.parent
            
            if source == "app_plugins":
                app_plugins_dir = self._find_external_dir("app_plugins")
                if app_plugins_dir is None:
                    logger.debug("app_plugins directory not found")
                    return []
                # Add both the parent dir (for app_plugins imports) and GUI (for plugins.base imports)
                with _with_sys_path(app_plugins_dir.parent):
                    with _with_sys_path(gui_dir):
                        from app_plugins.core_plugins import get_core_plugins  # type: ignore
                        plugins = get_core_plugins()
                        logger.info("app_plugins core plugins retrieved: %d plugins", len(plugins))
                        return plugins
            elif source == "platforms":
                platforms_dir = self._find_external_dir("platforms")
                if platforms_dir is None:
                    logger.debug("platforms directory not found")
                    return []
                # Add both the parent dir (for platforms imports) and GUI (for plugins.base imports)
                with _with_sys_path(platforms_dir.parent):
                    with _with_sys_path(gui_dir):
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
                name = getattr(plugin_class, 'tab_name', plugin_class.__name__)
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

