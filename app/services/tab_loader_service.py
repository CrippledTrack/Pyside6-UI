"""
Tab loader thread for asynchronous plugin loading.

This module provides the TabLoaderThread class that orchestrates plugin discovery
and loading in a separate thread to avoid blocking the main UI.

Note: All business logic has been moved to PluginService per separation of concerns.
TabLoaderThread now only handles async execution and emitting signals to the UI.
"""

from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QWidget

if TYPE_CHECKING:
    from .plugin_service import PluginService
    from .settings_service import SettingsService

logger = logging.getLogger(__name__)


class TabLoaderThread(QThread):
    """Thread for loading plugins asynchronously.
    
    This class orchestrates plugin discovery and loading in a separate thread
    to keep the UI responsive during initialization.
    
    Business logic is delegated to PluginService - this class only handles:
    - Running discovery asynchronously
    - Emitting signals to update the UI
    """
    
    finished = Signal()
    error = Signal(str)
    add_tab = Signal(str, object)  # (tab_name, plugin_class)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        plugin_service: Optional["PluginService"] = None,
        settings_service: Optional["SettingsService"] = None
    ) -> None:
        """Initialize the tab loader thread.
        
        Args:
            parent: Optional parent widget
            plugin_service: Plugin service for discovery and registry access (required)
            settings_service: Settings service for session restoration (optional)
        """
        super().__init__(parent)
        self.setObjectName("TabLoaderThread")
        
        if plugin_service is None:
            raise ValueError("PluginService is required for TabLoaderThread")
        
        self._plugin_service = plugin_service
        self._settings_service = settings_service

    def run(self) -> None:
        """Execute the plugin loading process.
        
        This method:
        1. Discovers and registers all plugins (via PluginService)
        2. Loads saved plugin states (via PluginService)
        3. Emits add_tab signals for enabled plugins
        """
        try:
            # Step 1: Discover and register all plugins
            self._plugin_service.discover_and_register_all_plugins()
            
            # Step 2: Load saved plugin states (user preferences)
            self._plugin_service.load_saved_plugin_states()
            
            # Step 3: Emit signals for all enabled plugins
            self._emit_enabled_plugins()
            
            self.finished.emit()
        except Exception as e:  # pragma: no cover - runtime error path
            logger.error(f"Error in TabLoaderThread: {e}")
            self.error.emit(str(e))

    def _emit_enabled_plugins(self) -> None:
        """Emit add_tab signals for all enabled plugins, respecting saved order."""
        enabled_plugins = self._plugin_service.get_enabled_plugins()
        
        # Get saved tab order if available
        saved_order = []
        if self._settings_service:
            saved_order = self._settings_service.get_tab_order()
        
        # 1. Add tabs in saved order
        for tab_name in saved_order:
            if tab_name in enabled_plugins:
                plugin_class = enabled_plugins[tab_name]
                self.add_tab.emit(tab_name, plugin_class)
                # Remove from dict to track what's left
                del enabled_plugins[tab_name]
        
        # 2. Add remaining (new/unsaved) tabs alphabetically
        for tab_name in sorted(enabled_plugins.keys()):
            plugin_class = enabled_plugins[tab_name]
            self.add_tab.emit(tab_name, plugin_class)


__all__ = ['TabLoaderThread']
