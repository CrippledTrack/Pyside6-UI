from __future__ import annotations

import os
import subprocess
import sys
import pwd
import grp
import logging
import time
import threading
from pathlib import Path
from typing import Optional
from ..daemon.protocol import get_effective_uid_gid

logger = logging.getLogger(__name__)

# Timeout constants (in seconds)
PKEXEC_COMMAND_TIMEOUT = 600  # 10 minutes for privileged commands
DAEMON_SHUTDOWN_TIMEOUT = 2   # Wait for daemon shutdown

# Global daemon process reference
_daemon_process: Optional[subprocess.Popen] = None


def clear_daemon_process() -> None:
    """Clear the module-level daemon process pointer (does not kill the process).

    Used when a client takes ownership of restarting so ``start_daemon()``
    will spawn a new process instead of returning the dead handle.
    """
    global _daemon_process
    _daemon_process = None


def set_daemon_process(process: Optional[subprocess.Popen]) -> None:
    """Update the module-level daemon process pointer."""
    global _daemon_process
    _daemon_process = process


def _set_pdeathsig():
    """Ask the Linux kernel to send SIGTERM when our parent process dies.
    
    Uses prctl(PR_SET_PDEATHSIG, SIGTERM) to register a kernel-level parent
    death signal. This ensures the privileged daemon is cleaned up even if the
    GUI process hangs, is killed with SIGKILL, or otherwise exits abnormally.
    
    This function is intended to be passed as preexec_fn to subprocess.Popen,
    where it runs in the child process after fork() but before exec().
    """
    import ctypes
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    PR_SET_PDEATHSIG = 1
    SIGTERM = 15
    result = libc.prctl(PR_SET_PDEATHSIG, SIGTERM)
    if result != 0:
        import ctypes.util
        errno = ctypes.get_errno()
        # Log to stderr since this runs in child before exec
        import sys
        print(f"[Daemon-preexec] WARNING: prctl(PR_SET_PDEATHSIG) failed with errno {errno}",
              file=sys.stderr, flush=True)


def _drain_stderr(process: subprocess.Popen):
    """Continuously reads and logs/discards stderr of the given process to prevent deadlock."""
    logger.info(f"Starting stderr draining thread for PID {process.pid}")
    try:
        while True:
            line = process.stderr.readline()
            if not line:
                break
            try:
                line_str = line.decode('utf-8', errors='ignore').strip()
                if line_str:
                    line_upper = line_str.upper()
                    if " - ERROR - " in line_upper or " - CRITICAL - " in line_upper or "TRACEBACK" in line_upper or "EXCEPTION" in line_upper:
                        logger.error(f"[Daemon-Stderr] {line_str}")
                    elif " - WARNING - " in line_upper:
                        logger.warning(f"[Daemon-Stderr] {line_str}")
                    elif " - DEBUG - " in line_upper:
                        logger.debug(f"[Daemon-Stderr] {line_str}")
                    elif " - INFO - " in line_upper:
                        logger.info(f"[Daemon-Stderr] {line_str}")
                    else:
                        # Fallback for general printed statements
                        if any(err in line_upper for err in ["ERROR", "FAILED", "CRITICAL", "EXCEPTION"]):
                            logger.error(f"[Daemon-Stderr] {line_str}")
                        else:
                            logger.info(f"[Daemon-Stderr] {line_str}")
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"Error draining stderr: {e}")


def is_admin():
    try:
        return os.geteuid() == 0
    except AttributeError:
        try:
            return os.getuid() == 0
        except AttributeError:
            return False


def run_command_as_admin(command, description="This operation", interactive=False):
    """Run a command with admin privileges using direct elevation.
    
    Note: This should only be used before the daemon is available (e.g., Qt dependency installation).
    For normal operations, use the daemon via GUI.app.utils.privileged.run_privileged_command instead.
    
    Args:
        command: Command and arguments as list
        description: Description of operation (for prompts)
        interactive: If True, don't capture output (allows password prompts to display)
    """
    logger.info(f"run_command_as_admin: command={command}, interactive={interactive}, is_admin={is_admin()}")
    
    if is_admin():
        if interactive:
            return subprocess.run(command, text=True)
        return subprocess.run(command, capture_output=True, text=True)

    # Check for pkexec/sudo availability
    pkexec_avail = check_pkexec_available()
    sudo_avail = check_sudo_available()
    logger.info(f"Elevation methods available: pkexec={pkexec_avail}, sudo={sudo_avail}")

    if pkexec_avail:
        try:
            pkexec_command = ['pkexec'] + command
            logger.info(f"Attempting elevation with pkexec: {pkexec_command}")
            # pkexec uses its own GUI prompt - it displays separately
            # We can capture output even with pkexec since the GUI prompt is independent
            result = subprocess.run(pkexec_command, capture_output=True, text=True, timeout=PKEXEC_COMMAND_TIMEOUT)
            logger.info(f"pkexec completed with return code {result.returncode}")
            if result.returncode != 0:
                logger.warning(f"pkexec command failed with return code {result.returncode}")
                if result.stderr:
                    logger.warning(f"Error output: {result.stderr}")
            return result
        except subprocess.TimeoutExpired:
            logger.error("pkexec command timed out")
            raise
        except Exception as e:
            logger.warning(f"pkexec failed with exception: {e}, falling back to sudo")
            # Fall through to sudo

    if sudo_avail:
        try:
            sudo_command = ['sudo'] + command
            logger.info(f"Attempting elevation with sudo: {sudo_command}")
            # For sudo with interactive, use stdin=None so it can prompt on terminal
            if interactive:
                # Don't capture output so password prompt can show, but we need returncode
                # Use stdin=None to allow password prompt on tty
                result = subprocess.run(sudo_command, text=True, stdin=None)
                logger.info(f"sudo (interactive) completed with return code {result.returncode}")
                return result
            # Non-interactive: capture output
            result = subprocess.run(sudo_command, capture_output=True, text=True)
            logger.info(f"sudo (non-interactive) completed with return code {result.returncode}")
            return result
        except Exception as e:
            logger.error(f"sudo failed with exception: {e}")
            raise
    else:
        error_msg = "Neither pkexec nor sudo is available for privilege escalation"
        logger.error(error_msg)
        raise Exception(error_msg)


def check_sudo_available():
    try:
        result = subprocess.run(['which', 'sudo'], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def check_pkexec_available():
    try:
        result = subprocess.run(['which', 'pkexec'], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def get_current_user():
    try:
        return pwd.getpwuid(os.getuid()).pw_name
    except (KeyError, AttributeError):
        return os.getenv('USER', 'unknown')


def get_current_group():
    try:
        return grp.getgrgid(os.getgid()).gr_name
    except (KeyError, AttributeError):
        return os.getenv('GROUP', 'unknown')


def can_elevate():
    if check_pkexec_available():
        return True
    if not check_sudo_available():
        return False
    try:
        result = subprocess.run(['sudo', '-n', 'true'], capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return True


def get_sudo_status():
    return {
        'is_admin': is_admin(),
        'current_user': get_current_user(),
        'current_group': get_current_group(),
        'sudo_available': check_sudo_available(),
        'pkexec_available': check_pkexec_available(),
        'can_elevate': can_elevate() if (check_sudo_available() or check_pkexec_available()) else False,
    }


def is_daemon_running() -> bool:
    """Check if the privileged pipe daemon process is active."""
    global _daemon_process
    return _daemon_process is not None and _daemon_process.poll() is None


def start_daemon() -> Optional[object]:
    """Start the privileged pipe daemon process.

    Returns:
        DaemonClient instance if successful, None otherwise
    """
    global _daemon_process

    if is_daemon_running():
        logger.info("Daemon already running")
        from ..daemon import get_daemon_client, is_daemon_available
        if is_daemon_available():
            return get_daemon_client()
        from ..daemon.client import DaemonClient
        return DaemonClient(process=_daemon_process)

    if hasattr(sys, 'frozen') and sys.frozen:
        exe_path = sys.executable
        daemon_cmd = [exe_path, '--pipe']
    else:
        exe_path = sys.executable
        script_path = None

        if sys.argv and sys.argv[0] and sys.argv[0] != '-c':
            potential_path = Path(sys.argv[0])
            if potential_path.is_absolute() and potential_path.exists():
                script_path = potential_path
            elif (Path.cwd() / potential_path).exists():
                script_path = Path.cwd() / potential_path
            elif potential_path.exists():
                script_path = potential_path.resolve()

        if script_path is None or not script_path.exists():
            try:
                import __main__
                if hasattr(__main__, '__file__') and __main__.__file__:
                    main_file = Path(__main__.__file__)
                    if main_file.exists():
                        script_path = main_file
            except Exception:
                pass

        if script_path is None or not script_path.exists():
            app_py = Path(__file__).parent.parent / 'app' / 'app.py'
            if app_py.exists():
                root_dir = app_py.parent.parent.parent
                gui_pkg = app_py.parent.parent.name
                for py_file in root_dir.glob('*.py'):
                    try:
                        content = py_file.read_text(encoding='utf-8', errors='ignore')
                        if f'from {gui_pkg}.app.app import run' in content or f'{gui_pkg}.app.app' in content:
                            script_path = py_file
                            break
                    except Exception:
                        continue

        if script_path is None or not script_path.exists():
            logger.error("Could not determine main script path for daemon")
            return None

        logger.info(f"Daemon script path: {script_path}")
        daemon_cmd = [exe_path, str(script_path), '--pipe']

    original_uid, original_gid = get_effective_uid_gid()
    if os.environ.get('SUDO_UID') or os.environ.get('PKEXEC_UID'):
        logger.info(f"Running via elevation, original UID: {original_uid}, GID: {original_gid}")
    else:
        logger.info(f"Running as normal user, UID: {original_uid}, GID: {original_gid}")

    if original_uid is not None:
        daemon_cmd.extend(['--uid', str(original_uid)])
        logger.info(f"Passing --uid {original_uid} to daemon")
    if original_gid is not None:
        daemon_cmd.extend(['--gid', str(original_gid)])
        logger.info(f"Passing --gid {original_gid} to daemon")

    daemon_env = os.environ.copy()
    if original_uid is not None:
        daemon_env['PKEXEC_UID'] = str(original_uid)
        daemon_env['SUDO_UID'] = str(original_uid)
    if original_gid is not None:
        daemon_env['PKEXEC_GID'] = str(original_gid)
        daemon_env['SUDO_GID'] = str(original_gid)

    process = None
    if check_pkexec_available():
        logger.info("Starting daemon with pkexec...")
        try:
            process = subprocess.Popen(
                ['pkexec'] + daemon_cmd,
                env=daemon_env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
                preexec_fn=_set_pdeathsig
            )
            _daemon_process = process
            logger.info(f"Daemon process started via pkexec with PID {process.pid}")
            threading.Thread(target=_drain_stderr, name="DaemonStderrDrainer", args=(process,), daemon=True).start()
        except Exception as e:
            logger.error(f"Failed to start daemon with pkexec: {e}")
            process = None

    if process is None and check_sudo_available():
        logger.info("Starting daemon with sudo...")
        try:
            process = subprocess.Popen(
                ['sudo', '-E'] + daemon_cmd,
                env=daemon_env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
                preexec_fn=_set_pdeathsig
            )
            _daemon_process = process
            logger.info(f"Daemon process started via sudo with PID {process.pid}")
            threading.Thread(target=_drain_stderr, name="DaemonStderrDrainer", args=(process,), daemon=True).start()
        except Exception as e:
            logger.error(f"Failed to start daemon with sudo: {e}")
            return None

    if process is None:
        logger.error("Neither pkexec nor sudo available")
        return None

    logger.info("Verifying pipe daemon connection via ping...")
    from ..daemon.client import DaemonClient
    client = DaemonClient(process=process)

    for i in range(120):
        if process.poll() is not None:
            logger.error(f"Pipe daemon process exited with return code {process.returncode}")
            _daemon_process = None
            return None
        try:
            response = client.request('ping', {}, timeout=1.0)
            if response.get('success') and response.get('result') == 'pong':
                logger.info("Successfully connected to pipe daemon via ping")
                return client
        except Exception as e:
            logger.debug(f"Ping attempt {i} failed: {e}")
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


def stop_daemon():
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
            client.request('shutdown', {}, timeout=2.0)
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
            logger.info(f"Pipe daemon already stopped or shutting down (connection closed: {e})")
        else:
            logger.error(f"Error requesting pipe daemon shutdown: {e}")
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
    'is_admin',
    'run_command_as_admin',
    'get_sudo_status',
    'start_daemon',
    'stop_daemon',
    'is_daemon_running',
    'clear_daemon_process',
    'set_daemon_process',
]
