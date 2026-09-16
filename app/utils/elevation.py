"""Platform facade for admin checks and privileged-daemon spawn/stop.

Callers that should work on Linux and macOS import this module instead of
``elevation_linux`` or ``elevation_macos``. Process ownership lives in
``elevation_unix`` so client restart cannot fork a second daemon handle.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Tuple

from ..constants import CURRENT_PLATFORM

logger = logging.getLogger(__name__)

_DAEMON_PLATFORMS = frozenset({"linux", "darwin"})


def supports_privileged_daemon(platform_name: Optional[str] = None) -> bool:
    """Return True when this OS uses a pipe daemon instead of process relaunch.

    Linux and macOS keep the GUI unprivileged and spawn a root helper.
    Windows uses UAC relaunch of the whole process.
    """
    name = (platform_name or CURRENT_PLATFORM).lower()
    return name in _DAEMON_PLATFORMS


def privileged_action_copy(uses_daemon: bool) -> Tuple[str, str]:
    """Return (description, button_label) for admin-required UI chrome."""
    if uses_daemon:
        return (
            "The privileged daemon is not currently running.\n"
            "Some features requiring root access will be disabled.\n\n"
            "Click the button below to start the daemon and "
            "grant administrator privileges when prompted.",
            "Start Privileged Daemon",
        )
    return (
        "This tab requires administrator privileges to run.\n"
        "Please restart the application with elevated privileges.",
        "Restart as Administrator",
    )


def _backend():
    if CURRENT_PLATFORM == "linux":
        from . import elevation_linux as impl

        return impl
    if CURRENT_PLATFORM == "darwin":
        from . import elevation_macos as impl

        return impl
    return None


def is_admin() -> bool:
    if CURRENT_PLATFORM == "windows":
        from .elevation_windows import is_admin as windows_is_admin

        return windows_is_admin()
    impl = _backend()
    if impl is None:
        return False
    return bool(impl.is_admin())


def get_sudo_status() -> Optional[dict[str, Any]]:
    impl = _backend()
    if impl is None:
        return None
    return impl.get_sudo_status()


def spawn_daemon_process():
    impl = _backend()
    if impl is None:
        logger.error("Privileged daemon spawn is not supported on %s", CURRENT_PLATFORM)
        return None
    return impl.spawn_daemon_process()


def start_daemon() -> Optional[object]:
    impl = _backend()
    if impl is None:
        return None
    return impl.start_daemon()


def stop_daemon() -> None:
    impl = _backend()
    if impl is None:
        return
    impl.stop_daemon()
    if CURRENT_PLATFORM == "darwin":
        from .elevation_macos import cleanup_askpass

        cleanup_askpass()


def clear_daemon_process() -> None:
    from .elevation_unix import clear_daemon_process as _clear

    _clear()


def set_daemon_process(process) -> None:
    from .elevation_unix import set_daemon_process as _set

    _set(process)


def is_daemon_running() -> bool:
    from .elevation_unix import is_daemon_running as _running

    return _running()


__all__ = [
    "supports_privileged_daemon",
    "is_admin",
    "get_sudo_status",
    "spawn_daemon_process",
    "start_daemon",
    "stop_daemon",
    "clear_daemon_process",
    "set_daemon_process",
    "is_daemon_running",
    "privileged_action_copy",
]
