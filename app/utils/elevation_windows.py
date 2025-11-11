"""Windows elevation utilities for running commands with administrator privileges.

This module provides functions to check admin status and elevate processes
on Windows systems using UAC (User Account Control).
"""

from __future__ import annotations

import ctypes
import logging
import os
import subprocess
import sys

logger = logging.getLogger(__name__)


def is_admin() -> bool:
    """Check if the current process is running with administrator privileges.
    
    Returns:
        True if running as administrator, False otherwise
    """
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:  # noqa: BLE001 - ctypes errors are non-specific here
        return False


def run_as_admin() -> bool:
    """Attempt to re-launch the current script with administrator privileges.

    Behavior:
    - If already running as admin: returns False immediately (no relaunch).
    - If elevation request succeeds: starts elevated instance and exits current process.
    - If elevation request fails (e.g., UAC denied): raises RuntimeError.
    
    Returns:
        False if already running as admin, otherwise exits current process
        
    Raises:
        RuntimeError: If elevation request fails
    """
    if is_admin():
        return False

    script = os.path.abspath(sys.argv[0])
    params = ' '.join(sys.argv[1:])

    ret = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        sys.executable,
        f'"{script}" {params}',
        None,
        1,
    )

    if ret > 32:
        sys.exit(0)
    raise RuntimeError(f"ShellExecuteW returned error code {ret}")


def run_command_as_admin(command: list[str]) -> subprocess.CompletedProcess[str] | None:
    """Run a specific command with administrator privileges.
    
    Args:
        command: Command and arguments as a list
        
    Returns:
        subprocess.CompletedProcess if running as admin, None if spawned in new window
        
    Raises:
        Exception: If elevation request fails
    """
    if is_admin():
        return subprocess.run(command, capture_output=True, text=True)

    cmd = ' '.join(command)

    ret = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        "cmd.exe",
        f'/c {cmd}',
        None,
        1,
    )

    if ret <= 32:
        raise Exception(f"Failed to run command with elevation. Error code: {ret}")

    return None


__all__ = ['is_admin', 'run_as_admin', 'run_command_as_admin']
