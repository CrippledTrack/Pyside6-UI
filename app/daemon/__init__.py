"""Unix privileged daemon for handling root operations over stdin/stdout."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

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


def peek_daemon_client() -> Optional['DaemonClient']:
    """Return the global client if one was set, without requiring a connection."""
    return _daemon_client


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


def client_for_process(process: Any) -> Optional['DaemonClient']:
    """Return the existing client, or wrap *process* once if stdout is usable.

    Never constructs a second ``DaemonClient`` for a live process.
    """
    if _daemon_client is not None:
        return _daemon_client
    from .pipe_io import process_stdout_usable
    if not process_stdout_usable(process):
        return None
    from .client import DaemonClient
    client = DaemonClient(process=process)
    set_daemon_client(client)
    return client


__all__ = [
    'set_daemon_client',
    'peek_daemon_client',
    'get_daemon_client',
    'is_daemon_available',
    'client_for_process',
]
