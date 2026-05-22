"""
Daemon lifecycle management for privileged operations.
"""
from __future__ import annotations

import logging
import platform
from typing import Any, Optional


logger = logging.getLogger(__name__)


class DaemonLifecycleService:
    """Start and stop the privileged daemon when required."""

    def start_if_required(self, container: Any) -> Optional[Any]:
        if platform.system().lower() != "linux":
            return None

        # Check if running directly as root
        import os
        try:
            is_root = os.getuid() == 0 or os.geteuid() == 0
        except (AttributeError, OSError):
            is_root = False

        if is_root:
            logger.info("Application is running directly as root. Initializing LocalDaemonClient.")
            from ..daemon.client import LocalDaemonClient
            from ..daemon import set_daemon_client
            daemon_client = LocalDaemonClient()
            set_daemon_client(daemon_client)
            return daemon_client

        from ..utils.imports import get_platforms_constants
        require_admin_by_default = getattr(get_platforms_constants(), 'REQUIRE_ADMIN_BY_DEFAULT', False)
        from ..daemon import set_daemon_client
        from ..utils.elevation_linux import start_daemon
        if not require_admin_by_default:
            logger.info("REQUIRE_ADMIN_BY_DEFAULT is False - skipping privileged daemon startup")
            return None

        logger.info("Starting privileged daemon...")
        daemon_client = start_daemon()
        if not daemon_client or not daemon_client.is_connected():
            logger.warning(
                "Failed to start privileged daemon. Some features requiring admin privileges will be disabled."
            )
            logger.warning("The application will continue in limited mode.")
            return None

        set_daemon_client(daemon_client)
        logger.info("Privileged daemon started successfully")
        return daemon_client

    def shutdown(self, daemon_client: Optional[Any] = None) -> None:
        if platform.system().lower() != "linux":
            return

        if daemon_client is None:
            try:
                from ..daemon import get_daemon_client, is_daemon_available
                if is_daemon_available():
                    daemon_client = get_daemon_client()
            except Exception:
                pass

        if not daemon_client:
            # Try to stop daemon process if it was spawned but client is not available/connected
            try:
                from ..utils.elevation_linux import stop_daemon
                stop_daemon()
            except Exception:
                pass
            return

        from ..daemon.client import LocalDaemonClient
        if isinstance(daemon_client, LocalDaemonClient):
            logger.info("Local root mode active, no external daemon to stop")
            return

        from ..utils.elevation_linux import stop_daemon

        logger.info("Stopping privileged daemon...")
        try:
            if daemon_client.is_connected():
                daemon_client.request("shutdown", {})
                daemon_client.disconnect()
        except Exception:
            # Ignore errors during cleanup - daemon may already be stopped
            pass
        stop_daemon()


__all__ = ["DaemonLifecycleService"]
