from __future__ import annotations

import os
import subprocess
import sys
import pwd
import grp
import logging
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Timeout constants (in seconds)
PKEXEC_COMMAND_TIMEOUT = 600  # 10 minutes for privileged commands
DAEMON_SHUTDOWN_TIMEOUT = 2   # Wait for daemon shutdown
DAEMON_QUICK_TIMEOUT = 1      # Quick daemon status check

# Global daemon process reference
_daemon_process: Optional[subprocess.Popen] = None


def is_admin():
    try:
        return os.geteuid() == 0
    except AttributeError:
        try:
            return os.getuid() == 0
        except AttributeError:
            return False


def prompt_for_admin_immediately():
    if is_admin():
        return True

    print("This application requires root privileges to function properly.")

    if check_pkexec_available():
        print("Using pkexec for authentication...")
        try:
            result = subprocess.run(['pkexec', 'true'], capture_output=True, text=True)
            if result.returncode == 0:
                print("Admin privileges obtained successfully via pkexec.")
                return True
            else:
                print("pkexec authentication failed or was cancelled.")
                return False
        except Exception as e:
            print(f"Error with pkexec: {e}")

    if check_sudo_available():
        print("Falling back to sudo for authentication...")
        try:
            result = subprocess.run(['sudo', '-n', 'true'], capture_output=True, text=True)
            if result.returncode == 0:
                print("Admin privileges available via sudo.")
                return True
            else:
                print("Please enter your password when prompted...")
                result = subprocess.run(['sudo', '-v'], capture_output=True, text=True)
                if result.returncode == 0:
                    print("Admin privileges obtained successfully via sudo.")
                    return True
                else:
                    print("Failed to obtain admin privileges via sudo.")
                    return False
        except Exception as e:
            print(f"Error obtaining admin privileges via sudo: {e}")
            return False
    else:
        print("Error: Neither pkexec nor sudo is available on this system.")
        print("Please run the application as root manually.")
        return False


def ensure_root_privileges():
    if is_admin():
        return True
    return prompt_for_admin_immediately()


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


def run_command_as_admin_interactive(command, description="This operation"):
    """Run a command with admin privileges interactively using direct elevation.
    
    Note: This should only be used before the daemon is available (e.g., Qt dependency installation).
    For normal operations, use the daemon via GUI.app.utils.privileged.run_privileged_command instead.
    """
    if is_admin():
        return subprocess.run(command, text=True)

    if check_pkexec_available():
        try:
            pkexec_command = ['pkexec'] + command
            return subprocess.run(pkexec_command, text=True)
        except Exception as e:
            print(f"pkexec failed, falling back to sudo: {e}")

    if check_sudo_available():
        sudo_command = ['sudo'] + command
        return subprocess.run(sudo_command, text=True)
    else:
        raise Exception("Neither pkexec nor sudo is available for privilege escalation")


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


def prompt_for_elevation(operation_description="this operation"):
    print(f"\n{operation_description} requires root privileges.")
    print("The application will prompt for your password when needed.")
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


def run_as_admin() -> bool:
    """Attempt to re-launch the current application with root privileges.
    
    Behavior:
    - If already running as root: returns False immediately (no relaunch).
    - If elevation request succeeds: starts elevated instance and exits current process.
    - If elevation request fails (e.g., password denied): raises RuntimeError.
    
    Returns:
        False if already running as root, otherwise exits current process
        
    Raises:
        RuntimeError: If elevation request fails or no elevation method is available
    """
    if is_admin():
        return False
    
    # Get the script/executable path
    script = os.path.abspath(sys.argv[0])
    python_exe = sys.executable
    
    # Build command arguments - preserve all original arguments
    cmd_args = [python_exe, script] + sys.argv[1:]
    
    # Try pkexec first (preferred for GUI applications)
    if check_pkexec_available():
        try:
            # pkexec expects: pkexec <command> [args...]
            # We use Popen and don't wait, so the new process starts and we exit
            process = subprocess.Popen(
                ['pkexec'] + cmd_args,
                start_new_session=True
            )
            # Wait for authentication - give user time to enter password
            # Check periodically if process is still running (waiting for auth or started)
            # If process exits quickly (< 2 seconds), it likely failed
            # If process is still running after 2 seconds, assume auth is in progress or succeeded
            max_wait = 120  # 2 minutes max wait for authentication
            check_interval = 0.5
            waited = 0
            
            while waited < max_wait:
                time.sleep(check_interval)
                waited += check_interval
                
                poll_result = process.poll()
                if poll_result is None:
                    # Process is still running - either waiting for auth or app has started
                    # If we've waited at least 2 seconds, assume auth succeeded and app is starting
                    if waited >= 2.0:
                        # Give it a bit more time to actually start the app, then exit
                        time.sleep(1.0)
                        sys.exit(0)
                else:
                    # Process exited
                    # If it exited very quickly (< 1 second), it's likely an immediate failure
                    if waited < 1.0:
                        returncode = poll_result
                        # pkexec returns 126 for authentication failure, 127 for command not found
                        raise RuntimeError(f"pkexec authentication failed or was cancelled (return code: {returncode})")
                    # If it ran for a while then exited, might have started but crashed
                    # Or user cancelled after some time - treat as failure
                    returncode = poll_result
                    raise RuntimeError(f"pkexec process exited (return code: {returncode})")
            
            # Timeout - process still running but we've waited too long
            # This shouldn't happen, but if it does, assume it's working and exit
            logger.warning("pkexec authentication wait timed out, assuming success and exiting")
            sys.exit(0)
            
        except FileNotFoundError:
            # pkexec not found, fall through to sudo
            pass
        except Exception as e:
            # If it's already a RuntimeError, re-raise it
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"pkexec failed: {e}") from e
    
    # Fall back to sudo
    if check_sudo_available():
        try:
            # sudo expects: sudo <command> [args...]
            # We use Popen and don't wait, so the new process starts and we exit
            process = subprocess.Popen(
                ['sudo'] + cmd_args,
                start_new_session=True
            )
            # Wait for authentication - give user time to enter password
            # Same logic as pkexec
            max_wait = 120  # 2 minutes max wait for authentication
            check_interval = 0.5
            waited = 0
            
            while waited < max_wait:
                time.sleep(check_interval)
                waited += check_interval
                
                poll_result = process.poll()
                if poll_result is None:
                    # Process is still running - either waiting for auth or app has started
                    # If we've waited at least 2 seconds, assume auth succeeded and app is starting
                    if waited >= 2.0:
                        # Give it a bit more time to actually start the app, then exit
                        time.sleep(1.0)
                        sys.exit(0)
                else:
                    # Process exited
                    # If it exited very quickly (< 1 second), it's likely an immediate failure
                    if waited < 1.0:
                        returncode = poll_result
                        raise RuntimeError(f"sudo authentication failed or was cancelled (return code: {returncode})")
                    # If it ran for a while then exited, might have started but crashed
                    # Or user cancelled after some time - treat as failure
                    returncode = poll_result
                    raise RuntimeError(f"sudo process exited (return code: {returncode})")
            
            # Timeout - process still running but we've waited too long
            # This shouldn't happen, but if it does, assume it's working and exit
            logger.warning("sudo authentication wait timed out, assuming success and exiting")
            sys.exit(0)
            
        except FileNotFoundError:
            pass
        except Exception as e:
            # If it's already a RuntimeError, re-raise it
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"sudo failed: {e}") from e
    
    # No elevation method available
    raise RuntimeError("Neither pkexec nor sudo is available. Cannot restart with elevated privileges.")


def is_daemon_running(socket_path: Optional[str] = None) -> bool:
    """Check if daemon is running by checking socket existence."""
    if socket_path is None:
        from ..daemon.protocol import get_socket_path
        # Get UID from environment to determine correct socket path
        # When running normally (not via sudo/pkexec), get current user's UID directly
        uid_str = os.environ.get('SUDO_UID') or os.environ.get('PKEXEC_UID')
        if not uid_str:
            # Not running via sudo/pkexec, get current user's UID directly
            try:
                uid = os.getuid()
            except (AttributeError, OSError):
                uid = None
        else:
            uid = int(uid_str) if uid_str else None
        socket_path = get_socket_path(uid)
    if not os.path.exists(socket_path):
        return False
    
    # Try to connect to verify it's actually working
    try:
        import socket
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        sock.connect(socket_path)
        sock.close()
        return True
    except Exception:
        return False


def start_daemon(socket_path: Optional[str] = None) -> Optional[object]:
    """Start the privileged daemon process.
    
    Returns:
        DaemonClient instance if successful, None otherwise
    """
    global _daemon_process
    
    if socket_path is None:
        from ..daemon.protocol import get_socket_path
        # Get UID from environment to determine correct socket path
        # When running normally (not via sudo/pkexec), get current user's UID directly
        uid_str = os.environ.get('SUDO_UID') or os.environ.get('PKEXEC_UID')
        if not uid_str:
            # Not running via sudo/pkexec, get current user's UID directly
            try:
                uid = os.getuid()
            except (AttributeError, OSError):
                uid = None
        else:
            uid = int(uid_str) if uid_str else None
        socket_path = get_socket_path(uid)
        logger.info(f"Determined socket path: {socket_path} (UID: {uid})")
    
    # Check if already running
    if is_daemon_running(socket_path):
        logger.info("Daemon already running")
        from ..daemon.client import DaemonClient
        client = DaemonClient(socket_path)
        if client.connect():
            return client
        logger.warning("Socket exists but connection failed, cleaning up...")
    
    # Get path to current executable
    # Find the main script path
    if hasattr(sys, 'frozen') and sys.frozen:
        # PyInstaller bundle - executable is the script
        exe_path = sys.executable
        daemon_cmd = [exe_path, '--daemon']
    else:
        # Development mode - need to run python with the script
        exe_path = sys.executable  # python executable
        
        # Try to find the main script dynamically
        script_path = None
        
        # First, try sys.argv[0] (the script that was invoked)
        if sys.argv and sys.argv[0] and sys.argv[0] != '-c':
            potential_path = Path(sys.argv[0])
            if potential_path.is_absolute() and potential_path.exists():
                script_path = potential_path
            elif (Path.cwd() / potential_path).exists():
                script_path = Path.cwd() / potential_path
            elif potential_path.exists():
                script_path = potential_path.resolve()
        
        # If that didn't work, try to find __main__.__file__
        if script_path is None or not script_path.exists():
            try:
                import __main__
                if hasattr(__main__, '__file__') and __main__.__file__:
                    main_file = Path(__main__.__file__)
                    if main_file.exists():
                        script_path = main_file
            except Exception:
                pass
        
        # If still not found, try to find the app.py entry point
        if script_path is None or not script_path.exists():
            # Look for app.py which contains the run() function
            app_py = Path(__file__).parent.parent / 'app' / 'app.py'
            if app_py.exists():
                # Find the root script that imports from the GUI module
                # Check common locations relative to app.py
                root_dir = app_py.parent.parent.parent
                gui_pkg = app_py.parent.parent.name
                # Look for any .py file in root that might be the entry point
                for py_file in root_dir.glob('*.py'):
                    try:
                        # Quick check: does it import from the gui package app.app?
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
        daemon_cmd = [exe_path, str(script_path), '--daemon']
    
    # Get UID/GID before starting daemon (needed for socket path and permissions)
    # When running normally (not via sudo/pkexec), we need to get current user's UID
    uid_str = os.environ.get('SUDO_UID') or os.environ.get('PKEXEC_UID')
    if not uid_str:
        # Not running via sudo/pkexec, get current user's UID directly
        try:
            original_uid = os.getuid()
            original_gid = os.getgid()
            logger.info(f"Running as normal user, UID: {original_uid}, GID: {original_gid}")
        except (AttributeError, OSError):
            original_uid = None
            original_gid = None
    else:
        original_uid = int(uid_str) if uid_str else None
        gid_str = os.environ.get('SUDO_GID') or os.environ.get('PKEXEC_GID')
        original_gid = int(gid_str) if gid_str else None
        logger.info(f"Running via elevation, original UID: {original_uid}, GID: {original_gid}")
    
    # Pass UID/GID as command-line arguments (pkexec doesn't preserve env vars)
    if original_uid is not None:
        daemon_cmd.extend(['--uid', str(original_uid)])
        logger.info(f"Passing --uid {original_uid} to daemon")
    if original_gid is not None:
        daemon_cmd.extend(['--gid', str(original_gid)])
        logger.info(f"Passing --gid {original_gid} to daemon")
    
    # Prepare environment (still pass it, but UID/GID are in command line as backup)
    daemon_env = os.environ.copy()
    if original_uid is not None:
        daemon_env['PKEXEC_UID'] = str(original_uid)
        daemon_env['SUDO_UID'] = str(original_uid)
    if original_gid is not None:
        daemon_env['PKEXEC_GID'] = str(original_gid)
        daemon_env['SUDO_GID'] = str(original_gid)
    
    # Try pkexec first, then sudo
    if check_pkexec_available():
        logger.info("Starting daemon with pkexec...")
        try:
            # Capture stderr to see daemon startup errors
            # stdout can stay uncaptured for pkexec GUI prompt if needed
            # Pass environment variables so daemon can determine socket path
            process = subprocess.Popen(
                ['pkexec'] + daemon_cmd,
                env=daemon_env,
                stderr=subprocess.PIPE,
                start_new_session=True  # Detach from parent
            )
            _daemon_process = process
            logger.info(f"Daemon process started with PID {process.pid}")
            
            # Monitor daemon stderr in background to catch errors
            import threading
            def check_daemon_stderr_periodically():
                """Periodically check daemon stderr for errors."""
                if not process.stderr:
                    return
                try:
                    # Wait a bit, then check if process exited
                    time.sleep(2)
                    if process.poll() is not None:
                        # Process exited, read stderr
                        try:
                            stderr_data = process.stderr.read().decode('utf-8', errors='ignore')
                            if stderr_data:
                                logger.error(f"Daemon exited with stderr: {stderr_data}")
                        except Exception:
                            pass
                except Exception as e:
                    logger.debug(f"Error checking daemon stderr: {e}")
            
            threading.Thread(target=check_daemon_stderr_periodically, daemon=True).start()
            
        except Exception as e:
            logger.error(f"Failed to start daemon with pkexec: {e}")
            return None
    
    elif check_sudo_available():
        logger.info("Starting daemon with sudo...")
        try:
            # Don't capture stdout/stderr so password prompt can display
            # Pass environment variables so daemon can determine socket path
            # Use -E flag to preserve environment, or explicitly pass env
            process = subprocess.Popen(
                ['sudo', '-E'] + daemon_cmd,
                env=daemon_env,
                start_new_session=True  # Detach from parent
            )
            _daemon_process = process
        except Exception as e:
            logger.error(f"Failed to start daemon with sudo: {e}")
            return None
    
    else:
        logger.error("Neither pkexec nor sudo available")
        return None
    
    # Wait for daemon to start (socket to appear)
    # Use longer timeout for interactive prompts (pkexec/sudo) - users may take time to enter password
    # For interactive elevation, allow up to 5 minutes (600 iterations * 0.5s)
    # For non-interactive, use shorter timeout
    using_interactive = check_pkexec_available() or check_sudo_available()
    max_wait = 600 if using_interactive else 20  # 5 minutes for interactive, 10 seconds for non-interactive
    check_interval = 0.5
    
    logger.info(f"Waiting for daemon to start... (checking socket at: {socket_path})")
    logger.info(f"Daemon process PID: {_daemon_process.pid if _daemon_process else None}")
    
    for i in range(max_wait):
        time.sleep(check_interval)
        
        # Periodically check if process is still running (every 2 seconds)
        if i > 0 and i % 4 == 0:
            if _daemon_process:
                is_running = _daemon_process.poll() is None
                logger.debug(f"Daemon process status: {'running' if is_running else 'exited'}")
        
        # Check if process is still alive
        if _daemon_process and _daemon_process.poll() is not None:
            # Process exited, check return code and read stderr
            returncode = _daemon_process.returncode
            logger.error(f"Daemon process exited with return code {returncode}")
            
            # Try to read stderr for error messages
            if _daemon_process.stderr:
                try:
                    stderr_data = _daemon_process.stderr.read().decode('utf-8', errors='ignore')
                    if stderr_data:
                        logger.error(f"Daemon stderr output: {stderr_data}")
                except Exception:
                    pass
            
            _daemon_process = None
            return None
        
        # Check if socket appeared (daemon started)
        if is_daemon_running(socket_path):
            logger.info(f"Daemon started successfully, socket found at: {socket_path}")
            from ..daemon.client import DaemonClient
            client = DaemonClient(socket_path)
            if client.connect():
                logger.info("Successfully connected to daemon")
                return client
            else:
                logger.warning("Socket exists but connection failed, continuing to wait...")
        
        # Log progress every 10 seconds
        if i > 0 and i % 20 == 0:
            elapsed = i * check_interval
            logger.debug(f"Still waiting for daemon... ({elapsed:.1f}s elapsed, process running: {_daemon_process.poll() is None if _daemon_process else False})")
        
        # Process still running but socket not ready yet - continue waiting
        # (user might be entering password in pkexec/sudo prompt)
    
    # Timeout reached - check final status
    if _daemon_process and _daemon_process.poll() is None:
        # Process is still running (likely waiting for password or starting up)
        logger.warning(f"Daemon process still running (PID {_daemon_process.pid}) but socket not accessible after {max_wait * check_interval:.1f} seconds")
        logger.warning("If you see a password prompt, please enter your password. The daemon will start once authenticated.")
        # Don't kill the process - let it continue, user might still be entering password
        # The process will continue in background and socket may appear later
        return None
    else:
        logger.error("Daemon failed to start within timeout")
        if _daemon_process:
            returncode = _daemon_process.poll()
            if returncode is not None:
                logger.error(f"Daemon process exited with return code {returncode}")
    
    # Only cleanup if process has exited
    if _daemon_process and _daemon_process.poll() is not None:
        try:
            _daemon_process.terminate()
            _daemon_process.wait(timeout=DAEMON_SHUTDOWN_TIMEOUT)
        except Exception:
            try:
                _daemon_process.kill()
            except Exception:
                pass
        _daemon_process = None
    return None


def stop_daemon(socket_path: Optional[str] = None):
    """Stop the daemon by sending shutdown request."""
    if socket_path is None:
        from ..daemon.protocol import get_socket_path
        # Get UID from environment to determine correct socket path
        # When running normally (not via sudo/pkexec), get current user's UID directly
        uid_str = os.environ.get('SUDO_UID') or os.environ.get('PKEXEC_UID')
        if not uid_str:
            # Not running via sudo/pkexec, get current user's UID directly
            try:
                uid = os.getuid()
            except (AttributeError, OSError):
                uid = None
        else:
            uid = int(uid_str) if uid_str else None
        socket_path = get_socket_path(uid)
    if not is_daemon_running(socket_path):
        logger.info("Daemon not running")
        return
    
    try:
        from ..daemon.client import DaemonClient
        client = DaemonClient(socket_path)
        if client.connect():
            logger.info("Sending shutdown request to daemon...")
            client.request('shutdown', {})
            client.disconnect()
            logger.info("Daemon shutdown requested")
        
        # Wait a bit for daemon to exit
        time.sleep(0.5)
        
        # Clean up process reference
        global _daemon_process
        if _daemon_process:
            try:
                _daemon_process.wait(timeout=DAEMON_QUICK_TIMEOUT)
            except:
                pass
            _daemon_process = None
        
    except Exception as e:
        logger.error(f"Error stopping daemon: {e}")
    
    # Clean up socket file if it still exists
    if os.path.exists(socket_path):
        try:
            os.unlink(socket_path)
        except Exception:
            pass


__all__ = ['is_admin', 'run_command_as_admin', 'get_sudo_status', 'start_daemon', 'stop_daemon']
