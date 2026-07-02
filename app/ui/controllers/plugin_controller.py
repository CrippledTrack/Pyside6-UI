"""
Plugin management controller.

This module provides PluginController to handle plugin toggling, discovery,
and state management, extracted from MainWindow.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Callable, TYPE_CHECKING

from ...qt_bindings import QObject, Signal

from ...qt_bindings import is_valid as _qt_is_valid

from ...services.plugin_service import PluginService
from ...services.interfaces import ISettingsService
from ...services.plugin_registry_facade import PluginRegistryFacade

if TYPE_CHECKING:
    from ...services.container import ServiceContainer
    from ...services.interfaces import IMainWindowDelegate

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
        self._main_window: Optional[IMainWindowDelegate] = None
        
        # Track extension components per plugin for removal on disable
        self._plugin_menu_actions: Dict[str, list] = {}  # plugin_name -> [(action, target_menu), ...]
        self._plugin_toolbar_actions: Dict[str, list] = {}  # plugin_name -> [action, ...]
        self._plugin_status_widgets: Dict[str, list] = {}  # plugin_name -> [widget, ...]
        self._plugin_created_menus: Dict[str, list] = {}  # plugin_name -> [menu, ...] menus created by plugin
        self._service_extensions_started: bool = False  # Track if service extensions have been started

        # Map of extension names to integration functions
        self._integration_handlers = {
            "Menu": self._integrate_menu_extension,
            "Status": self._integrate_status_extension,
            "Toolbar": self._integrate_toolbar_extension,
            "Service": self._integrate_service_extension,
        }
        
        # Retrieve services from container
        
        self.settings_service = container.get(ISettingsService)
        self.plugin_service = container.get(PluginService)
        self.registry = container.get(PluginRegistryFacade)
    
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
                # Call lifecycle hook on plugin instance
                try:
                    instance = self.registry.get_plugin_instance(plugin_name)
                    if hasattr(instance, 'on_plugin_enabled'):
                        instance.on_plugin_enabled()
                except Exception as e:
                    logger.error(f"Error calling on_plugin_enabled for '{plugin_name}': {e}")
                # Publish event for EventSubscriberExtension plugins
                self.registry.publish_event("plugin_enabled", {"plugin_name": plugin_name})
            
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
                # Call lifecycle hook on plugin instance
                try:
                    if self.registry.has_plugin_instance(plugin_name):
                        instance = self.registry.get_plugin_instance(plugin_name)
                        if hasattr(instance, 'on_plugin_disabled'):
                            instance.on_plugin_disabled()
                except Exception as e:
                    logger.error(f"Error calling on_plugin_disabled for '{plugin_name}': {e}")
                self.plugin_service.disable_plugin(plugin_name)
                logger.info(f"Disabled plugin: {plugin_name}")
                # Publish event for EventSubscriberExtension plugins
                self.registry.publish_event("plugin_disabled", {"plugin_name": plugin_name})
            
            # Always try to remove extensions when disabling, even if already disabled in registry
            # This handles cases where the dialog disabled it first but we still need UI cleanup
            if self._main_window is not None:
                self._remove_plugin_extensions_dynamic(plugin_name, plugin_class)
        
        self._save_plugin_states()
        self.plugin_toggled.emit(plugin_name, enabled)
        self.plugin_state_changed.emit()
        
        # Clear plugin instance from cache if disabling to prevent resource leaks
        if not enabled:
            try:
                self.registry.unload_plugin_instance(plugin_name)
            except Exception as e:
                logger.error(f"Error unloading plugin instance '{plugin_name}': {e}")
        
        return True
    
    def _integrate_plugin_extensions_dynamic(self, plugin_name: str, plugin_class: type) -> None:
        """Integrate extensions for a single plugin that was just enabled.
        
        Args:
            plugin_name: Name of the plugin
            plugin_class: The plugin class
        """
        try:
            from ....plugin_system.extensions import EXTENSION_POINTS
            for ep in EXTENSION_POINTS:
                if ep.name in self._integration_handlers:
                    if ep.check_implements(plugin_class):
                        toggle_name = ep.parent_toggle if ep.parent_toggle else ep.name
                        if self._is_extension_enabled(plugin_name, toggle_name):
                            handler = self._integration_handlers[ep.name]
                            handler(plugin_name, plugin_class)
                            logger.info(f"Dynamically integrated {ep.name} extension for '{plugin_name}'")
                        else:
                            logger.debug(f"{ep.name} extension disabled for '{plugin_name}'")
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
                        if self._main_window:
                            self._main_window.remove_menu_action(action, target_menu)
                    except Exception as e:
                        logger.debug(f"Error removing menu action: {e}")
                
                # Check if we should remove the menus created by this plugin
                if self._main_window and plugin_name in self._plugin_created_menus:
                    for menu in self._plugin_created_menus[plugin_name]:
                        try:
                            self._main_window.remove_menu_if_empty(menu)
                        except Exception as e:
                            logger.debug(f"Error removing empty menu: {e}")
                            
                del self._plugin_menu_actions[plugin_name]
                if plugin_name in self._plugin_created_menus:
                    del self._plugin_created_menus[plugin_name]
                logger.info(f"Removed menu extensions for '{plugin_name}'")
            
            # Remove toolbar actions
            if plugin_name in self._plugin_toolbar_actions:
                for action in self._plugin_toolbar_actions[plugin_name]:
                    try:
                        if self._main_window:
                            self._main_window.remove_toolbar_action(action)
                    except Exception as e:
                        logger.debug(f"Error removing toolbar action: {e}")
                del self._plugin_toolbar_actions[plugin_name]
                logger.info(f"Removed toolbar actions for '{plugin_name}'")
            
            # Remove status widgets
            if plugin_name in self._plugin_status_widgets:
                for widget in self._plugin_status_widgets[plugin_name]:
                    try:
                        if self._main_window:
                            self._main_window.remove_status_widget(widget)
                    except Exception as e:
                        logger.debug(f"Error removing status widget: {e}")
                del self._plugin_status_widgets[plugin_name]
                logger.info(f"Removed status extensions for '{plugin_name}'")
            
            # Shutdown Service Extension (has on_application_shutdown method)
            if hasattr(plugin_class, 'on_application_shutdown'):
                try:
                    # Get instance
                    # If it was running, instance should exist
                    if self.registry.has_plugin_instance(plugin_name):
                        instance = self.registry.get_plugin_instance(plugin_name)
                        instance.on_application_shutdown()
                        logger.info(f"Shutdown service extension for '{plugin_name}'")
                    else:
                        logger.debug(
                            "Skipping service shutdown for '%s' - instance not created",
                            plugin_name
                        )
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
    
    def refresh_plugin_extensions(self, plugin_name: str) -> None:
        """Refresh extensions for a plugin to apply extension type toggle changes.
        
        This removes all existing extensions and re-integrates them based on
        current settings (respecting extension type enabled states).
        
        Args:
            plugin_name: Name of the plugin to refresh
        """
        if not self._main_window:
            logger.debug("Cannot refresh extensions: MainWindow not set")
            return
        
        plugin_class = self.plugin_service.get_plugin(plugin_name)
        if not plugin_class:
            logger.warning(f"Plugin '{plugin_name}' not found")
            return
        
        if not self.plugin_service.is_enabled(plugin_name):
            logger.debug(f"Plugin '{plugin_name}' is disabled, skipping refresh")
            return
        
        # Remove existing extensions for this plugin
        self._remove_plugin_extensions_dynamic(plugin_name, plugin_class)
        
        # Re-integrate with current settings
        self._integrate_plugin_extensions_dynamic(plugin_name, plugin_class)
        
        # Handle Dynamic Tab Extension Toggle
        # We need to manually handle this because tabs are normally managed by MainWindow via plugin_toggled
        if hasattr(plugin_class, 'create_widget') and self._main_window:
            should_have_tab = self._is_extension_enabled(plugin_name, "Tab")
            # Check if tab is currently loaded
            tab_exists = self._main_window.has_plugin_tab(plugin_name)
            
            if should_have_tab and not tab_exists:
                self._main_window.add_plugin_tab(plugin_name, plugin_class)
                logger.info(f"Dynamically added tab for '{plugin_name}'")
            elif not should_have_tab and tab_exists:
                self._main_window.remove_plugin_tab(plugin_name)
                logger.info(f"Dynamically removed tab for '{plugin_name}'")
        
        logger.info(f"Refreshed extensions for '{plugin_name}'")
    
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
    
    def _is_extension_enabled(self, plugin_name: str, extension_type: str) -> bool:
        """Check if a specific extension type is enabled for a plugin.
        
        Defaults to True if settings service is not available.
        """
        if not self.settings_service:
            return True
        return self.settings_service.is_extension_enabled(plugin_name, extension_type)
    
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
    # Extension Integration
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
                        self._main_window.remove_menu_action(action, target_menu)
                    except Exception as e:
                        logger.debug(f"Error removing menu action: {e}")
                del self._plugin_menu_actions[plugin_name]
            
            # Remove all menus created by plugins
            for plugin_name in list(self._plugin_created_menus.keys()):
                for menu in self._plugin_created_menus[plugin_name]:
                    try:
                        self._main_window.remove_menu_if_empty(menu)
                    except Exception as e:
                        logger.debug(f"Error removing created menu: {e}")
                del self._plugin_created_menus[plugin_name]
            
            # Remove all toolbar actions from the plugin toolbar
            for plugin_name in list(self._plugin_toolbar_actions.keys()):
                for action in self._plugin_toolbar_actions[plugin_name]:
                    try:
                        self._main_window.remove_toolbar_action(action)
                    except Exception as e:
                        logger.debug(f"Error removing toolbar action: {e}")
                del self._plugin_toolbar_actions[plugin_name]
            
            # Remove all status widgets
            for plugin_name in list(self._plugin_status_widgets.keys()):
                for widget in self._plugin_status_widgets[plugin_name]:
                    try:
                        self._main_window.remove_status_widget(widget)
                    except Exception as e:
                        logger.debug(f"Error removing status widget: {e}")
                del self._plugin_status_widgets[plugin_name]
            
            logger.info("Cleaned up all plugin extensions")
        except Exception as e:
            logger.error(f"Error cleaning up extensions: {e}")
    
    def integrate_extensions(self, main_window: IMainWindowDelegate) -> None:
        """Integrate all plugin extensions into the main window.
        
        Args:
            main_window: The MainWindow instance to integrate into
        """
        self._main_window = main_window
        
        # Clean up any previously integrated extensions to prevent duplicates
        self.cleanup_all_extensions()
        
        try:
            # Map of extension names to registry extension query functions
            registry_queries = {
                "Menu": self.registry.get_menu_extensions,
                "Status": self.registry.get_status_extensions,
                "Toolbar": self.registry.get_toolbar_extensions,
            }
            
            for ext_name, query_func in registry_queries.items():
                plugins = query_func(enabled_only=True)
                for name, plugin_class in plugins.items():
                    try:
                        if self._is_extension_enabled(name, ext_name):
                            handler = self._integration_handlers.get(ext_name)
                            if handler:
                                handler(name, plugin_class)
                        else:
                            logger.debug(f"{ext_name} extension disabled for '{name}'")
                    except Exception as e:
                        logger.error(f"Failed to integrate {ext_name} extension '{name}': {e}")
            
            # Initialize Service Extensions
            self.start_service_extensions()
            
            logger.info("Integrated extensions")
        except Exception as e:
            logger.error(f"Error integrating plugin extensions: {e}")
    
    def _integrate_menu_extension(self, name: str, plugin_class: type) -> None:
        """Add menu items from a MenuExtension plugin."""
        if not self._main_window:
            return
        
        # Get plugin instance
        instance = self.registry.get_plugin_instance(name)
        menu_items = instance.get_menu_items()
        
        # Track actions for this plugin as (action, target_menu) tuples
        if name not in self._plugin_menu_actions:
            self._plugin_menu_actions[name] = []
        if name not in self._plugin_created_menus:
            self._plugin_created_menus[name] = []
        
        for item in menu_items:
            # Delegate creation of menu item
            res = self._main_window.add_menu_action(
                menu_title=item.menu,
                label=item.label,
                callback=item.callback,
                shortcut=item.shortcut,
                icon=item.icon,
                enabled=item.enabled,
                separator_before=item.separator_before,
                separator_after=item.separator_after
            )
            action, target_menu, was_created, sep_before, sep_after = res
            
            if was_created:
                self._plugin_created_menus[name].append(target_menu)
                
            if sep_before:
                self._plugin_menu_actions[name].append((sep_before, target_menu))
                
            self._plugin_menu_actions[name].append((action, target_menu))
            
            if sep_after:
                self._plugin_menu_actions[name].append((sep_after, target_menu))
            
            logger.debug(f"Added menu item '{item.label}' to '{item.menu}' from plugin '{name}'")
    
    def _integrate_status_extension(self, name: str, plugin_class: type) -> None:
        """Add status bar widget from a StatusExtension plugin."""
        if not self._main_window:
            return
            
        # Get plugin instance
        instance = self.registry.get_plugin_instance(name)
        widget = self._main_window.add_status_widget_for_plugin(name, instance)
        if widget:
            # Track widget for removal on disable
            if name not in self._plugin_status_widgets:
                self._plugin_status_widgets[name] = []
            self._plugin_status_widgets[name].append(widget)
            logger.debug(f"Added status bar widget from plugin '{name}'")
    
    def _integrate_toolbar_extension(self, name: str, plugin_class: type) -> None:
        """Add toolbar actions from a ToolbarExtension plugin to the plugin toolbar."""
        if not self._main_window:
            return
            
        # Get plugin instance
        instance = self.registry.get_plugin_instance(name)
        actions = instance.get_toolbar_actions()
        
        # Track actions for this plugin
        if name not in self._plugin_toolbar_actions:
            self._plugin_toolbar_actions[name] = []
        
        for action_def in actions:
            action = self._main_window.add_toolbar_action(
                label=action_def.label,
                callback=action_def.callback,
                icon=action_def.icon,
                tooltip=action_def.tooltip,
                checkable=action_def.checkable,
                checked=action_def.checked
            )
            if action:
                self._plugin_toolbar_actions[name].append(action)
                logger.debug(f"Added toolbar action '{action_def.label}' from plugin '{name}'")
    
    def _integrate_service_extension(self, name: str, plugin_class: type) -> None:
        """Start a ServiceExtension plugin."""
        instance = self.registry.get_plugin_instance(name)
        logger.info(f"Starting service extension: {name}")
        instance.on_application_start(self.container)

    def start_service_extensions(self) -> None:
        """Start all ServiceExtension plugins."""
        try:
            service_plugins = self.registry.get_service_extensions(enabled_only=True)
            for name, plugin_class in service_plugins.items():
                try:
                    if self._is_extension_enabled(name, "Service"):
                        self._integrate_service_extension(name, plugin_class)
                    else:
                        logger.debug(f"Service extension disabled for '{name}'")
                except Exception as e:
                    logger.error(f"Failed to start service extension '{name}': {e}")
            # Mark that service extensions have been started
            self._service_extensions_started = True
        except Exception as e:
            logger.error(f"Error starting service extensions: {e}")
    
    def shutdown_service_extensions(self) -> None:
        """Shutdown all ServiceExtension plugins."""
        
        try:
            service_plugins = self.registry.get_service_extensions(enabled_only=True)
            for name, plugin_class in service_plugins.items():
                try:
                    # Get plugin instance and shutdown service
                    # Note: We need the instance to be created/cached even if we are shutting down
                    # But typically if it was running, it should be in cache
                    if self.registry.has_plugin_instance(name):
                        instance = self.registry.get_plugin_instance(name)
                        logger.info(f"Shutting down service extension: {name}")
                        instance.on_application_shutdown()
                except Exception as e:
                    logger.error(f"Error shutting down service extension '{name}': {e}")
            # Mark that service extensions have been shut down
            self._service_extensions_started = False
        except Exception as e:
            logger.error(f"Error shutting down service extensions: {e}")


__all__ = ['PluginController']
