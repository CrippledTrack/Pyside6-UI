"""Linux elevation: pkexec/sudo wrappers and privileged daemon spawn."""

from __future__ import annotations

import logging
import subprocess
from typing import Optional

from . import elevation_unix as unix

logger = logging.getLogger(__name__)

PKEXEC_COMMAND_TIMEOUT = 600

is_admin = unix.is_admin
check_sudo_available = unix.check_sudo_available
get_current_user = unix.get_current_user
get_current_group = unix.get_current_group
clear_daemon_process = unix.clear_daemon_process
set_daemon_process = unix.set_daemon_process
is_daemon_running = unix.is_daemon_running
stop_daemon = unix.stop_daemon


def _set_pdeathsig():
    """Ask the Linux kernel to send SIGTERM when our parent process dies.

    Uses prctl(PR_SET_PDEATHSIG, SIGTERM) to register a kernel-level parent
    death signal. This ensures the privileged daemon is cleaned up even if the
    GUI process hangs, is killed with SIGKILL, or otherwise exits abnormally.

    This function is intended to be passed as preexec_fn to subprocess.Popen,
    where it runs in the child process after fork() but before exec().
    """
    import ctypes
    import sys

    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    PR_SET_PDEATHSIG = 1
    SIGTERM = 15
    result = libc.prctl(PR_SET_PDEATHSIG, SIGTERM)
    if result != 0:
        errno = ctypes.get_errno()
        print(
            f"[Daemon-preexec] WARNING: prctl(PR_SET_PDEATHSIG) failed with errno {errno}",
            file=sys.stderr,
            flush=True,
        )


def run_command_as_admin(command, description="This operation", interactive=False):
    """Run a command with admin privileges using direct elevation.

    Note: This should only be used before the daemon is available (e.g., Qt
    dependency installation). For normal operations, use the daemon via
    GUI.app.utils.privileged.run_privileged_command instead.

    Args:
        command: Command and arguments as list
        description: Description of operation (for prompts)
        interactive: If True, don't capture output (allows password prompts to display)
    """
    logger.info(
        "run_command_as_admin: command=%s, interactive=%s, is_admin=%s",
        command,
        interactive,
        is_admin(),
    )

    if is_admin():
        if interactive:
            return subprocess.run(command, text=True)
        return subprocess.run(command, capture_output=True, text=True)

    pkexec_avail = check_pkexec_available()
    sudo_avail = check_sudo_available()
    logger.info(
        "Elevation methods available: pkexec=%s, sudo=%s",
        pkexec_avail,
        sudo_avail,
    )

    if pkexec_avail:
        try:
            pkexec_command = ["pkexec"] + command
            logger.info("Attempting elevation with pkexec: %s", pkexec_command)
            result = subprocess.run(
                pkexec_command,
                capture_output=True,
                text=True,
                timeout=PKEXEC_COMMAND_TIMEOUT,
            )
            logger.info("pkexec completed with return code %s", result.returncode)
            if result.returncode != 0:
                logger.warning(
                    "pkexec command failed with return code %s",
                    result.returncode,
                )
                if result.stderr:
                    logger.warning("Error output: %s", result.stderr)
            return result
        except subprocess.TimeoutExpired:
            logger.error("pkexec command timed out")
            raise
        except Exception as e:
            logger.warning("pkexec failed with exception: %s, falling back to sudo", e)

    if sudo_avail:
        try:
            sudo_command = ["sudo"] + command
            logger.info("Attempting elevation with sudo: %s", sudo_command)
            if interactive:
                result = subprocess.run(sudo_command, text=True, stdin=None)
                logger.info(
                    "sudo (interactive) completed with return code %s",
                    result.returncode,
                )
                return result
            result = subprocess.run(sudo_command, capture_output=True, text=True)
            logger.info(
                "sudo (non-interactive) completed with return code %s",
                result.returncode,
            )
            return result
        except Exception as e:
            logger.error("sudo failed with exception: %s", e)
            raise
    error_msg = "Neither pkexec nor sudo is available for privilege escalation"
    logger.error(error_msg)
    raise Exception(error_msg)


def check_pkexec_available():
    try:
        result = subprocess.run(["which", "pkexec"], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def can_elevate():
    if check_pkexec_available():
        return True
    if not check_sudo_available():
        return False
    try:
        result = subprocess.run(["sudo", "-n", "true"], capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return True


def get_sudo_status():
    return {
        "is_admin": is_admin(),
        "current_user": get_current_user(),
        "current_group": get_current_group(),
        "sudo_available": check_sudo_available(),
        "pkexec_available": check_pkexec_available(),
        "can_elevate": can_elevate()
        if (check_sudo_available() or check_pkexec_available())
        else False,
    }


def _popen_elevated(argv: list[str], env: dict[str, str]) -> Optional[subprocess.Popen]:
    try:
        process = subprocess.Popen(
            argv,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            preexec_fn=_set_pdeathsig,
        )
        logger.info("Daemon process started via %s with PID %s", argv[0], process.pid)
        return process
    except Exception as e:
        logger.error("Failed to start daemon with %s: %s", argv[0], e)
        return None


def spawn_daemon_process() -> Optional[subprocess.Popen]:
    """Spawn and verify a privileged daemon process without wrapping a client.

    Returns the process after a successful ping. The caller owns the pipes
    and must attach at most one reader.
    """
    existing = unix.existing_usable_daemon()
    if existing is not None:
        return existing

    daemon_cmd = unix.build_daemon_command()
    if daemon_cmd is None:
        return None
    daemon_env = unix.build_daemon_env()

    process = None
    if check_pkexec_available():
        logger.info("Starting daemon with pkexec...")
        process = _popen_elevated(["pkexec"] + daemon_cmd, daemon_env)

    if process is None and check_sudo_available():
        logger.info("Starting daemon with sudo...")
        process = _popen_elevated(["sudo", "-E"] + daemon_cmd, daemon_env)
        if process is None:
            return None

    if process is None:
        logger.error("Neither pkexec nor sudo available")
        return None

    return unix.finalize_spawned_process(process)


def start_daemon() -> Optional[object]:
    """Start the privileged pipe daemon process.

    Returns:
        DaemonClient instance if successful, None otherwise
    """
    return unix.start_daemon_from_spawn(spawn_daemon_process)


__all__ = [
    "is_admin",
    "run_command_as_admin",
    "get_sudo_status",
    "start_daemon",
    "spawn_daemon_process",
    "stop_daemon",
    "is_daemon_running",
    "clear_daemon_process",
    "set_daemon_process",
    "can_elevate",
    "check_sudo_available",
    "check_pkexec_available",
]
