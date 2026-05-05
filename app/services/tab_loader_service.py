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

from ..qt_bindings import QThread, Signal, QWidget

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
        self._cancelled = False

    def cancel(self) -> None:
        """Request cooperative cancellation of the loader."""
        self._cancelled = True
        self.requestInterruption()

    def run(self) -> None:
        """Execute the plugin loading process.
        
        This method:
        1. Discovers and registers all plugins (via PluginService)
        2. Loads saved plugin states (via PluginService)
        3. Emits add_tab signals for enabled plugins
        """
        try:
            if self._should_cancel():
                return
            # Step 1: Discover and register all plugins
            self._plugin_service.discover_and_register_all_plugins()
            
            if self._should_cancel():
                return
            # Step 2: Load saved plugin states (user preferences)
            self._plugin_service.load_saved_plugin_states()
            
            if self._should_cancel():
                return
            # Step 3: Emit signals for all enabled plugins
            self._emit_enabled_plugins()
            
            if self._should_cancel():
                return
            self.finished.emit()
        except Exception as e:  # pragma: no cover - runtime error path
            logger.error(f"Error in TabLoaderThread: {e}")
            self.error.emit(str(e))

    def _emit_enabled_plugins(self) -> None:
        """Emit add_tab signals for all enabled plugins, respecting saved order."""
        enabled_plugins = dict(self._plugin_service.get_enabled_plugins())
        has_settings = self._settings_service is not None

        # Get saved tab order if available
        saved_order = self._settings_service.get_tab_order() if has_settings else []
        
        # 1. Add tabs in saved order
        for tab_name in saved_order:
            if self._should_cancel():
                return
            
            # PERF: Use pop() to get and remove in one atomic operation (1 hash lookup vs 3)
            plugin_class = enabled_plugins.pop(tab_name, None)
            if plugin_class is not None:
                # PERF: Inline the extension enabled check to avoid function call overhead in loop
                if has_settings and not self._settings_service.is_extension_enabled(tab_name, "Tab"):
                    continue
                self.add_tab.emit(tab_name, plugin_class)
        
        # 2. Add remaining (new/unsaved) tabs alphabetically
        for tab_name in sorted(enabled_plugins.keys()):
            if self._should_cancel():
                return
            if has_settings and not self._settings_service.is_extension_enabled(tab_name, "Tab"):
                continue
            self.add_tab.emit(tab_name, enabled_plugins[tab_name])

    def _should_cancel(self) -> bool:
        """Check if cancellation has been requested."""
        return self._cancelled or self.isInterruptionRequested()


__all__ = ['TabLoaderThread']
