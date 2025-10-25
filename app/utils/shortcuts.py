"""
Keyboard shortcuts manager for the main window.

Provides global keyboard shortcuts for common actions.
"""
from __future__ import annotations

import logging
from typing import Dict, Callable, Optional
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)


class ShortcutManager(QObject):
    """Manages keyboard shortcuts for the application."""
    
    # Signals for shortcut actions
    tabSearch = Signal()  # Ctrl+T
    nextTab = Signal()    # Ctrl+Tab
    prevTab = Signal()    # Ctrl+Shift+Tab
    closeTab = Signal()   # Ctrl+W
    reopenTab = Signal()  # Ctrl+Shift+T
  # Ctrl+,
    toggleFullscreen = Signal()  # F11
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.shortcuts: Dict[str, QShortcut] = {}
        self.setup_shortcuts()
    
    def setup_shortcuts(self):
        """Setup all keyboard shortcuts."""
        shortcuts_config = {
            "tab_search": ("Ctrl+T", self.tabSearch.emit),
            "next_tab": ("Ctrl+Tab", self.nextTab.emit),
            "prev_tab": ("Ctrl+Shift+Tab", self.prevTab.emit),
            "close_tab": ("Ctrl+W", self.closeTab.emit),
            "reopen_tab": ("Ctrl+Shift+T", self.reopenTab.emit),
            "fullscreen": ("F11", self.toggleFullscreen.emit),
        }
        
        for name, (key_sequence, callback) in shortcuts_config.items():
            try:
                shortcut = QShortcut(QKeySequence(key_sequence), self.parent())
                shortcut.activated.connect(callback)
                self.shortcuts[name] = shortcut
                logger.debug(f"Registered shortcut: {name} -> {key_sequence}")
            except Exception as e:
                logger.error(f"Failed to register shortcut {name}: {e}")
    
    def enable_shortcut(self, name: str, enabled: bool = True):
        """Enable or disable a specific shortcut."""
        if name in self.shortcuts:
            self.shortcuts[name].setEnabled(enabled)
            logger.debug(f"Shortcut {name} {'enabled' if enabled else 'disabled'}")
    
    def disable_shortcut(self, name: str):
        """Disable a specific shortcut."""
        self.enable_shortcut(name, False)
    
    def is_shortcut_enabled(self, name: str) -> bool:
        """Check if a shortcut is enabled."""
        if name in self.shortcuts:
            return self.shortcuts[name].isEnabled()
        return False
    
    def get_shortcut_sequence(self, name: str) -> str:
        """Get the key sequence for a shortcut."""
        if name in self.shortcuts:
            return self.shortcuts[name].key().toString()
        return ""
    
    def get_all_shortcuts(self) -> Dict[str, str]:
        """Get all registered shortcuts as name -> key sequence mapping."""
        return {name: shortcut.key().toString() 
                for name, shortcut in self.shortcuts.items()}
    
    def add_custom_shortcut(self, name: str, key_sequence: str, callback: Callable):
        """Add a custom shortcut."""
        try:
            shortcut = QShortcut(QKeySequence(key_sequence), self.parent())
            shortcut.activated.connect(callback)
            self.shortcuts[name] = shortcut
            logger.debug(f"Added custom shortcut: {name} -> {key_sequence}")
            return True
        except Exception as e:
            logger.error(f"Failed to add custom shortcut {name}: {e}")
            return False
    
    def remove_shortcut(self, name: str):
        """Remove a shortcut."""
        if name in self.shortcuts:
            self.shortcuts[name].setParent(None)
            del self.shortcuts[name]
            logger.debug(f"Removed shortcut: {name}")
    
    def clear_all_shortcuts(self):
        """Remove all shortcuts."""
        for shortcut in self.shortcuts.values():
            shortcut.setParent(None)
        self.shortcuts.clear()
        logger.debug("Cleared all shortcuts")
