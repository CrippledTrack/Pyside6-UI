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


__all__ = ['set_daemon_client', 'get_daemon_client']
