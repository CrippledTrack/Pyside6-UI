"""
Plugin management controller.

This module provides PluginController to handle plugin toggling, discovery,
and state management, extracted from MainWindow.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Callable, TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from ....plugin_system.registry import plugin_registry
from ....plugin_system.interfaces import (
    MenuExtension,
    StatusExtension,
    ToolbarExtension,
    ServiceExtension,
)

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
        
        # For dynamic extension integration
        self._main_window = None
        self._plugin_toolbar = None
        
        # Track extension components per plugin for removal on disable
        self._plugin_menu_actions: Dict[str, list] = {}  # plugin_name -> [(QAction, QMenu), ...]
        self._plugin_toolbar_actions: Dict[str, list] = {}  # plugin_name -> [QAction, ...]
        self._plugin_status_widgets: Dict[str, list] = {}  # plugin_name -> [QWidget, ...]
        self._plugin_created_menus: Dict[str, list] = {}  # plugin_name -> [QMenu, ...] menus created by plugin
        self._service_extensions_started: bool = False  # Track if service extensions have been started
        
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
            # Enable in registry if not already enabled
            if not self.plugin_service.is_enabled(plugin_name):
                self.plugin_service.enable_plugin(plugin_name)
                logger.info(f"Enabled plugin: {plugin_name}")
                # Publish event for EventSubscriberExtension plugins
                plugin_registry.publish_event("plugin_enabled", {"plugin_name": plugin_name})
            
            # Always try to integrate extensions (handles re-enable case)
            # Only integrates if not already integrated (tracking dicts are empty for this plugin)
            logger.debug(f"Checking dynamic integration: _main_window = {self._main_window}")
            if self._main_window is not None:
                # Check if extensions are already integrated
                has_menu = plugin_name in self._plugin_menu_actions
                has_toolbar = plugin_name in self._plugin_toolbar_actions
                has_status = plugin_name in self._plugin_status_widgets
                
                if not (has_menu or has_toolbar or has_status):
                    self._integrate_plugin_extensions_dynamic(plugin_name, plugin_class)
                else:
                    logger.debug(f"Extensions already integrated for '{plugin_name}'")
            else:
                logger.warning(f"Cannot dynamically integrate extensions for '{plugin_name}': MainWindow not set")
        else:
            if self.plugin_service.is_enabled(plugin_name):
                self.plugin_service.disable_plugin(plugin_name)
                logger.info(f"Disabled plugin: {plugin_name}")
                # Publish event for EventSubscriberExtension plugins
                plugin_registry.publish_event("plugin_disabled", {"plugin_name": plugin_name})
                
                # Remove dynamically integrated extensions
                if self._main_window is not None:
                    self._remove_plugin_extensions_dynamic(plugin_name, plugin_class)
        
        self._save_plugin_states()
        self.plugin_toggled.emit(plugin_name, enabled)
        self.plugin_state_changed.emit()
        
        return True
    
    def _integrate_plugin_extensions_dynamic(self, plugin_name: str, plugin_class: type) -> None:
        """Integrate extensions for a single plugin that was just enabled.
        
        Args:
            plugin_name: Name of the plugin
            plugin_class: The plugin class
        """
        
        try:
            # Integrate Menu Extension
            if issubclass(plugin_class, MenuExtension):
                self._integrate_menu_extension(plugin_name, plugin_class)
                logger.info(f"Dynamically integrated menu extension for '{plugin_name}'")
            
            # Integrate Status Extension
            if issubclass(plugin_class, StatusExtension):
                self._integrate_status_extension(plugin_name, plugin_class)
                logger.info(f"Dynamically integrated status extension for '{plugin_name}'")
            
            # Integrate Toolbar Extension (adds to Plugins menu)
            if issubclass(plugin_class, ToolbarExtension):
                self._integrate_toolbar_extension(plugin_name, plugin_class)
                logger.info(f"Dynamically integrated toolbar extension for '{plugin_name}'")
            
            # Start Service Extension
            if issubclass(plugin_class, ServiceExtension):
                plugin_class.on_application_start(self.container)
                logger.info(f"Dynamically started service extension for '{plugin_name}'")
        except Exception as e:
            logger.error(f"Error dynamically integrating extensions for '{plugin_name}': {e}")
    
    def _remove_plugin_extensions_dynamic(self, plugin_name: str, plugin_class: type) -> None:
        """Remove extensions for a plugin that was just disabled.
        
        Args:
            plugin_name: Name of the plugin
            plugin_class: The plugin class
        """
        
        try:
            # Remove menu actions - stored as (action, target_menu) tuples
            if plugin_name in self._plugin_menu_actions:
                for action, target_menu in self._plugin_menu_actions[plugin_name]:
                    try:
                        if target_menu:
                            target_menu.removeAction(action)
                    except Exception as e:
                        logger.debug(f"Error removing menu action: {e}")
                del self._plugin_menu_actions[plugin_name]
                logger.info(f"Removed menu extensions for '{plugin_name}'")
            
            # Remove menus that were created by this plugin
            if plugin_name in self._plugin_created_menus:
                menu_bar = self._main_window.menuBar()
                for menu in self._plugin_created_menus[plugin_name]:
                    try:
                        # Find and remove the menu's action from the menu bar
                        for action in menu_bar.actions():
                            if action.menu() == menu:
                                menu_bar.removeAction(action)
                                logger.debug(f"Removed created menu '{menu.title()}' for '{plugin_name}'")
                                break
                    except Exception as e:
                        logger.debug(f"Error removing created menu: {e}")
                del self._plugin_created_menus[plugin_name]
            
            # Remove toolbar actions
            if plugin_name in self._plugin_toolbar_actions:
                for action in self._plugin_toolbar_actions[plugin_name]:
                    try:
                        if self._plugin_toolbar:
                            self._plugin_toolbar.removeAction(action)
                    except Exception as e:
                        logger.debug(f"Error removing toolbar action: {e}")
                del self._plugin_toolbar_actions[plugin_name]
                
                # Hide toolbar if empty
                if self._plugin_toolbar and not self._plugin_toolbar.actions():
                    self._plugin_toolbar.hide()
                    
                logger.info(f"Removed toolbar extensions for '{plugin_name}'")
            
            # Remove status widgets
            if plugin_name in self._plugin_status_widgets:
                for widget in self._plugin_status_widgets[plugin_name]:
                    try:
                        self._main_window.statusBar().removeWidget(widget)
                        widget.hide()  # Hide instead of delete to avoid corruption
                    except Exception as e:
                        logger.debug(f"Error removing status widget: {e}")
                del self._plugin_status_widgets[plugin_name]
                logger.info(f"Removed status extensions for '{plugin_name}'")
            
            # Shutdown Service Extension
            if issubclass(plugin_class, ServiceExtension):
                try:
                    plugin_class.on_application_shutdown()
                    logger.info(f"Shutdown service extension for '{plugin_name}'")
                except Exception as e:
                    logger.error(f"Error shutting down service extension '{plugin_name}': {e}")
                    
        except Exception as e:
            logger.error(f"Error removing extensions for '{plugin_name}': {e}")
    
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
    
    # =========================================================================
    # v3.4.0 Extension Integration
    # =========================================================================
    
    def cleanup_all_extensions(self) -> None:
        """Clean up all previously integrated extensions.
        
        This removes all menu actions, toolbar actions, status widgets,
        and shuts down all ServiceExtension plugins. Used before reloading
        plugins to prevent duplicates.
        """
        if not self._main_window:
            # Nothing to clean up if main window isn't set
            return
        
        logger.info("Cleaning up all plugin extensions...")
        
        try:
            # Shutdown all ServiceExtension plugins first (only if they were started)
            if self._service_extensions_started:
                self.shutdown_service_extensions()
            
            # Remove all menu actions
            for plugin_name in list(self._plugin_menu_actions.keys()):
                for action, target_menu in self._plugin_menu_actions[plugin_name]:
                    try:
                        if target_menu:
                            target_menu.removeAction(action)
                    except Exception as e:
                        logger.debug(f"Error removing menu action: {e}")
                del self._plugin_menu_actions[plugin_name]
            
            # Remove all menus created by plugins
            menu_bar = self._main_window.menuBar()
            for plugin_name in list(self._plugin_created_menus.keys()):
                for menu in self._plugin_created_menus[plugin_name]:
                    try:
                        # Find and remove the menu's action from the menu bar
                        for action in menu_bar.actions():
                            if action.menu() == menu:
                                menu_bar.removeAction(action)
                                logger.debug(f"Removed created menu '{menu.title()}' for '{plugin_name}'")
                                break
                    except Exception as e:
                        logger.debug(f"Error removing created menu: {e}")
                del self._plugin_created_menus[plugin_name]
            
            # Remove all toolbar actions from the plugin toolbar
            for plugin_name in list(self._plugin_toolbar_actions.keys()):
                for action in self._plugin_toolbar_actions[plugin_name]:
                    try:
                        if self._plugin_toolbar:
                            self._plugin_toolbar.removeAction(action)
                    except Exception as e:
                        logger.debug(f"Error removing toolbar action: {e}")
                del self._plugin_toolbar_actions[plugin_name]
            
            # Hide toolbar if empty
            if self._plugin_toolbar and not self._plugin_toolbar.actions():
                self._plugin_toolbar.hide()
            
            logger.info("Cleaned up all plugin extensions")
        except Exception as e:
            logger.error(f"Error cleaning up extensions: {e}")
    
    def integrate_extensions(self, main_window: Any) -> None:
        """Integrate all v3.4.0 plugin extensions into the main window.
        
        Args:
            main_window: The MainWindow instance to integrate into
        """
        
        self._main_window = main_window
        
        # Clean up any previously integrated extensions to prevent duplicates
        self.cleanup_all_extensions()
        
        try:
            # Integrate Menu Extensions
            menu_plugins = plugin_registry.get_menu_extensions(enabled_only=True)
            for name, plugin_class in menu_plugins.items():
                try:
                    self._integrate_menu_extension(name, plugin_class)
                except Exception as e:
                    logger.error(f"Failed to integrate menu extension '{name}': {e}")
            
            # Integrate Status Extensions
            status_plugins = plugin_registry.get_status_extensions(enabled_only=True)
            for name, plugin_class in status_plugins.items():
                try:
                    self._integrate_status_extension(name, plugin_class)
                except Exception as e:
                    logger.error(f"Failed to integrate status extension '{name}': {e}")
            
            # Integrate Toolbar Extensions (now adds to Plugins menu)
            toolbar_plugins = plugin_registry.get_toolbar_extensions(enabled_only=True)
            for name, plugin_class in toolbar_plugins.items():
                try:
                    self._integrate_toolbar_extension(name, plugin_class)
                except Exception as e:
                    logger.error(f"Failed to integrate toolbar extension '{name}': {e}")
            
            # Initialize Service Extensions
            self.start_service_extensions()
            
            logger.info(f"Integrated extensions: {len(menu_plugins)} menu, {len(status_plugins)} status, "
                       f"{len(toolbar_plugins)} toolbar")
        except Exception as e:
            logger.error(f"Error integrating plugin extensions: {e}")
    
    def _integrate_menu_extension(self, name: str, plugin_class: type) -> None:
        """Add menu items from a MenuExtension plugin."""
        from PySide6.QtGui import QAction
        
        menu_items = plugin_class.get_menu_items()
        menu_bar = self._main_window.menuBar()
        
        # Track actions for this plugin as (action, target_menu) tuples
        if name not in self._plugin_menu_actions:
            self._plugin_menu_actions[name] = []
        if name not in self._plugin_created_menus:
            self._plugin_created_menus[name] = []
        
        for item in menu_items:
            # Find or create the target menu
            target_menu = None
            menu_was_created = False
            for action in menu_bar.actions():
                if action.text().replace("&", "") == item.menu:
                    target_menu = action.menu()
                    break
            
            if target_menu is None:
                # Create new menu - track that we created it
                target_menu = menu_bar.addMenu(item.menu)
                self._plugin_created_menus[name].append(target_menu)
                menu_was_created = True
            
            # Add separator before if requested
            if item.separator_before:
                sep_action = target_menu.addSeparator()
                self._plugin_menu_actions[name].append((sep_action, target_menu))
            
            # Create action
            action = QAction(item.label, self._main_window)
            action.triggered.connect(item.callback)
            if item.shortcut:
                action.setShortcut(item.shortcut)
            action.setEnabled(item.enabled)
            target_menu.addAction(action)
            
            # Track the action AND menu for removal on disable
            self._plugin_menu_actions[name].append((action, target_menu))
            
            # Add separator after if requested
            if item.separator_after:
                sep_action = target_menu.addSeparator()
                self._plugin_menu_actions[name].append((sep_action, target_menu))
            
            logger.debug(f"Added menu item '{item.label}' to '{item.menu}' from plugin '{name}'")
    
    def _integrate_status_extension(self, name: str, plugin_class: type) -> None:
        """Add status bar widget from a StatusExtension plugin."""
        widget = plugin_class.create_status_widget(self._main_window.statusBar())
        if widget:
            self._main_window.statusBar().addPermanentWidget(widget)
            # Track widget for removal on disable
            if name not in self._plugin_status_widgets:
                self._plugin_status_widgets[name] = []
            self._plugin_status_widgets[name].append(widget)
            logger.debug(f"Added status bar widget from plugin '{name}'")
    
    def _get_or_create_plugin_toolbar(self):
        """Get or create the plugin toolbar."""
        from PySide6.QtWidgets import QToolBar
        from PySide6.QtCore import Qt
        
        # Return cached toolbar if exists
        if self._plugin_toolbar is not None:
            return self._plugin_toolbar
        
        # Create new toolbar
        toolbar = QToolBar("Plugin Toolbar", self._main_window)
        toolbar.setObjectName("PluginToolbar")
        toolbar.setMovable(True)
        toolbar.setFloatable(True)
        
        # Add to main window
        self._main_window.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
        
        self._plugin_toolbar = toolbar
        logger.debug("Created plugin toolbar")
        return toolbar
    
    def _integrate_toolbar_extension(self, name: str, plugin_class: type) -> None:
        """Add toolbar actions from a ToolbarExtension plugin to the plugin toolbar."""
        from PySide6.QtGui import QAction
        
        actions = plugin_class.get_toolbar_actions()
        
        # Track actions for this plugin
        if name not in self._plugin_toolbar_actions:
            self._plugin_toolbar_actions[name] = []
        
        # Get or create plugin toolbar
        toolbar = self._get_or_create_plugin_toolbar()
        
        for action_def in actions:
            action = QAction(action_def.label, self._main_window)
            action.triggered.connect(action_def.callback)
            if action_def.tooltip:
                action.setToolTip(action_def.tooltip)
            if action_def.checkable:
                action.setCheckable(True)
                action.setChecked(action_def.checked)
            toolbar.addAction(action)
            
            # Track the action for removal on disable
            self._plugin_toolbar_actions[name].append(action)
            
            logger.debug(f"Added toolbar action '{action_def.label}' from plugin '{name}'")
        
        # Ensure toolbar is visible when actions are added
        if toolbar.actions():
            toolbar.show()

    
    def start_service_extensions(self) -> None:
        """Start all ServiceExtension plugins."""
        from ....plugin_system.registry import plugin_registry
        
        try:
            service_plugins = plugin_registry.get_service_extensions(enabled_only=True)
            for name, plugin_class in service_plugins.items():
                try:
                    logger.info(f"Starting service extension: {name}")
                    plugin_class.on_application_start(self.container)
                except Exception as e:
                    logger.error(f"Failed to start service extension '{name}': {e}")
            # Mark that service extensions have been started
            self._service_extensions_started = True
        except Exception as e:
            logger.error(f"Error starting service extensions: {e}")
    
    def shutdown_service_extensions(self) -> None:
        """Shutdown all ServiceExtension plugins."""
        from ....plugin_system.registry import plugin_registry
        
        try:
            service_plugins = plugin_registry.get_service_extensions(enabled_only=True)
            for name, plugin_class in service_plugins.items():
                try:
                    logger.info(f"Shutting down service extension: {name}")
                    plugin_class.on_application_shutdown()
                except Exception as e:
                    logger.error(f"Error shutting down service extension '{name}': {e}")
            # Mark that service extensions have been shut down
            self._service_extensions_started = False
        except Exception as e:
            logger.error(f"Error shutting down service extensions: {e}")


__all__ = ['PluginController']
