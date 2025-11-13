"""
Status bar manager.

This module provides StatusBarManager to handle status bar messages
and timers.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QTimer, QObject
from PySide6.QtWidgets import QStatusBar

logger = logging.getLogger(__name__)


class StatusBarManager(QObject):
    """Manager for status bar messages."""
    
    def __init__(
        self,
        status_bar: QStatusBar,
        parent: Optional[QObject] = None
    ) -> None:
        """Initialize the status bar manager.
        
        Args:
            status_bar: The status bar widget to manage
            parent: Optional parent object
        """
        super().__init__(parent)
        self.status_bar = status_bar
        self._status_timer: Optional[QTimer] = None
    
    def show_status(self, message: str, timeout: int = 0) -> None:
        """Show a status message in the status bar.
        
        Args:
            message: Status message to display
            timeout: Timeout in milliseconds (0 = permanent, clears on next show_status call)
        """
        # Clear any existing timer
        if self._status_timer:
            self._status_timer.stop()
            self._status_timer.deleteLater()
            self._status_timer = None
        
        # Show the message
        if timeout > 0:
            self.status_bar.showMessage(message, timeout)
            # Set up timer to clear after timeout
            self._status_timer = QTimer(self)
            self._status_timer.setSingleShot(True)
            self._status_timer.timeout.connect(self.clear_status)
            self._status_timer.start(timeout)
        else:
            self.status_bar.showMessage(message)
    
    def clear_status(self) -> None:
        """Clear the status bar message."""
        # Clear any existing timer
        if self._status_timer:
            self._status_timer.stop()
            self._status_timer.deleteLater()
            self._status_timer = None
        self.status_bar.clearMessage()
    
    def get_current_message(self) -> str:
        """Get the current status bar message.
        
        Returns:
            Current message or empty string if no message
        """
        return self.status_bar.currentMessage()


__all__ = ['StatusBarManager']

