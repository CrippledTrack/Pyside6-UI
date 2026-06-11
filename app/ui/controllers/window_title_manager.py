"""
Window title manager.

This module provides WindowTitleManager to handle window title updates
based on the current tab and version information.
"""

from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ...qt_bindings import QMainWindow
    from .tab_controller import TabController

from ...constants import CURRENT_PLATFORM
from ...utils.display_utils import build_title
from ...utils.imports import get_platforms_constants

logger = logging.getLogger(__name__)

# Import platform constants
constants = get_platforms_constants()
VERSION = constants.VERSION
VERSION_NAME = constants.VERSION_NAME


class WindowTitleManager:
    """Manager for window title updates."""
    
    def __init__(
        self,
        main_window: "QMainWindow",
        tab_controller: Optional["TabController"] = None
    ) -> None:
        """Initialize the window title manager.
        
        Args:
            main_window: The main window to update
            tab_controller: Optional tab controller for getting current tab info
        """
        self.main_window = main_window
        self.tab_controller = tab_controller
    
    def set_tab_controller(self, tab_controller: "TabController") -> None:
        """Set the tab controller.
        
        Args:
            tab_controller: Tab controller instance
        """
        self.tab_controller = tab_controller
    
    def update_title(self) -> None:
        """Update the window title based on current state."""
        try:
            tab_name = None
            plugin_version = None
            
            if not getattr(constants, "SINGLE_PLUGIN_MODE", False) and self.tab_controller:
                tab_name = self.tab_controller.get_current_tab_name()
                if tab_name:
                    tab_info = self.tab_controller.get_tab_info(tab_name)
                    if tab_info:
                        plugin_class = tab_info.get("plugin_class")
                        if plugin_class:
                            plugin_version = getattr(plugin_class, "plugin_version", None)
            
            title = build_title(VERSION_NAME, VERSION, CURRENT_PLATFORM, tab_name, plugin_version)
            self.main_window.setWindowTitle(title)
        except Exception as e:
            logger.error(f"Error updating window title: {e}")
            # Fallback to basic title
            self.main_window.setWindowTitle(
                build_title(VERSION_NAME, VERSION, CURRENT_PLATFORM)
            )
    
    def get_base_title(self) -> str:
        """Get the base window title without tab information.
        
        Returns:
            Base window title
        """
        return build_title(VERSION_NAME, VERSION, CURRENT_PLATFORM)


__all__ = ['WindowTitleManager']

