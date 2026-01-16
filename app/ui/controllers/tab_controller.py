"""
Tab management controller.

This module provides TabController to handle tab creation, loading,
activation/deactivation, and lifecycle management, extracted from MainWindow.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Callable, TYPE_CHECKING

from PySide6.QtCore import Signal, QObject
from PySide6.QtWidgets import QTabWidget, QWidget

from ...constants import CURRENT_PLATFORM

if TYPE_CHECKING:
    from ...services.container import ServiceContainer
    from ....plugin_system.base import BaseTabPlugin

from ...services.plugin_registry_facade import PluginRegistryFacade

from ..widgets.admin_required_placeholder import AdminRequiredPlaceholder
from ..widgets.error_placeholder import ErrorPlaceholder
from ..widgets.loading_placeholder import LoadingPlaceholder
from ...utils.admin import needs_admin_for_plugin

logger = logging.getLogger(__name__)


class TabController(QObject):
    """Controller for managing tabs and their lifecycle."""
    
    # Signals
    tab_added = Signal(str)  # Emitted when a tab is added
    tab_removed = Signal(str)  # Emitted when a tab is removed
    tab_activated = Signal(str)  # Emitted when a tab is activated
    tab_deactivated = Signal(str)  # Emitted when a tab is deactivated
    title_update_requested = Signal()  # Emitted when window title should be updated
    
    def __init__(
        self,
        tab_widget: QTabWidget,
        container: "ServiceContainer",
        parent: Optional[QObject] = None
    ) -> None:
        """Initialize the tab controller.
        
        Args:
            tab_widget: The tab widget to manage
            container: Service container for dependency injection
            parent: Optional parent object
        """
        super().__init__(parent)
        self.tab_widget = tab_widget
        self.container = container
        
        # Retrieve services from container
        from ...services.admin_service import AdminService
        from ...services.daemon_service import DaemonService
        
        self.admin_service = container.get(AdminService)
        # DaemonService is only relevant on Linux
        self.daemon_service = container.get(DaemonService) if CURRENT_PLATFORM == "linux" else None
        self.registry = container.get(PluginRegistryFacade)
        
        self.loaded_tabs: Dict[str, Dict[str, Any]] = {}
        self.is_loading_tab = False
        self._previous_tab_index = -1
        
        # Connect tab widget signals
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
    
    def add_tab(self, tab_name: str, plugin_class: Any) -> None:
        """Add a new tab to the tab widget.
        
        Args:
            tab_name: Name of the tab
            plugin_class: Plugin class for the tab
        """
        placeholder = LoadingPlaceholder(tab_name)
        self.loaded_tabs[tab_name] = {
            "plugin_class": plugin_class,
            "instance": None,
            "placeholder": placeholder,
        }
        self.tab_widget.addTab(placeholder, tab_name)
        self.tab_added.emit(tab_name)
        self.title_update_requested.emit()
        logger.debug(f"Added tab: {tab_name}")
    
    def remove_tab(self, tab_name: str) -> None:
        """Remove a tab from the tab widget.
        
        Args:
            tab_name: Name of the tab to remove
        """
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == tab_name:
                self.tab_widget.removeTab(i)
                break
        
        if tab_name in self.loaded_tabs:
            # Call deactivation hook if instance exists
            tab_info = self.loaded_tabs[tab_name]
            if tab_info.get("instance"):
                # Call deactivation hook
                try:
                    plugin_instance = self.registry.get_plugin_instance(tab_name)
                    if hasattr(plugin_instance, 'on_tab_deactivated'):
                        plugin_instance.on_tab_deactivated()
                except Exception as e:
                    logger.debug(f"Error calling deactivation hook: {e}")
            
            del self.loaded_tabs[tab_name]
            self.tab_removed.emit(tab_name)
            self.title_update_requested.emit()
            logger.debug(f"Removed tab: {tab_name}")
    
    def remove_tab_by_index(self, index: int) -> None:
        """Remove a tab by index.
        
        Args:
            index: Index of the tab to remove
        """
        if 0 <= index < self.tab_widget.count():
            tab_name = self.tab_widget.tabText(index)
            self.remove_tab(tab_name)
    
    def on_tab_changed(self, index: int) -> None:
        """Handle tab change event.
        
        Args:
            index: Index of the newly selected tab
        """
        if self.is_loading_tab or index < 0:
            return
        
        # Call deactivation hook for previously active tab
        if self._previous_tab_index >= 0 and self._previous_tab_index != index:
            try:
                prev_tab_name = self.tab_widget.tabText(self._previous_tab_index)
                prev_instance_info = self.loaded_tabs.get(prev_tab_name)
                # Only call if we have a widget instance
                if prev_instance_info and prev_instance_info.get("instance"):
                    plugin_instance = self.registry.get_plugin_instance(prev_tab_name)
                    if hasattr(plugin_instance, 'on_tab_deactivated'):
                        plugin_instance.on_tab_deactivated()
                self.tab_deactivated.emit(prev_tab_name)
            except Exception as e:
                logger.debug(f"Error calling deactivation hook: {e}")
        
        try:
            self.is_loading_tab = True
            tab_name = self.tab_widget.tabText(index)
            tab_info = self.loaded_tabs.get(tab_name)
            
            if not tab_info:
                self.is_loading_tab = False
                self._previous_tab_index = index
                return
            
            # On Linux, check if tab is showing AdminRequiredPlaceholder and daemon is now available
            if CURRENT_PLATFORM == "linux" and tab_info.get("instance"):
                if isinstance(tab_info["instance"], AdminRequiredPlaceholder):
                    plugin_class = tab_info["plugin_class"]
                    requires_admin = getattr(plugin_class, 'requires_admin', False)
                    
                    # Check if daemon is now available
                    if self.daemon_service and self.daemon_service.is_available():
                        if not needs_admin_for_plugin(False, requires_admin, False):
                            # Daemon is available, reload the tab
                            logger.info(f"Daemon available, reloading tab '{tab_name}'")
                            self._reload_tab(tab_name)
                            self._previous_tab_index = index
                            self.is_loading_tab = False
                            self.title_update_requested.emit()
                            return
            
            # Lazy load tab content if not already loaded
            if not tab_info["instance"]:
                plugin_class = tab_info["plugin_class"]
                requires_admin = bool(getattr(plugin_class, "requires_admin", False))
                
                if needs_admin_for_plugin(
                    CURRENT_PLATFORM == "windows",
                    requires_admin,
                    self.admin_service.is_admin()
                ):
                    # Show admin required placeholder
                    admin_widget = self._create_admin_placeholder(tab_name)
                    tab_info["instance"] = admin_widget
                else:
                    # Create the actual plugin widget using instance
                    plugin_instance = self.registry.get_plugin_instance(tab_name)
                    tab_info["instance"] = plugin_instance.create_widget(self.tab_widget)
                
                # Replace placeholder with actual widget
                current_index = self.tab_widget.currentIndex()
                if current_index >= 0:
                    self.tab_widget.removeTab(current_index)
                    self.tab_widget.insertTab(current_index, tab_info["instance"], tab_name)
                    self.tab_widget.setCurrentIndex(current_index)
                
                logger.info(f"Lazy loaded plugin tab: {tab_name}")
            
            # Call activation hook for newly active tab
            if tab_info["instance"] and not isinstance(tab_info["instance"], (LoadingPlaceholder, ErrorPlaceholder, AdminRequiredPlaceholder)):
                try:
                    plugin_instance = self.registry.get_plugin_instance(tab_name)
                    if hasattr(plugin_instance, 'on_tab_activated'):
                        plugin_instance.on_tab_activated()
                except Exception as e:
                    logger.debug(f"Error calling activation hook for {tab_name}: {e}")
            self.tab_activated.emit(tab_name)
        
        except Exception as e:
            logger.error(f"Error loading tab {tab_name}: {e}")
            # Replace current tab content with an error placeholder
            try:
                error_widget = ErrorPlaceholder(tab_name, str(e))
                current_index = self.tab_widget.currentIndex()
                if current_index >= 0:
                    self.tab_widget.removeTab(current_index)
                    self.tab_widget.insertTab(current_index, error_widget, tab_name)
                    self.tab_widget.setCurrentIndex(current_index)
            except Exception:
                pass
        finally:
            self.is_loading_tab = False
            self._previous_tab_index = index
            self.title_update_requested.emit()
    
    def _reload_tab(self, tab_name: str) -> None:
        """Reload a specific tab by replacing its widget.
        
        Args:
            tab_name: Name of the tab to reload
        """
        tab_info = self.loaded_tabs.get(tab_name)
        if not tab_info:
            logger.warning(f"Tab info not found for '{tab_name}'")
            return
        
        plugin_class = tab_info["plugin_class"]
        requires_admin = getattr(plugin_class, 'requires_admin', False)
        
        # Find the tab index
        index = -1
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == tab_name:
                index = i
                break
        
        if index < 0:
            logger.warning(f"Tab '{tab_name}' not found in tab widget")
            return
        
        try:
            # Check if admin is still needed
            if needs_admin_for_plugin(
                CURRENT_PLATFORM == "windows",
                requires_admin,
                self.admin_service.is_admin()
            ):
                # Still needs admin, keep placeholder
                logger.debug(f"Tab '{tab_name}' still needs admin, keeping placeholder")
                return
            
            logger.info(f"Creating widget for tab '{tab_name}' (daemon available)")
            # Create the actual widget using instance
            plugin_instance = self.registry.get_plugin_instance(tab_name)
            widget = plugin_instance.create_widget(self.tab_widget)
            tab_info["instance"] = widget
            
            # Replace the tab widget
            self.tab_widget.removeTab(index)
            self.tab_widget.insertTab(index, widget, tab_name)
            
            # If this was the current tab, make sure it's still selected
            current_index = self.tab_widget.currentIndex()
            if current_index != index:
                self.tab_widget.setCurrentIndex(index)
            
            logger.info(f"Successfully reloaded tab '{tab_name}'")
        except Exception as e:
            logger.error(f"Error reloading tab '{tab_name}': {e}", exc_info=True)
            # Keep the placeholder on error
    
    def get_current_tab_name(self) -> Optional[str]:
        """Get the name of the currently active tab.
        
        Returns:
            Tab name or None if no tab is selected
        """
        current_index = self.tab_widget.currentIndex()
        if current_index >= 0:
            return self.tab_widget.tabText(current_index)
        return None
    
    def get_tab_info(self, tab_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a tab.
        
        Args:
            tab_name: Name of the tab
            
        Returns:
            Tab info dictionary or None if tab not found
        """
        return self.loaded_tabs.get(tab_name)
    
    def get_tab_count(self) -> int:
        """Get the number of tabs.
        
        Returns:
            Number of tabs
        """
        return self.tab_widget.count()
    
    def get_tab_order(self) -> List[str]:
        """Get the current order of tabs.
        
        Returns:
            List of tab names in their current visual order
        """
        order = []
        for i in range(self.tab_widget.count()):
            order.append(self.tab_widget.tabText(i))
        return order

    def clear_loaded_tabs(self) -> None:
        """Clear all loaded tab state.
        
        This is used when reloading all plugins. It clears the internal
        tracking of loaded tabs without removing the actual tab widgets
        (which should be removed separately).
        """
        # Call deactivation hooks for all tabs with instances
        for tab_name, tab_info in self.loaded_tabs.items():
            if tab_info.get("instance"):
                try:
                    plugin_instance = self.registry.get_plugin_instance(tab_name)
                    if hasattr(plugin_instance, 'on_tab_deactivated'):
                        plugin_instance.on_tab_deactivated()
                except Exception as e:
                    logger.debug(f"Error calling deactivation hook for {tab_name}: {e}")
        
        self.loaded_tabs.clear()
        self._previous_tab_index = -1
        logger.info("Cleared all loaded tab state")
    
    def set_restart_admin_callback(self, callback: Callable[[], None]) -> None:
        """Set callback for restart as admin action.
        
        Args:
            callback: Callback function to call when restart is requested
        """
        # Store callback for future use
        self._restart_admin_callback = callback
        
        # Update all existing AdminRequiredPlaceholder widgets to use this callback
        for tab_info in self.loaded_tabs.values():
            if tab_info.get("instance") and isinstance(tab_info["instance"], AdminRequiredPlaceholder):
                # Disconnect existing connections (if any)
                try:
                    tab_info["instance"].restartRequested.disconnect()
                except Exception:
                    pass
                # Connect new callback
                tab_info["instance"].restartRequested.connect(callback)
    
    def _create_admin_placeholder(self, tab_name: str) -> AdminRequiredPlaceholder:
        """Create an admin required placeholder widget.
        
        Args:
            tab_name: Name of the tab
            
        Returns:
            AdminRequiredPlaceholder widget
        """
        admin_widget = AdminRequiredPlaceholder(tab_name)
        if hasattr(self, '_restart_admin_callback') and self._restart_admin_callback:
            admin_widget.restartRequested.connect(self._restart_admin_callback)
        return admin_widget


__all__ = ['TabController']

