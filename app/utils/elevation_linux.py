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


def is_daemon_running(socket_path: str = '/tmp/cyberpatriot-daemon.sock') -> bool:
    """Check if daemon is running by checking socket existence."""
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


def start_daemon(socket_path: str = '/tmp/cyberpatriot-daemon.sock') -> Optional[object]:
    """Start the privileged daemon process.
    
    Returns:
        DaemonClient instance if successful, None otherwise
    """
    global _daemon_process
    
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
            # Find cyberpatriot.py in the current directory or parent
            script_path = Path.cwd() / 'cyberpatriot.py'
            if not script_path.exists():
                # Try parent directory
                script_path = Path.cwd().parent / 'cyberpatriot.py'
            if not script_path.exists():
                # Fallback: use current directory as script
                script_path = Path(__file__).parent.parent.parent / 'cyberpatriot.py'
            
            logger.info(f"Daemon script path: {script_path}")
            daemon_cmd = [exe_path, str(script_path), '--daemon']
    
    # Try pkexec first, then sudo
    if check_pkexec_available():
        logger.info("Starting daemon with pkexec...")
        try:
            # Capture stderr to see daemon startup errors
            # stdout can stay uncaptured for pkexec GUI prompt if needed
            process = subprocess.Popen(
                ['pkexec'] + daemon_cmd,
                stderr=subprocess.PIPE,
                start_new_session=True  # Detach from parent
            )
            _daemon_process = process
            logger.info(f"Daemon process started with PID {process.pid}")
            
            # Wait a moment and check for immediate errors
            import threading
            def check_daemon_stderr():
                time.sleep(1)  # Give daemon a moment to start
                if process.stderr and process.poll() is not None:
                    # Process already exited, read stderr
                    try:
                        stderr_data = process.stderr.read().decode('utf-8', errors='ignore')
                        if stderr_data:
                            logger.error(f"Daemon stderr output: {stderr_data}")
                    except Exception:
                        pass
            
            threading.Thread(target=check_daemon_stderr, daemon=True).start()
            
        except Exception as e:
            logger.error(f"Failed to start daemon with pkexec: {e}")
            return None
    
    elif check_sudo_available():
        logger.info("Starting daemon with sudo...")
        try:
            # Don't capture stdout/stderr so password prompt can display
            process = subprocess.Popen(
                ['sudo'] + daemon_cmd,
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
    logger.info("Waiting for daemon to start...")
    max_wait = 10
    for i in range(max_wait):
        time.sleep(0.5)
        
        # Check if process is still alive
        if _daemon_process and _daemon_process.poll() is not None:
            # Process exited, check return code
            returncode = _daemon_process.returncode
            logger.error(f"Daemon process exited with return code {returncode}")
            _daemon_process = None
            return None
        
        if is_daemon_running(socket_path):
            logger.info("Daemon started successfully")
            from ..daemon.client import DaemonClient
            client = DaemonClient(socket_path)
            if client.connect():
                return client
    
    logger.error("Daemon failed to start within timeout")
    
    # Check process status one more time
    if _daemon_process:
        returncode = _daemon_process.poll()
        if returncode is not None:
            logger.error(f"Daemon process exited with return code {returncode}")
        else:
            logger.warning(f"Daemon process still running (PID {_daemon_process.pid}) but socket not accessible")
    
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
    return None


def stop_daemon(socket_path: str = '/tmp/cyberpatriot-daemon.sock'):
    """Stop the daemon by sending shutdown request."""
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


