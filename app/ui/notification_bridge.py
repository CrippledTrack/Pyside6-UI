"""Bridge NotificationService callbacks to IMainWindowShell."""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable, Callable, TYPE_CHECKING

from .abstractions.shell import IMainWindowShell

if TYPE_CHECKING:
    from ..services.notification_service import Notification

logger = logging.getLogger(__name__)

Unsubscribe = Callable[[], None]


@runtime_checkable
class _NotificationSubscriber(Protocol):
    """Minimal notification API needed by the shell bridge."""

    def subscribe_added(self, callback: Callable[["Notification"], None]) -> Unsubscribe:
        ...

    def subscribe_unread_changed(self, callback: Callable[[int], None]) -> Unsubscribe:
        ...


class NotificationShellBridge:
    """Subscribes to NotificationService and forwards to the main window shell."""

    def __init__(
        self,
        notification_service: _NotificationSubscriber,
        shell: IMainWindowShell,
    ) -> None:
        self._service = notification_service
        self._shell = shell
        self._unsub_added = notification_service.subscribe_added(self._on_added)
        self._unsub_unread = notification_service.subscribe_unread_changed(
            self._shell.on_unread_count_changed
        )

    def _on_added(self, notification: "Notification") -> None:
        try:
            self._shell.on_notification_added(notification)
        except Exception as e:
            logger.error(f"Shell notification handler error: {e}", exc_info=True)

    def disconnect(self) -> None:
        """Unsubscribe from notification service."""
        self._unsub_added()
        self._unsub_unread()


__all__ = ['NotificationShellBridge']
