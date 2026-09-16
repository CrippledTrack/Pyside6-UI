"""macOS elevation: sudo -A askpass spawn for the privileged pipe daemon."""

from __future__ import annotations

import logging
import os
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from . import elevation_unix as unix

logger = logging.getLogger(__name__)

is_admin = unix.is_admin
check_sudo_available = unix.check_sudo_available
get_current_user = unix.get_current_user
get_current_group = unix.get_current_group
clear_daemon_process = unix.clear_daemon_process
set_daemon_process = unix.set_daemon_process
is_daemon_running = unix.is_daemon_running
stop_daemon = unix.stop_daemon

ASKPASS_PROMPT = "Administrator password required to start the privileged daemon:"
ASKPASS_TITLE = "Privileged Daemon"

# Executable askpass body. sudo -A runs this and reads the password from stdout.
# Cancel must print nothing on stdout and exit non-zero; an empty line would
# look like an empty password and make sudo prompt again. Re-raising the
# AppleScript error does both, and leaving stderr alone keeps real osascript
# failures (no GUI session, TCC denial) visible in the daemon stderr log.
ASKPASS_SCRIPT = """#!/bin/sh
exec osascript -e 'try' -e 'text returned of (display dialog "{prompt}" default answer "" with hidden answer with title "{title}" buttons {{"Cancel", "OK"}} default button "OK")' -e 'on error' -e 'error number 1' -e 'end try'
""".format(prompt=ASKPASS_PROMPT, title=ASKPASS_TITLE)

_askpass_path: Optional[str] = None


def sudo_askpass_command(daemon_cmd: list[str]) -> list[str]:
    """Return the elevated argv that preserves stdin/stdout pipes."""
    return ["sudo", "-A", "-E", *daemon_cmd]


def sudo_askpass_env(base_env: dict[str, str], askpass_path: str) -> dict[str, str]:
    """Copy *base_env* and set SUDO_ASKPASS for ``sudo -A``."""
    env = dict(base_env)
    env["SUDO_ASKPASS"] = askpass_path
    return env


def write_askpass_script(path: Optional[str] = None) -> str:
    """Write an executable osascript askpass helper and return its path."""
    if path is None:
        fd, path = tempfile.mkstemp(prefix="gui-sudo-askpass-", suffix=".sh")
        os.close(fd)
    Path(path).write_text(ASKPASS_SCRIPT, encoding="utf-8")
    os.chmod(path, stat.S_IRWXU)  # 0o700
    return path


def ensure_askpass() -> str:
    """Return a cached executable askpass path, creating it if needed."""
    global _askpass_path
    if (
        _askpass_path
        and os.path.isfile(_askpass_path)
        and os.access(_askpass_path, os.X_OK)
    ):
        return _askpass_path
    _askpass_path = write_askpass_script()
    logger.info("Wrote sudo askpass helper at %s", _askpass_path)
    return _askpass_path


def cleanup_askpass() -> None:
    """Remove the cached askpass file if it exists."""
    global _askpass_path
    if not _askpass_path:
        return
    try:
        os.remove(_askpass_path)
    except OSError:
        pass
    _askpass_path = None


def can_elevate() -> bool:
    """True when sudo exists; the GUI askpass can prompt even without a tty."""
    return check_sudo_available()


def get_sudo_status() -> dict:
    sudo_avail = check_sudo_available()
    return {
        "is_admin": is_admin(),
        "current_user": get_current_user(),
        "current_group": get_current_group(),
        "sudo_available": sudo_avail,
        "pkexec_available": False,
        "can_elevate": sudo_avail,
    }


def spawn_daemon_process() -> Optional[subprocess.Popen]:
    """Spawn the pipe daemon via ``sudo -A -E`` and wait for ping."""
    existing = unix.existing_usable_daemon()
    if existing is not None:
        return existing

    if not check_sudo_available():
        logger.error("sudo is not available for privilege escalation")
        return None

    daemon_cmd = unix.build_daemon_command()
    if daemon_cmd is None:
        return None

    askpass = ensure_askpass()
    daemon_env = sudo_askpass_env(unix.build_daemon_env(), askpass)
    argv = sudo_askpass_command(daemon_cmd)
    logger.info("Starting daemon with sudo -A...")
    try:
        process = subprocess.Popen(
            argv,
            env=daemon_env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        logger.info("Daemon process started via sudo -A with PID %s", process.pid)
    except Exception as e:
        logger.error("Failed to start daemon with sudo -A: %s", e)
        cleanup_askpass()
        return None

    daemon = unix.finalize_spawned_process(process)
    if daemon is None:
        # Cancelled prompt or failed auth: do not leave the helper on disk.
        cleanup_askpass()
    return daemon


def start_daemon() -> Optional[object]:
    """Start the privileged pipe daemon process."""
    return unix.start_daemon_from_spawn(spawn_daemon_process)


__all__ = [
    "ASKPASS_SCRIPT",
    "is_admin",
    "get_sudo_status",
    "can_elevate",
    "sudo_askpass_command",
    "sudo_askpass_env",
    "write_askpass_script",
    "ensure_askpass",
    "cleanup_askpass",
    "start_daemon",
    "spawn_daemon_process",
    "stop_daemon",
    "is_daemon_running",
    "clear_daemon_process",
    "set_daemon_process",
]
