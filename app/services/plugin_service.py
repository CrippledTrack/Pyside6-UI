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
        
        Returns (registered_core_plugins, summary) where summary may contain counts/metadata.
        """
        registered_core: List[Type[Any]] = []
        summary: Dict[str, Any] = {"total_discovered": 0}

        try:
            # Register core plugins from both sources
            logger.info("Attempting to load core plugins...")
            platforms_plugins = self._load_core_plugins_from_source("platforms")
            gui_plugins = self._load_core_plugins_from_source("gui")
            
            all_core_plugins = platforms_plugins + gui_plugins
            logger.info("Total core plugins to register: %d plugins", len(all_core_plugins))
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

            # Discover plugins from both external and built-in locations
            try:
                from ...plugin_system.discovery import discover_and_register_plugins as discover
                from ..utils.paths import get_plugins_dir

                # Discover external plugins (in parent project's plugins directory)
                external_plugins_dir = str(get_plugins_dir())
                external_results, external_summary = discover(external_plugins_dir)
                if isinstance(external_summary, dict):
                    summary.update(external_summary)
                logger.info("External plugin discovery complete: %s plugins found", external_summary.get("total_discovered", 0))

                # Discover built-in plugins (in GUI/plugins directory)
                gui_plugins_dir = str(Path(__file__).parent.parent.parent / "plugins")
                builtin_results, builtin_summary = discover(gui_plugins_dir)
                if isinstance(builtin_summary, dict):
                    # Merge the summaries
                    summary["total_discovered"] = summary.get("total_discovered", 0) + builtin_summary.get("total_discovered", 0)
                    if "local_plugins" in summary and "local_plugins" in builtin_summary:
                        summary["local_plugins"] = summary["local_plugins"] + builtin_summary["local_plugins"]
                    else:
                        summary["builtin_plugins"] = builtin_summary.get("local_plugins", 0)
                logger.info("Built-in plugin discovery complete: %s plugins found", builtin_summary.get("total_discovered", 0))
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
            source: Either 'platforms' (for app_plugins/, with legacy fallback) or 'gui'
            
        Returns:
            List of plugin classes, empty list on error
        """
        try:
            if source == "platforms":
                parent_dir = Path(__file__).parent.parent.parent
                with _with_sys_path(parent_dir):
                    # Try new name first (app_plugins)
                    try:
                        from app_plugins.core_plugins import get_core_plugins  # type: ignore
                        plugins = get_core_plugins()
                        logger.info("App plugins core plugins retrieved: %d plugins", len(plugins))
                        return plugins
                    except ImportError:
                        # LEGACY: Support for old 'platforms/' folder name (deprecated, 3.0.0 compatibility)
                        from platforms.core_plugins import get_core_plugins  # type: ignore
                        plugins = get_core_plugins()
                        logger.warning("Using legacy 'platforms/' folder for core plugins (deprecated, 3.0.0 compatibility). Consider migrating to 'app_plugins/'")
                        logger.info("Platforms core plugins retrieved: %d plugins", len(plugins))
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
    
    @property
    def is_discovery_complete(self) -> bool:
        """Check if plugin discovery has been completed."""
        return self._discovery_complete


# Legacy function for backward compatibility
def discover_and_register_all_plugins() -> Tuple[List[Type[Any]], Dict[str, Any]]:
    """Discover and register core and external plugins.
    
    This is a legacy function for backward compatibility.
    New code should use PluginService.discover_and_register_all_plugins().
    
    Returns (registered_core_plugins, summary) where summary may contain counts/metadata.
    """
    service = PluginService()
    return service.discover_and_register_all_plugins()


__all__ = ['PluginService', 'discover_and_register_all_plugins']
