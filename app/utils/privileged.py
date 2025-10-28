"""Helper module for running privileged commands via daemon."""

import subprocess
import logging

logger = logging.getLogger(__name__)


def run_privileged_command(command, timeout=300):
    """Run a command with root privileges via daemon.
    
    Args:
        command: List of command and arguments (e.g., ['systemctl', 'stop', 'apache2'])
                 or string for shell commands
        timeout: Timeout in seconds (default 300)
    
    Returns:
        subprocess.CompletedProcess instance
        
    Raises:
        subprocess.CalledProcessError: If command fails
        RuntimeError: If daemon is not available
    """
    try:
        from ..daemon import get_daemon_client
        
        daemon = get_daemon_client()
        
        # Convert string commands to list for daemon (use shell=True when executing)
        if isinstance(command, str):
            # For shell commands, we need to pass as a list with shell=True somehow
            # The daemon expects a list, so for now we'll send as ['sh', '-c', command]
            cmd_to_send = ['sh', '-c', command]
        else:
            cmd_to_send = command
        
        response = daemon.request('run_command', {
            'command': cmd_to_send,
            'timeout': timeout
        })
        
        # Response has structure: {'id': ..., 'success': bool, 'result': {...}, 'error': ...}
        if not response.get('success', False):
            error_msg = response.get('error', 'Unknown error')
            result = response.get('result', {})
            raise subprocess.CalledProcessError(
                result.get('returncode', -1),
                command,
                result.get('stdout', ''),
                result.get('stderr', error_msg)
            )
        
        # Extract result from response
        result = response.get('result', {})
        
        return subprocess.CompletedProcess(
            command,
            result.get('returncode', 0),
            result.get('stdout', ''),
            result.get('stderr', '')
        )
        
    except RuntimeError as e:
        # Daemon not initialized
        logger.warning(f"Daemon not available ({e}), falling back to direct subprocess")
        # Fallback for backwards compatibility in development
        if isinstance(command, str):
            return subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
        return subprocess.run(command, capture_output=True, text=True, check=True, timeout=timeout)
    except Exception as e:
        logger.error(f"Error running privileged command: {e}")
        raise
