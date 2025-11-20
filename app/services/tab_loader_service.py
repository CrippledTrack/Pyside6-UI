"""
Tab loader service for asynchronous plugin loading.

This module provides the TabLoaderThread class that handles plugin discovery
and loading in a separate thread to avoid blocking the main UI.
"""

from __future__ import annotations

import logging
from typing import List, Optional, TYPE_CHECKING, Any

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QTabWidget, QWidget

if TYPE_CHECKING:
    from .settings_service import SettingsService

from ...plugin_system import plugin_registry
from .plugin_service import discover_and_register_all_plugins

logger = logging.getLogger(__name__)


class TabLoaderThread(QThread):
    """Thread for loading plugins asynchronously.
    
    This class handles plugin discovery, registration, and state management
    in a separate thread to keep the UI responsive during initialization.
    """
    
    finished = Signal()
    error = Signal(str)
    add_tab = Signal(str, object)

    def __init__(self, parent: Optional[QWidget] = None, settings_service: Optional["SettingsService"] = None) -> None:
        """Initialize the tab loader thread.
        
        Args:
            parent: Optional parent widget
            settings_service: Optional settings service for loading plugin states
        """
        super().__init__(parent)
        self.setObjectName("TabLoaderThread")
        self.tab_widget: Optional[QTabWidget] = None
        self.settings_service = settings_service

    def set_tab_widget(self, tab_widget: QTabWidget) -> None:
        """Set the tab widget (currently unused but kept for potential future use)."""
        self.tab_widget = tab_widget

    def run(self) -> None:
        """Execute the plugin loading process."""
        try:
            self.discover_and_register_plugins()
            self._load_plugin_states()
            self._emit_enabled_plugins()
            self.finished.emit()
        except Exception as e:  # pragma: no cover - runtime error path
            logger.error(f"Error in TabLoaderThread: {e}")
            self.error.emit(str(e))

    def _load_plugin_states(self) -> None:
        """Load and apply saved plugin states from settings."""
        if not self.settings_service:
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
        """Apply user-disabled plugins from settings."""
        logger.info(f"Loading saved user-disabled plugins: {disabled_plugins}")
        for plugin_name in disabled_plugins:
            if plugin_registry.get_plugin(plugin_name):
                plugin_registry.disable_plugin(plugin_name)
                logger.debug(f"Applied user preference: {plugin_name} disabled")

    def _handle_first_run(self) -> None:
        """Handle first run scenario - log defaults and initialize empty disabled list."""
        logger.info("First run detected, applying default plugin states (disabled_by_default flags)")
        # Log default states for information
        enabled_by_default = [name for name in plugin_registry.list_plugin_names() 
                            if plugin_registry.is_enabled(name)]
        disabled_by_default = [name for name in plugin_registry.list_plugin_names() 
                              if not plugin_registry.is_enabled(name)]
        logger.info(f"Default plugin states: {len(enabled_by_default)} enabled, "
                   f"{len(disabled_by_default)} disabled by default")
        if disabled_by_default:
            logger.info(f"Disabled by default: {', '.join(disabled_by_default)}")
        
        # Initialize empty disabled list (user hasn't disabled anything yet)
        if self.settings_service:
            self.settings_service.save_disabled_plugins([])

    def _emit_enabled_plugins(self) -> None:
        """Emit signals for all enabled plugins."""
        enabled_plugins = plugin_registry.get_enabled_plugins()
        for tab_name, plugin_class in enabled_plugins.items():
            self.add_tab.emit(tab_name, plugin_class)

    def discover_and_register_plugins(self) -> None:
        """Discover and register all available plugins."""
        discover_and_register_all_plugins()


__all__ = ['TabLoaderThread']

