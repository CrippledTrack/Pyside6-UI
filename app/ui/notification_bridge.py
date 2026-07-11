"""Bridge NotificationService callbacks to IMainWindowShell."""

from __future__ import annotations

import logging

from ..services.notification_service import Notification, NotificationService
from .abstractions.shell import IMainWindowShell

logger = logging.getLogger(__name__)


class NotificationShellBridge:
    """Subscribes to NotificationService and forwards to the main window shell."""

    def __init__(
        self,
        notification_service: NotificationService,
        shell: IMainWindowShell,
    ) -> None:
        self._service = notification_service
        self._shell = shell
        self._unsub_added = notification_service.subscribe_added(self._on_added)
        self._unsub_unread = notification_service.subscribe_unread_changed(
            self._shell.on_unread_count_changed
        )

    def _on_added(self, notification: Notification) -> None:
        try:
            self._shell.on_notification_added(notification)
        except Exception as e:
            logger.error(f"Shell notification handler error: {e}", exc_info=True)

    def disconnect(self) -> None:
        """Unsubscribe from notification service."""
        self._unsub_added()
        self._unsub_unread()


__all__ = ['NotificationShellBridge']
