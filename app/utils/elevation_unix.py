"""Shared Unix helpers for the privileged pipe daemon.

Linux (pkexec/sudo) and macOS (sudo -A) spawn backends share process
ownership, daemon argv construction, stderr draining, and ping-wait.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from ..daemon.protocol import get_effective_uid_gid

logger = logging.getLogger(__name__)

DAEMON_SHUTDOWN_TIMEOUT = 2

_daemon_process: Optional[subprocess.Popen] = None


def clear_daemon_process() -> None:
    """Clear the module-level daemon process pointer (does not kill the process)."""
    global _daemon_process
    _daemon_process = None


def set_daemon_process(process: Optional[subprocess.Popen]) -> None:
    """Update the module-level daemon process pointer."""
    global _daemon_process
    _daemon_process = process


def get_daemon_process() -> Optional[subprocess.Popen]:
    """Return the current daemon process handle, if any."""
    return _daemon_process


def is_admin() -> bool:
    """Return True when the current process is running as root."""
    try:
        return os.geteuid() == 0
    except AttributeError:
        try:
            return os.getuid() == 0
        except AttributeError:
            return False


def check_sudo_available() -> bool:
    try:
        result = subprocess.run(["which", "sudo"], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def get_current_user() -> str:
    try:
        import pwd

        return pwd.getpwuid(os.getuid()).pw_name
    except (KeyError, AttributeError):
        return os.getenv("USER", "unknown")


def get_current_group() -> str:
    try:
        import grp

        return grp.getgrgid(os.getgid()).gr_name
    except (KeyError, AttributeError):
        return os.getenv("GROUP", "unknown")


def is_daemon_running() -> bool:
    """Check if the privileged pipe daemon process is active."""
    return _daemon_process is not None and _daemon_process.poll() is None


def drain_stderr(process: subprocess.Popen) -> None:
    """Continuously read and log stderr of *process* to prevent deadlock."""
    logger.info("Starting stderr draining thread for PID %s", process.pid)
    try:
        while True:
            line = process.stderr.readline()
            if not line:
                break
            try:
                line_str = line.decode("utf-8", errors="ignore").strip()
                if not line_str:
                    continue
                line_upper = line_str.upper()
                if (
                    " - ERROR - " in line_upper
                    or " - CRITICAL - " in line_upper
                    or "TRACEBACK" in line_upper
                    or "EXCEPTION" in line_upper
                ):
                    logger.error("[Daemon-Stderr] %s", line_str)
                elif " - WARNING - " in line_upper:
                    logger.warning("[Daemon-Stderr] %s", line_str)
                elif " - DEBUG - " in line_upper:
                    logger.debug("[Daemon-Stderr] %s", line_str)
                elif " - INFO - " in line_upper:
                    logger.info("[Daemon-Stderr] %s", line_str)
                elif any(err in line_upper for err in ["ERROR", "FAILED", "CRITICAL", "EXCEPTION"]):
                    logger.error("[Daemon-Stderr] %s", line_str)
                else:
                    logger.info("[Daemon-Stderr] %s", line_str)
            except Exception:
                pass
    except Exception as e:
        logger.debug("Error draining stderr: %s", e)


def start_stderr_drainer(process: subprocess.Popen) -> None:
    threading.Thread(
        target=drain_stderr,
        name="DaemonStderrDrainer",
        args=(process,),
        daemon=True,
    ).start()


def replace_unusable_daemon_process() -> None:
    """Drop a live process whose stdout is closed so a replacement can spawn."""
    global _daemon_process
    old = _daemon_process
    _daemon_process = None
    if old is None or old.poll() is not None:
        return
    try:
        old.terminate()
        old.wait(timeout=DAEMON_SHUTDOWN_TIMEOUT)
    except Exception:
        try:
            old.kill()
        except Exception:
            pass


def existing_usable_daemon() -> Optional[subprocess.Popen]:
    """Return the live daemon if its stdout is usable; else clear it."""
    from ..daemon.pipe_io import process_stdout_usable

    if not is_daemon_running():
        return None
    if process_stdout_usable(_daemon_process):
        logger.info("Daemon already running")
        return _daemon_process
    logger.warning("Existing daemon stdout is unusable; replacing the process")
    replace_unusable_daemon_process()
    return None


def _resolve_script_path() -> Optional[Path]:
    if sys.argv and sys.argv[0] and sys.argv[0] != "-c":
        potential_path = Path(sys.argv[0])
        if potential_path.is_absolute() and potential_path.exists():
            return potential_path
        cwd_path = Path.cwd() / potential_path
        if cwd_path.exists():
            return cwd_path
        if potential_path.exists():
            return potential_path.resolve()

    try:
        import __main__

        if hasattr(__main__, "__file__") and __main__.__file__:
            main_file = Path(__main__.__file__)
            if main_file.exists():
                return main_file
    except Exception:
        pass

    app_py = Path(__file__).parent.parent / "app" / "app.py"
    if app_py.exists():
        root_dir = app_py.parent.parent.parent
        gui_pkg = app_py.parent.parent.name
        for py_file in root_dir.glob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                if (
                    f"from {gui_pkg}.app.app import run" in content
                    or f"{gui_pkg}.app.app" in content
                ):
                    return py_file
            except Exception:
                continue
    return None


def build_daemon_command(
    *,
    parent_pid: Optional[int] = None,
    uid: Optional[int] = None,
    gid: Optional[int] = None,
) -> Optional[list[str]]:
    """Build the unprivileged argv for the pipe daemon (no pkexec/sudo).

    Includes ``--pipe``, original ``--uid``/``--gid``, and ``--parent-pid`` of
    the GUI so the helper can exit when the unprivileged parent dies.
    """
    if hasattr(sys, "frozen") and sys.frozen:
        daemon_cmd = [sys.executable, "--pipe"]
    else:
        script_path = _resolve_script_path()
        if script_path is None or not script_path.exists():
            logger.error("Could not determine main script path for daemon")
            return None
        logger.info("Daemon script path: %s", script_path)
        daemon_cmd = [sys.executable, str(script_path), "--pipe"]

    original_uid, original_gid = get_effective_uid_gid()
    if uid is not None:
        original_uid = uid
    if gid is not None:
        original_gid = gid

    if os.environ.get("SUDO_UID") or os.environ.get("PKEXEC_UID"):
        logger.info(
            "Running via elevation, original UID: %s, GID: %s",
            original_uid,
            original_gid,
        )
    else:
        logger.info(
            "Running as normal user, UID: %s, GID: %s",
            original_uid,
            original_gid,
        )

    if original_uid is not None:
        daemon_cmd.extend(["--uid", str(original_uid)])
        logger.info("Passing --uid %s to daemon", original_uid)
    if original_gid is not None:
        daemon_cmd.extend(["--gid", str(original_gid)])
        logger.info("Passing --gid %s to daemon", original_gid)

    watch_pid = os.getpid() if parent_pid is None else parent_pid
    daemon_cmd.extend(["--parent-pid", str(watch_pid)])
    logger.info("Passing --parent-pid %s to daemon", watch_pid)
    return daemon_cmd


def build_daemon_env() -> dict[str, str]:
    """Copy the current environment and stamp original uid/gid for the helper."""
    daemon_env = os.environ.copy()
    original_uid, original_gid = get_effective_uid_gid()
    if original_uid is not None:
        daemon_env["PKEXEC_UID"] = str(original_uid)
        daemon_env["SUDO_UID"] = str(original_uid)
    if original_gid is not None:
        daemon_env["PKEXEC_GID"] = str(original_gid)
        daemon_env["SUDO_GID"] = str(original_gid)
    return daemon_env


def wait_for_daemon_ping(process: subprocess.Popen) -> Optional[subprocess.Popen]:
    """Ping the spawned process until ready, or tear it down on failure."""
    global _daemon_process
    from ..daemon.pipe_io import ping_daemon_process

    logger.info("Verifying pipe daemon connection via ping...")
    for i in range(120):
        if process.poll() is not None:
            logger.error(
                "Pipe daemon process exited with return code %s",
                process.returncode,
            )
            _daemon_process = None
            return None
        try:
            if ping_daemon_process(process, timeout=1.0):
                logger.info("Successfully connected to pipe daemon via ping")
                return process
        except Exception as e:
            logger.debug("Ping attempt %s failed: %s", i, e)
        time.sleep(0.5)

    logger.error("Pipe daemon failed to respond to ping within timeout")
    try:
        process.terminate()
        process.wait(timeout=2.0)
    except Exception:
        try:
            process.kill()
        except Exception:
            pass
    _daemon_process = None
    return None


def finalize_spawned_process(process: subprocess.Popen) -> Optional[subprocess.Popen]:
    """Record *process*, drain stderr, and wait until ping succeeds."""
    global _daemon_process
    _daemon_process = process
    start_stderr_drainer(process)
    return wait_for_daemon_ping(process)


def start_daemon_from_spawn(
    spawn_fn: Callable[[], Optional[subprocess.Popen]],
) -> Optional[object]:
    """Spawn via *spawn_fn* and wrap a ``DaemonClient``."""
    process = spawn_fn()
    if process is None:
        return None
    from ..daemon import client_for_process

    return client_for_process(process)


def stop_daemon() -> None:
    """Stop the privileged pipe daemon process gracefully."""
    global _daemon_process

    if not _daemon_process or _daemon_process.poll() is not None:
        logger.info("Pipe daemon not running")
        _daemon_process = None
        return

    try:
        from ..daemon import get_daemon_client, is_daemon_available

        if is_daemon_available():
            client = get_daemon_client()
            logger.info("Sending shutdown request to pipe daemon...")
            client.request("shutdown", {}, timeout=2.0)
            client.disconnect()
        else:
            logger.info("No active daemon client, terminating pipe daemon process...")
            _daemon_process.terminate()
            try:
                _daemon_process.wait(timeout=2.0)
            except Exception:
                try:
                    _daemon_process.kill()
                except Exception:
                    pass
    except Exception as e:
        if "Connection closed by daemon" in str(e) or "pipe EOF" in str(e):
            logger.info(
                "Pipe daemon already stopped or shutting down (connection closed: %s)",
                e,
            )
        else:
            logger.error("Error requesting pipe daemon shutdown: %s", e)
        if _daemon_process:
            try:
                _daemon_process.terminate()
                _daemon_process.wait(timeout=DAEMON_SHUTDOWN_TIMEOUT)
            except Exception:
                try:
                    _daemon_process.kill()
                except Exception:
                    pass
    _daemon_process = None


__all__ = [
    "DAEMON_SHUTDOWN_TIMEOUT",
    "is_admin",
    "check_sudo_available",
    "get_current_user",
    "get_current_group",
    "clear_daemon_process",
    "set_daemon_process",
    "get_daemon_process",
    "is_daemon_running",
    "existing_usable_daemon",
    "build_daemon_command",
    "build_daemon_env",
    "finalize_spawned_process",
    "start_daemon_from_spawn",
    "stop_daemon",
]
