"""
Plugin registry system for managing discovered and loaded plugins.

This module provides the PluginRegistry class which maintains a registry of all
available plugins, handles plugin registration, enables/disables plugins, and
manages version compatibility checks.
"""

from __future__ import annotations

import logging
from typing import Optional, List, Dict, Type

# Import after BaseTabPlugin is defined to avoid circular import issues
from .base import BaseTabPlugin  # type: ignore
from .version_utils import check_version_compatibility, get_gui_version

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Registry for managing discovered plugins."""

    def __init__(self) -> None:
        self._plugins: Dict[str, Type[BaseTabPlugin]] = {}
        self._core_plugins: Dict[str, Type[BaseTabPlugin]] = {}
        self._external_plugins: Dict[str, Type[BaseTabPlugin]] = {}
        self._disabled_plugins: set = set()
        # Track plugins seen in this runtime to apply default-disabled only once per session
        self._seen_plugins: set = set()
        # Track version incompatibility reasons for plugins
        self._version_incompatibilities: Dict[str, str] = {}

    def register_plugin(self, plugin_class: Type[BaseTabPlugin], is_core: bool = False) -> None:
        """
        Register a plugin in the registry.

        Args:
            plugin_class: The plugin class to register
            is_core: Whether this is a core plugin
        """
        plugin_name = plugin_class.tab_name

        # Validate plugin
        errors = plugin_class.validate_plugin()
        if errors:
            raise ValueError(f"Invalid plugin '{plugin_name}': {', '.join(errors)}")

        # Check platform compatibility
        if not plugin_class.is_compatible():
            return  # Skip incompatible plugins
        
        # Check version compatibility
        gui_version = get_gui_version()
        min_version = getattr(plugin_class, 'min_gui_version', None)
        required_version = getattr(plugin_class, 'required_gui_version', None)
        
        if min_version or required_version:
            is_compatible, error_msg = check_version_compatibility(
                gui_version, 
                min_gui_version=min_version,
                required_gui_version=required_version
            )
            
            if not is_compatible:
                self._version_incompatibilities[plugin_name] = error_msg or "Version incompatible"
                logger.warning(
                    f"Plugin '{plugin_name}' version requirement not met: "
                    f"{error_msg}. Skipping registration."
                )
                return  # Skip version-incompatible plugins
            else:
                logger.debug(
                    f"Plugin '{plugin_name}' version compatibility check passed: "
                    f"GUI {gui_version} meets requirements "
                    f"(min: {min_version}, required: {required_version})"
                )

        # Handle name conflicts: core plugins take priority over external plugins
        if plugin_name in self._plugins:
            existing_is_core = plugin_name in self._core_plugins
            if existing_is_core and not is_core:
                # Skip external plugin that conflicts with existing core plugin
                logger.warning(f"Skipping external plugin '{plugin_name}' - conflicts with existing core plugin")
                return
            elif not existing_is_core and is_core:
                # Replace external plugin with core plugin (core takes priority)
                logger.info(f"Replacing external plugin '{plugin_name}' with core plugin")
                # Remove from external plugins
                if plugin_name in self._external_plugins:
                    del self._external_plugins[plugin_name]

        self._plugins[plugin_name] = plugin_class

        if is_core:
            self._core_plugins[plugin_name] = plugin_class
        else:
            self._external_plugins[plugin_name] = plugin_class

        # Apply default disabled state only on first sight in this app session,
        # and do not override an existing user-enabled state
        try:
            if (
                getattr(plugin_class, 'disabled_by_default', False)
                and plugin_name not in self._seen_plugins
                and plugin_name not in self._disabled_plugins
            ):
                self._disabled_plugins.add(plugin_name)
        except Exception:
            pass

        # Mark as seen for this session
        self._seen_plugins.add(plugin_name)

    def get_all_plugins(self) -> Dict[str, BaseTabPlugin]:
        """Get all registered plugins."""
        return self._plugins.copy()

    def get_core_plugins(self) -> Dict[str, BaseTabPlugin]:
        """Get core plugins only."""
        return self._core_plugins.copy()

    def get_external_plugins(self) -> Dict[str, BaseTabPlugin]:
        """Get external plugins only."""
        return self._external_plugins.copy()

    def get_plugin(self, name: str) -> Optional[BaseTabPlugin]:
        """Get a specific plugin by name."""
        return self._plugins.get(name)

    def list_plugin_names(self) -> List[str]:
        """Get list of all plugin names."""
        return list(self._plugins.keys())

    def clear(self) -> None:
        """Clear all registered plugins."""
        self._plugins.clear()
        self._core_plugins.clear()
        self._external_plugins.clear()
        self._disabled_plugins.clear()
        self._version_incompatibilities.clear()
        self._seen_plugins.clear()

    def get_version_incompatibility(self, name: str) -> Optional[str]:
        """
        Get the version incompatibility reason for a plugin, if any.
        
        Args:
            name: Plugin name
            
        Returns:
            Incompatibility message if plugin was rejected due to version, None otherwise
        """
        return self._version_incompatibilities.get(name)

    def disable_plugin(self, name: str) -> None:
        """Disable a plugin by name."""
        self._disabled_plugins.add(name)

    def enable_plugin(self, name: str) -> None:
        """Enable a plugin by name."""
        self._disabled_plugins.discard(name)

    def is_enabled(self, name: str) -> bool:
        """Check if a plugin is enabled."""
        return name not in self._disabled_plugins

    def get_enabled_plugins(self) -> Dict[str, Type[BaseTabPlugin]]:
        """Get all enabled plugins."""
        return {k: v for k, v in self._plugins.items() if self.is_enabled(k)}


# Global plugin registry instance
plugin_registry = PluginRegistry()


__all__ = ['PluginRegistry', 'plugin_registry']