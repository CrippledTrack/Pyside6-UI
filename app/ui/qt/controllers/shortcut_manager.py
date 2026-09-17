"""
Keyboard shortcuts manager for the main window.

Provides global keyboard shortcuts for common actions.
"""
from __future__ import annotations

import logging
from typing import Dict, Callable, Optional
from ....constants import CURRENT_PLATFORM
from ..bindings import QObject, Signal, QShortcut, QKeySequence, QWidget

logger = logging.getLogger(__name__)


def default_shortcut_sequences(platform_name: Optional[str] = None) -> Dict[str, str]:
    """Return the shell shortcut key sequences for *platform_name*.

    In Qt's portable notation ``Ctrl`` means Command on macOS and ``Meta``
    means Control. macOS therefore needs different literals: ``Ctrl+Tab``
    would be Cmd+Tab (the system application switcher) and ``F11`` is taken
    by Mission Control, so tab cycling uses Control+Tab and fullscreen uses
    Control+Cmd+F. ``QKeySequence.StandardKey.NextChild`` is not a fix here:
    it also resolves to Cmd+Tab on macOS.
    """
    name = (platform_name or CURRENT_PLATFORM).lower()
    if name == "darwin":
        return {
            "next_tab": "Meta+Tab",
            "prev_tab": "Meta+Shift+Tab",
            "fullscreen": "Ctrl+Meta+F",
        }
    return {
        "next_tab": "Ctrl+Tab",
        "prev_tab": "Ctrl+Shift+Tab",
        "fullscreen": "F11",
    }


class ShortcutManager(QObject):
    """Manages keyboard shortcuts for the application."""
    
    # Signals for shortcut actions (see default_shortcut_sequences for keys)
    nextTab = Signal()
    prevTab = Signal()
    toggleFullscreen = Signal()
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.shortcuts: Dict[str, QShortcut] = {}
        self.setup_shortcuts()
    
    def setup_shortcuts(self) -> None:
        """Setup all keyboard shortcuts."""
        callbacks = {
            "next_tab": self.nextTab.emit,
            "prev_tab": self.prevTab.emit,
            "fullscreen": self.toggleFullscreen.emit,
        }
        shortcuts_config = {
            name: (sequence, callbacks[name])
            for name, sequence in default_shortcut_sequences().items()
        }
        
        for name, (key_sequence, callback) in shortcuts_config.items():
            try:
                shortcut = QShortcut(QKeySequence(key_sequence), self.parent())
                shortcut.activated.connect(callback)
                self.shortcuts[name] = shortcut
                logger.debug(f"Registered shortcut: {name} -> {key_sequence}")
            except Exception as e:
                logger.error(f"Failed to register shortcut {name}: {e}")
    
    def enable_shortcut(self, name: str, enabled: bool = True) -> None:
        """Enable or disable a specific shortcut."""
        if name in self.shortcuts:
            self.shortcuts[name].setEnabled(enabled)
            logger.debug(f"Shortcut {name} {'enabled' if enabled else 'disabled'}")
    
    def disable_shortcut(self, name: str) -> None:
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
    
    def add_custom_shortcut(self, name: str, key_sequence: str, callback: Callable) -> bool:
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
    
    def remove_shortcut(self, name: str) -> None:
        """Remove a shortcut."""
        if name in self.shortcuts:
            self.shortcuts[name].setParent(None)
            del self.shortcuts[name]
            logger.debug(f"Removed shortcut: {name}")
    
    def clear_all_shortcuts(self) -> None:
        """Remove all shortcuts."""
        for shortcut in self.shortcuts.values():
            shortcut.setParent(None)
        self.shortcuts.clear()
        logger.debug("Cleared all shortcuts")


__all__ = ['ShortcutManager', 'default_shortcut_sequences']

