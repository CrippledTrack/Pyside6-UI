"""Linux privileged daemon for handling root operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .client import DaemonClient

_daemon_client: Optional['DaemonClient'] = None


def set_daemon_client(client: Optional['DaemonClient']) -> None:
    """Set the global daemon client instance.
    
    Args:
        client: The daemon client instance to set, or None to clear it
    """
    global _daemon_client
    _daemon_client = client


def get_daemon_client() -> 'DaemonClient':
    """Get the global daemon client instance.
    
    Returns:
        The daemon client instance
        
    Raises:
        RuntimeError: If daemon client is not initialized
    """
    if _daemon_client is None:
        raise RuntimeError("Daemon client not initialized. Ensure daemon is started.")
    return _daemon_client


def is_daemon_available() -> bool:
    """Check if daemon client is available and connected."""
    if _daemon_client is None:
        return False
    try:
        return _daemon_client.is_connected()
    except Exception:
        return False


__all__ = ['set_daemon_client', 'get_daemon_client', 'is_daemon_available']
