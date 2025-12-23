"""
Plugin management controller.

This module provides PluginController to handle plugin toggling, discovery,
and state management, extracted from MainWindow.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Callable, TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from ...services.container import ServiceContainer
    from ....plugin_system.base import BaseTabPlugin

logger = logging.getLogger(__name__)


class PluginController(QObject):
    """Controller for managing plugins and their lifecycle."""
    
    # Signals
    plugin_toggled = Signal(str, bool)  # Emitted when a plugin is toggled (name, enabled)
    plugin_state_changed = Signal()  # Emitted when plugin states change
    
    def __init__(
        self,
        container: "ServiceContainer",
        parent: Optional[QObject] = None
    ) -> None:
        """Initialize the plugin controller.
        
        Args:
            container: Service container for dependency injection
            parent: Optional parent object
        """
        super().__init__(parent)
        self.container = container
        
        # Retrieve services from container
        from ...services.settings_service import SettingsService
        from ...services.plugin_service import PluginService
        
        self.settings_service = container.get(SettingsService)
        self.plugin_service = container.get(PluginService)
    
    def toggle_plugin(self, plugin_name: str, enabled: bool) -> bool:
        """Toggle a plugin on or off.
        
        Args:
            plugin_name: Name of the plugin to toggle
            enabled: True to enable, False to disable
            
        Returns:
            True if toggle was successful, False otherwise
        """
        plugin_class = self.plugin_service.get_plugin(plugin_name)
        if not plugin_class:
            logger.warning(f"Plugin '{plugin_name}' not found")
            return False
        
        if enabled:
            if not self.plugin_service.is_enabled(plugin_name):
                self.plugin_service.enable_plugin(plugin_name)
                logger.info(f"Enabled plugin: {plugin_name}")
        else:
            if self.plugin_service.is_enabled(plugin_name):
                self.plugin_service.disable_plugin(plugin_name)
                logger.info(f"Disabled plugin: {plugin_name}")
        
        self._save_plugin_states()
        self.plugin_toggled.emit(plugin_name, enabled)
        self.plugin_state_changed.emit()
        
        return True
    
    def is_plugin_enabled(self, plugin_name: str) -> bool:
        """Check if a plugin is enabled.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            True if enabled, False otherwise
        """
        return self.plugin_service.is_enabled(plugin_name)
    
    def get_plugin(self, plugin_name: str) -> Optional[Any]:
        """Get a plugin class by name.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            Plugin class or None if not found
        """
        return self.plugin_service.get_plugin(plugin_name)
    
    def get_enabled_plugins(self) -> Dict[str, Any]:
        """Get all enabled plugins.
        
        Returns:
            Dictionary mapping plugin names to plugin classes
        """
        return self.plugin_service.get_enabled_plugins()
    
    def get_all_plugins(self) -> Dict[str, Any]:
        """Get all registered plugins.
        
        Returns:
            Dictionary mapping plugin names to plugin classes
        """
        return self.plugin_service.get_all_plugins()
    
    def list_plugin_names(self) -> list[str]:
        """List all registered plugin names.
        
        Returns:
            List of plugin names
        """
        return self.plugin_service.list_plugin_names()
    
    def get_plugin_info(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a plugin.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            Plugin info dictionary or None if not found
        """
        plugin_class = self.plugin_service.get_plugin(plugin_name)
        if not plugin_class:
            return None
        
        return plugin_class.get_plugin_info()
    
    def _save_plugin_states(self) -> None:
        """Save plugin states to settings.
        
        This method saves user-disabled plugins (excludes plugins disabled by default).
        """
        if not self.settings_service:
            return
        
        try:
            # Determine which plugins are disabled by the user (not by default)
            all_disabled = [
                name for name in self.plugin_service.list_plugin_names()
                if not self.plugin_service.is_enabled(name)
            ]
            
            # Filter out plugins that are disabled_by_default
            user_disabled = []
            for plugin_name in all_disabled:
                plugin_class = self.plugin_service.get_plugin(plugin_name)
                if plugin_class and not getattr(plugin_class, 'disabled_by_default', False):
                    user_disabled.append(plugin_name)
            
            logger.debug(f"Saving user-disabled plugins: {user_disabled}")
            self.settings_service.save_disabled_plugins(user_disabled)
        except Exception as e:
            logger.warning(f"Failed to save plugin states: {e}")
    
    def load_plugin_states(self) -> None:
        """Load plugin states from settings.
        
        This method loads user-disabled plugins from settings and applies them.
        Also cleans up any disabled_by_default plugins that were incorrectly saved.
        """
        if not self.settings_service:
            return
        
        try:
            saved_disabled = self.settings_service.get_disabled_plugins()
            if saved_disabled:
                logger.info(f"Loading saved user-disabled plugins: {saved_disabled}")
                
                # Filter out plugins that are disabled_by_default (they shouldn't be in settings)
                cleaned_disabled = []
                for plugin_name in saved_disabled:
                    plugin_class = self.plugin_service.get_plugin(plugin_name)
                    if plugin_class:
                        if getattr(plugin_class, 'disabled_by_default', False):
                            logger.debug(f"Removing disabled_by_default plugin from settings: {plugin_name}")
                        else:
                            self.plugin_service.disable_plugin(plugin_name)
                            cleaned_disabled.append(plugin_name)
                            logger.debug(f"Applied user preference: {plugin_name} disabled")
                    else:
                        # Plugin no longer exists, don't include in cleaned list
                        logger.debug(f"Skipping non-existent plugin: {plugin_name}")
                
                # Re-save if we cleaned up any entries
                if len(cleaned_disabled) != len(saved_disabled):
                    logger.info(f"Cleaning up settings: removed {len(saved_disabled) - len(cleaned_disabled)} disabled_by_default plugins")
                    self.settings_service.save_disabled_plugins(cleaned_disabled)
        except Exception as e:
            logger.warning(f"Failed to load plugin states: {e}")


__all__ = ['PluginController']
