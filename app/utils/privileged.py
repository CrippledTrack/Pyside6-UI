"""Helper module for running privileged commands via daemon.

This module provides functions to execute commands, read files, and write files
with root privileges using the privileged daemon on Linux systems.
"""

from __future__ import annotations

import logging
import subprocess
from typing import List, Union

logger = logging.getLogger(__name__)


def run_privileged_command(command: Union[str, List[str]], timeout: int = 300):
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
        
        # Convert string commands to list for daemon
        if isinstance(command, str):
            cmd_to_send = ['sh', '-c', command]
        else:
            cmd_to_send = command
        
        # Handle timeout: None means no timeout, otherwise convert to int
        if timeout is None:
            timeout_for_request = None
        else:
            timeout_for_request = int(timeout) if timeout else 300
        
        response = daemon.request('run_command', {
            'command': cmd_to_send,
            'timeout': timeout_for_request
        }, timeout=timeout_for_request)
        
        # Response has structure: {'id': ..., 'success': bool, 'result': {...}, 'error': ...}
        if not response.get('success', False):
            error_msg = str(response.get('error', 'Unknown error'))
            result = response.get('result', {})
            stderr_msg = str(result.get('stderr', '')) or error_msg
            raise subprocess.CalledProcessError(
                result.get('returncode', -1),
                command,
                str(result.get('stdout', '')),
                stderr_msg
            )
        
        # Extract result from response
        result = response.get('result', {})
        
        return subprocess.CompletedProcess(
            command,
            result.get('returncode', 0),
            str(result.get('stdout', '')),
            str(result.get('stderr', ''))
        )
        
    except RuntimeError as e:
        # Daemon not initialized - raise error instead of falling back
        # This allows calling code to handle the missing daemon gracefully
        logger.error(f"Daemon not available ({e}). Privileged operations are disabled.")
        raise RuntimeError("Privileged operations require daemon. Start application with admin privileges to enable.") from e
    except Exception as e:
        logger.error(f"Error running privileged command: {str(e)}", exc_info=True)
        raise


def read_privileged_file(file_path: str) -> str:
    """Read content from a file with root privileges via daemon.
    
    Args:
        file_path: Path to file to read
        
    Returns:
        File content as string
    """
    try:
        result = run_privileged_command(['cat', file_path], timeout=30)
        if result.returncode == 0:
            return result.stdout
        else:
            raise IOError(f"Failed to read {file_path}: {result.stderr}")
    except Exception as e:
        logger.error(f"Error reading privileged file {file_path}: {e}")
        raise


def write_privileged_file(file_path: str, content: str) -> bool:
    """Write content to a file with root privileges via daemon.
    
    Args:
        file_path: Path to file to write
        content: Content to write to file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        import tempfile
        import os
        target_dir = os.path.dirname(file_path) or "."

        # Determine existing permissions/ownership if the file exists
        mode = "644"
        owner = None
        group = None
        try:
            stat_result = run_privileged_command(
                ["stat", "-c", "%a %u %g", file_path],
                timeout=10
            )
            if stat_result.returncode == 0 and stat_result.stdout:
                parts = stat_result.stdout.strip().split()
                if len(parts) == 3:
                    mode, owner, group = parts
        except Exception:
            pass

        # Write to temp file in the target directory for atomic replace
        with tempfile.NamedTemporaryFile(
            mode="w",
            delete=False,
            encoding="utf-8",
            dir=target_dir
        ) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            # Atomic replace via daemon
            result = run_privileged_command(["mv", tmp_path, file_path], timeout=30)
            if result.returncode != 0:
                raise IOError(f"Failed to write {file_path}: {result.stderr}")

            # Restore permissions and ownership if we had them
            run_privileged_command(["chmod", mode, file_path], timeout=10)
            if owner is not None and group is not None:
                run_privileged_command(["chown", f"{owner}:{group}", file_path], timeout=10)

            return True
        finally:
            # Clean up temp file if still present
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
                
    except Exception as e:
        logger.error(f"Error writing privileged file {file_path}: {e}")
        return False


__all__ = ['run_privileged_command', 'read_privileged_file', 'write_privileged_file']