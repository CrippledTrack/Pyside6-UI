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

        from ..constants import REQUIRE_ADMIN_BY_DEFAULT
        from ..daemon import set_daemon_client
        from ..utils.elevation_linux import start_daemon
        if not REQUIRE_ADMIN_BY_DEFAULT:
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

    def shutdown(self, daemon_client: Optional[Any]) -> None:
        if platform.system().lower() != "linux" or not daemon_client:
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
