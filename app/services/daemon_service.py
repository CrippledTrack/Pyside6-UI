"""Daemon management service for Linux privileged operations.

This module provides a centralized service for managing the privileged daemon
on Linux systems, including starting, stopping, checking status, and refreshing
admin-required UI components when the daemon becomes available.
"""

from __future__ import annotations

import logging
import os
import platform
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Only import Linux-specific modules on Linux
if platform.system().lower() == "linux":
    from ..daemon import is_daemon_available, set_daemon_client
    from ..daemon.client import DaemonClient
    from ..daemon.protocol import get_socket_path
    from ..utils.elevation_linux import is_daemon_running, start_daemon
else:
    # Dummy functions for non-Linux platforms
    def is_daemon_running(*args, **kwargs) -> bool:
        return False
    
    def start_daemon(*args, **kwargs) -> Optional[object]:
        return None


class DaemonService:
    """Service for managing the privileged daemon on Linux systems."""
    
    def __init__(self):
        """Initialize the daemon service."""
        self._refresh_callbacks: list[Callable[[], None]] = []
        self._is_linux = platform.system().lower() == "linux"
    
    def is_available(self) -> bool:
        """Check if the daemon is available and connected.
        
        Returns:
            True if daemon is available, False otherwise
        """
        if not self._is_linux:
            return False
        
        try:
            return is_daemon_available()
        except Exception as e:
            logger.debug(f"Error checking daemon availability: {e}")
            return False
    
    def is_running(self) -> bool:
        """Check if the daemon process is running (socket exists).
        
        Returns:
            True if daemon socket exists, False otherwise
        """
        if not self._is_linux:
            return False
        
        from ..utils.imports import get_platforms_constants
        use_pipe_daemon = getattr(get_platforms_constants(), 'USE_PIPE_DAEMON', False)
        if use_pipe_daemon:
            try:
                from ..daemon import is_daemon_available
                return is_daemon_available()
            except Exception as e:
                logger.debug(f"Error checking if pipe daemon is running: {e}")
                return False
        
        try:
            return is_daemon_running()
        except Exception as e:
            logger.debug(f"Error checking if daemon is running: {e}")
            return False
    
    def start(self) -> tuple[bool, Optional[str]]:
        """Start the privileged daemon.
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        if not self._is_linux:
            return False, "Daemon is only available on Linux"
        
        # If client is already available, we are good
        if self.is_available():
            return True, None
            
        from ..utils.imports import get_platforms_constants
        use_pipe_daemon = getattr(get_platforms_constants(), 'USE_PIPE_DAEMON', False)
        if use_pipe_daemon:
            # In pipe mode, we don't try to connect to existing sockets or clean up stale sockets.
            # We just start a new daemon.
            return self._start_new_daemon()
        
        # Check if daemon is already running (Legacy Socket Mode specific checks, to be removed after 5.x)
        if self.is_running():
            # Check if client is set globally
            if not self.is_available():
                # Daemon is running but client not set - connect to it
                logger.info("Daemon is running but client not set, connecting...")
                if self._connect_to_existing_daemon():
                    logger.info("Connected to existing daemon")
                    self._notify_refresh_callbacks()
                    return True, None
                else:
                    logger.warning(
                        "Failed to connect to existing daemon, attempting restart"
                    )
                    return self._restart_daemon_from_stale_socket()
            else:
                # Daemon is running and client is set
                return True, None

        return self._start_new_daemon()
    
    def _connect_to_existing_daemon(self) -> bool:
        """Connect to an existing daemon and set the client globally.
        
        NOTE: Legacy Socket Mode method. To be removed after 5.x.
        
        Returns:
            True if connection succeeded, False otherwise
        """
        try:
            uid = os.getuid()
        except (AttributeError, OSError):
            uid = None
        
        socket_path = get_socket_path(uid)
        client = DaemonClient(socket_path)
        
        if client.connect():
            set_daemon_client(client)
            return True
        return False

    def _start_new_daemon(self) -> tuple[bool, Optional[str]]:
        """Launch a new daemon instance and configure the global client."""

        logger.info("Starting privileged daemon...")
        try:
            client = start_daemon()

            if client:
                # Set the daemon client globally so is_daemon_available() works
                set_daemon_client(client)
                logger.info("Daemon client set globally")

                # Notify callbacks to refresh UI
                self._notify_refresh_callbacks()

                return True, None
            else:
                return False, "Failed to start the privileged daemon"
        except Exception as e:
            logger.error(f"Error starting daemon: {e}", exc_info=True)
            return False, f"Error starting daemon: {e}"

    def _restart_daemon_from_stale_socket(self) -> tuple[bool, Optional[str]]:
        """Remove a stale socket and attempt to start a fresh daemon.
        
        NOTE: Legacy Socket Mode method. To be removed after 5.x.
        """

        try:
            uid = os.getuid()
        except (AttributeError, OSError):
            uid = None

        socket_path = get_socket_path(uid)

        if os.path.exists(socket_path):
            try:
                os.unlink(socket_path)
                logger.info(f"Removed stale daemon socket at {socket_path}")
            except OSError as e:
                logger.warning(f"Failed to remove stale daemon socket at {socket_path}: {e}")

        return self._start_new_daemon()
    
    def register_refresh_callback(self, callback: Callable[[], None]) -> None:
        """Register a callback to be called when daemon becomes available.
        
        Args:
            callback: Function to call when daemon status changes
        """
        if callback not in self._refresh_callbacks:
            self._refresh_callbacks.append(callback)
            logger.debug(f"Registered refresh callback: {callback.__name__ if hasattr(callback, '__name__') else 'anonymous'}")
    
    def unregister_refresh_callback(self, callback: Callable[[], None]) -> None:
        """Unregister a refresh callback.
        
        Args:
            callback: Function to remove from callbacks
        """
        if callback in self._refresh_callbacks:
            self._refresh_callbacks.remove(callback)
            logger.debug(f"Unregistered refresh callback: {callback.__name__ if hasattr(callback, '__name__') else 'anonymous'}")
    
    def _notify_refresh_callbacks(self) -> None:
        """Notify all registered refresh callbacks."""
        logger.info(f"Notifying {len(self._refresh_callbacks)} refresh callbacks")
        for callback in self._refresh_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in refresh callback: {e}", exc_info=True)
    
    def get_status_message(self) -> str:
        """Get a human-readable status message about the daemon.
        
        Returns:
            Status message string
        """
        if not self._is_linux:
            return "Daemon is only available on Linux"
        
        if self.is_available():
            return "The privileged daemon is currently running"
        elif self.is_running():
            return "Daemon socket exists but client not connected"
        else:
            return "The privileged daemon is not running"


__all__ = ['DaemonService']

