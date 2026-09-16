"""Daemon management service for privileged pipe operations.

Starts, checks, and refreshes UI when the Unix privileged daemon (Linux or
macOS) becomes available.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

from ..utils.elevation import start_daemon, supports_privileged_daemon

logger = logging.getLogger(__name__)


class DaemonService:
    """Service for managing the privileged pipe daemon on Linux and macOS."""

    def __init__(self) -> None:
        self._refresh_callbacks: list[Callable[[], None]] = []
        self._supports_daemon = supports_privileged_daemon()

    def is_available(self) -> bool:
        """Check if the daemon is available and connected."""
        if not self._supports_daemon:
            return False
        try:
            from ..daemon import is_daemon_available

            return is_daemon_available()
        except Exception as e:
            logger.debug(f"Error checking daemon availability: {e}")
            return False

    def start(self) -> tuple[bool, Optional[str]]:
        """Start the privileged pipe daemon.

        Returns:
            Tuple of (success, error_message)
        """
        if not self._supports_daemon:
            return False, "Daemon is only available on Linux and macOS"

        if self.is_available():
            return True, None

        logger.info("Starting privileged daemon...")
        try:
            from ..daemon import set_daemon_client

            client = start_daemon()
            if client:
                set_daemon_client(client)
                logger.info("Daemon client set globally")
                self._notify_refresh_callbacks()
                return True, None
            return False, (
                "Failed to start the privileged daemon. "
                "Approve the pkexec, sudo, or macOS password prompt, "
                "and check the application log for details."
            )
        except Exception as e:
            logger.error(f"Error starting daemon: {e}", exc_info=True)
            return False, (
                f"Error starting privileged daemon: {e}. "
                "Ensure pkexec or sudo is available and try again."
            )

    def register_refresh_callback(self, callback: Callable[[], None]) -> None:
        """Register a callback to be called when daemon becomes available."""
        if callback not in self._refresh_callbacks:
            self._refresh_callbacks.append(callback)
            logger.debug(
                f"Registered refresh callback: "
                f"{callback.__name__ if hasattr(callback, '__name__') else 'anonymous'}"
            )

    def _notify_refresh_callbacks(self) -> None:
        """Notify all registered refresh callbacks."""
        logger.info(f"Notifying {len(self._refresh_callbacks)} refresh callbacks")
        for callback in self._refresh_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in refresh callback: {e}", exc_info=True)


__all__ = ["DaemonService"]
