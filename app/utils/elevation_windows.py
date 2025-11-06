from __future__ import annotations

import ctypes
import sys
import os
import subprocess


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:  # noqa: E722 - ctypes errors are non-specific here
        return False


def run_as_admin():
    """
    Attempt to re-launch the current script with administrator privileges.

    Behavior:
    - If already running as admin: returns False immediately (no relaunch).
    - If elevation request succeeds: starts elevated instance and exits current process.
    - If elevation request fails (e.g., UAC denied): raises RuntimeError.
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


def run_command_as_admin(command):
    """
    Run a specific command with administrator privileges.
    Returns the subprocess.CompletedProcess object or None if spawned in new window.
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


