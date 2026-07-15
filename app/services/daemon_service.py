"""Daemon management service for Linux privileged operations.

This module provides a centralized service for managing the privileged pipe
daemon on Linux systems, including starting, checking status, and refreshing
admin-required UI components when the daemon becomes available.
"""

from __future__ import annotations

import logging
import platform
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Only import Linux-specific modules on Linux
if platform.system().lower() == "linux":
    from ..daemon import is_daemon_available, set_daemon_client
    from ..utils.elevation_linux import start_daemon
else:
    def start_daemon(*args, **kwargs) -> Optional[object]:
        return None


class DaemonService:
    """Service for managing the privileged pipe daemon on Linux systems."""

    def __init__(self) -> None:
        self._refresh_callbacks: list[Callable[[], None]] = []
        self._is_linux = platform.system().lower() == "linux"

    def is_available(self) -> bool:
        """Check if the daemon is available and connected."""
        if not self._is_linux:
            return False
        try:
            return is_daemon_available()
        except Exception as e:
            logger.debug(f"Error checking daemon availability: {e}")
            return False

    def is_running(self) -> bool:
        """Check if the daemon process is running and connected."""
        return self.is_available()

    def start(self) -> tuple[bool, Optional[str]]:
        """Start the privileged pipe daemon.

        Returns:
            Tuple of (success, error_message)
        """
        if not self._is_linux:
            return False, "Daemon is only available on Linux"

        if self.is_available():
            return True, None

        logger.info("Starting privileged daemon...")
        try:
            client = start_daemon()
            if client:
                set_daemon_client(client)
                logger.info("Daemon client set globally")
                self._notify_refresh_callbacks()
                return True, None
            return False, (
                "Failed to start the privileged daemon. "
                "Ensure pkexec or sudo is installed, approve the elevation prompt, "
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

    def unregister_refresh_callback(self, callback: Callable[[], None]) -> None:
        """Unregister a refresh callback."""
        if callback in self._refresh_callbacks:
            self._refresh_callbacks.remove(callback)
            logger.debug(
                f"Unregistered refresh callback: "
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

    def get_status_message(self) -> str:
        """Get a human-readable status message about the daemon."""
        if not self._is_linux:
            return "Daemon is only available on Linux"
        if self.is_available():
            return "The privileged daemon is currently running"
        return "The privileged daemon is not running"


__all__ = ['DaemonService']
