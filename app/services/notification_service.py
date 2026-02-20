"""
Notification service for managing application notifications.

This module provides a centralized service for handling, storing, and retrieving
notification history, and notifying the UI of new alerts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional

from ..qt_bindings import QObject, Signal

logger = logging.getLogger(__name__)


class NotificationType(Enum):
    """Types of notifications."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class Notification:
    """A single notification entry."""
    message: str
    type: NotificationType
    timestamp: datetime = field(default_factory=datetime.now)
    read: bool = False
    details: Optional[str] = None


class NotificationService(QObject):
    """Service for managing notifications."""
    
    # Constants
    MAX_HISTORY_SIZE = 50
    
    # Signals
    notification_added = Signal(Notification)
    unread_count_changed = Signal(int)
    
    def __init__(self) -> None:
        """Initialize the notification service."""
        super().__init__()
        self._notifications: List[Notification] = []
    
    def add_notification(self, message: str, type: NotificationType, details: Optional[str] = None) -> None:
        """Add a new notification.
        
        Args:
            message: The main message text
            type: The type of notification (info, success, warning, error)
            details: Optional detailed description
        """
        notification = Notification(message=message, type=type, details=details)
        self._notifications.insert(0, notification)  # Newest first
        
        # Enforce history limit
        while len(self._notifications) > self.MAX_HISTORY_SIZE:
            self._notifications.pop()  # Remove oldest
        
        logger.debug(f"Notification added: [{type.value}] {message}")
        
        self.notification_added.emit(notification)
        self._emit_unread_count()
    
    def get_notifications(self) -> List[Notification]:
        """Get all notifications.
        
        Returns:
            List of notifications (newest first)
        """
        return self._notifications
    
    def get_unread_count(self) -> int:
        """Get the number of unread notifications.
        
        Returns:
            Count of unread notifications
        """
        return sum(1 for n in self._notifications if not n.read)
    
    def mark_all_as_read(self) -> None:
        """Mark all notifications as read."""
        changed = False
        for n in self._notifications:
            if not n.read:
                n.read = True
                changed = True
        
        if changed:
            self._emit_unread_count()
    
    def clear_all(self) -> None:
        """Clear all notifications."""
        self._notifications.clear()
        self._emit_unread_count()
    
    def _emit_unread_count(self) -> None:
        """Emit the unread count signal."""
        self.unread_count_changed.emit(self.get_unread_count())


__all__ = ['NotificationService', 'Notification', 'NotificationType']
