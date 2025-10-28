"""Linux privileged daemon for handling root operations."""

_daemon_client = None


def set_daemon_client(client):
    """Set the global daemon client instance."""
    global _daemon_client
    _daemon_client = client


def get_daemon_client():
    """Get the global daemon client instance."""
    if _daemon_client is None:
        raise RuntimeError("Daemon client not initialized. Ensure daemon is started.")
    return _daemon_client


def is_daemon_available() -> bool:
    """Check if daemon client is available and connected."""
    if _daemon_client is None:
        return False
    try:
        return _daemon_client.is_connected()
    except:
        return False


__all__ = ['set_daemon_client', 'get_daemon_client', 'is_daemon_available']
