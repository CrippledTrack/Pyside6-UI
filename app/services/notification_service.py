"""
Notification service for managing application notifications.

This module provides a centralized service for handling, storing, and retrieving
notification history, and notifying observers of new alerts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

Unsubscribe = Callable[[], None]


def format_notification_age(
    timestamp: datetime,
    now: Optional[datetime] = None,
) -> str:
    """Return a short relative label for *timestamp*.

    Under a minute: ``just now``. Under an hour: ``Nm ago``.
    Under a day: ``Nh ago``. Older: a calendar date (``Sep 19``, or
    ``Sep 19, 2025`` when the year differs from *now*).
    """
    current = now or datetime.now()
    if timestamp.tzinfo is not None and current.tzinfo is None:
        current = current.replace(tzinfo=timestamp.tzinfo)
    elif timestamp.tzinfo is None and current.tzinfo is not None:
        timestamp = timestamp.replace(tzinfo=current.tzinfo)

    delta = current - timestamp
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    month_day = timestamp.strftime("%b %d").replace("  ", " ")
    if timestamp.year != current.year:
        return f"{month_day}, {timestamp.year}"
    return month_day


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


class NotificationService:
    """Service for managing notifications (toolkit-free)."""

    MAX_HISTORY_SIZE = 50

    def __init__(self) -> None:
        self._notifications: List[Notification] = []
        self._added_subscribers: List[Callable[[Notification], None]] = []
        self._unread_subscribers: List[Callable[[int], None]] = []

    def subscribe_added(self, callback: Callable[[Notification], None]) -> Unsubscribe:
        """Subscribe to new notification events."""
        self._added_subscribers.append(callback)

        def unsubscribe() -> None:
            if callback in self._added_subscribers:
                self._added_subscribers.remove(callback)

        return unsubscribe

    def subscribe_unread_changed(self, callback: Callable[[int], None]) -> Unsubscribe:
        """Subscribe to unread count changes."""
        self._unread_subscribers.append(callback)

        def unsubscribe() -> None:
            if callback in self._unread_subscribers:
                self._unread_subscribers.remove(callback)

        return unsubscribe

    def add_notification(
        self,
        message: str,
        type: NotificationType,
        details: Optional[str] = None,
    ) -> None:
        """Add a new notification."""
        notification = Notification(message=message, type=type, details=details)
        self._notifications.insert(0, notification)

        while len(self._notifications) > self.MAX_HISTORY_SIZE:
            self._notifications.pop()

        logger.debug(f"Notification added: [{type.value}] {message}")

        for cb in list(self._added_subscribers):
            try:
                cb(notification)
            except Exception as e:
                logger.error(f"Notification subscriber error: {e}", exc_info=True)
        self._notify_unread_count()

    def get_notifications(self) -> List[Notification]:
        """Get all notifications (newest first)."""
        return list(self._notifications)

    def get_unread_count(self) -> int:
        """Get count of unread notifications."""
        return sum(1 for n in self._notifications if not n.read)

    def mark_all_as_read(self) -> None:
        """Mark all notifications as read."""
        changed = False
        for n in self._notifications:
            if not n.read:
                n.read = True
                changed = True
        if changed:
            self._notify_unread_count()

    def remove_notification(self, notification: Notification) -> None:
        """Remove a single notification from history.

        Unknown objects are ignored so a stale UI row cannot raise.
        """
        try:
            self._notifications.remove(notification)
        except ValueError:
            return
        self._notify_unread_count()

    def clear_all(self) -> None:
        """Clear all notifications."""
        self._notifications.clear()
        self._notify_unread_count()

    def _notify_unread_count(self) -> None:
        count = self.get_unread_count()
        for cb in list(self._unread_subscribers):
            try:
                cb(count)
            except Exception as e:
                logger.error(f"Unread subscriber error: {e}", exc_info=True)


__all__ = [
    'NotificationService',
    'Notification',
    'NotificationType',
    'Unsubscribe',
    'format_notification_age',
]
