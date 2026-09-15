"""Helper module for running privileged commands via daemon.

This module provides functions to execute commands, read files, and write files
with root privileges using the privileged daemon on Linux systems.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from typing import Callable, List, Optional, Union

from ..daemon.client import StreamRequestHandle

logger = logging.getLogger(__name__)


@dataclass
class PrivilegedStreamResult:
    """Result of a streaming privileged command."""

    completed: subprocess.CompletedProcess
    request_id: Optional[str] = None


def _format_command(command: Union[str, List[str]]) -> str:
    if isinstance(command, str):
        return command
    return " ".join(str(part) for part in command)


def _dev_log_daemon(message: str) -> None:
    """Log daemon traffic in runtime dev mode only (production stays quiet)."""
    try:
        from .admin import is_dev_mode

        if is_dev_mode():
            logger.info(message)
    except Exception:
        pass


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

        cmd_display = _format_command(cmd_to_send)
        _dev_log_daemon(f"[daemon] run_command: {cmd_display}")
        
        response = daemon.request('run_command', {
            'command': cmd_to_send,
            'timeout': timeout_for_request
        }, timeout=timeout_for_request)
        
        # Response has structure: {'id': ..., 'success': bool, 'result': {...}, 'error': ...}
        if not response.get('success', False):
            error_msg = str(response.get('error', 'Unknown error'))
            result = response.get('result', {})
            stderr_msg = str(result.get('stderr', '')) or error_msg
            _dev_log_daemon(
                f"[daemon] run_command failed rc={result.get('returncode', -1)}: {cmd_display}"
            )
            raise subprocess.CalledProcessError(
                result.get('returncode', -1),
                command,
                str(result.get('stdout', '')),
                stderr_msg
            )
        
        # Extract result from response
        result = response.get('result', {})
        rc = result.get('returncode', 0)
        _dev_log_daemon(f"[daemon] run_command finished rc={rc}: {cmd_display}")
        
        return subprocess.CompletedProcess(
            command,
            rc,
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


def run_privileged_command_stream(
    command: Union[str, List[str]],
    on_chunk: Callable[[str], None],
    timeout: int = 300,
    on_started: Optional[Callable[[StreamRequestHandle], None]] = None,
) -> PrivilegedStreamResult:
    """Run a privileged command and stream stdout lines via ``on_chunk``.

    Args:
        command: Command list or shell string.
        on_chunk: Called for each output line as it arrives.
        timeout: Idle timeout in seconds (resets on each chunk). ``None`` uses
            the daemon client default.
        on_started: Optional callback receiving a :class:`StreamRequestHandle`
            so the caller can cancel via :func:`cancel_privileged_request`.

    Returns:
        :class:`PrivilegedStreamResult` with the completed process and request id.

    Raises:
        RuntimeError: If the daemon is unavailable.
        subprocess.CalledProcessError: If the daemon reports failure without a result.
    """
    try:
        from ..daemon import get_daemon_client

        daemon = get_daemon_client()

        if isinstance(command, str):
            cmd_to_send = ['sh', '-c', command]
        else:
            cmd_to_send = command

        if timeout is None:
            timeout_for_request = None
        else:
            timeout_for_request = int(timeout) if timeout else 300

        handle_box: dict[str, Optional[StreamRequestHandle]] = {'handle': None}
        cmd_display = _format_command(cmd_to_send)
        _dev_log_daemon(f"[daemon] run_command_stream: {cmd_display}")

        def _on_started(handle: StreamRequestHandle) -> None:
            handle_box['handle'] = handle
            _dev_log_daemon(
                f"[daemon] run_command_stream started id={handle.request_id}: {cmd_display}"
            )
            if on_started is not None:
                on_started(handle)

        response = daemon.request_stream(
            'run_command_stream',
            {
                'command': cmd_to_send,
                'timeout': timeout_for_request,
            },
            on_chunk=on_chunk,
            timeout=timeout_for_request,
            on_started=_on_started,
        )

        request_id = None
        if handle_box['handle'] is not None:
            request_id = handle_box['handle'].request_id
        elif response.get('id'):
            request_id = str(response['id'])

        if not response.get('success', False):
            error_msg = str(response.get('error', 'Unknown error'))
            result = response.get('result', {}) or {}
            stderr_msg = str(result.get('stderr', '')) or error_msg
            _dev_log_daemon(
                f"[daemon] run_command_stream failed rc={result.get('returncode', -1)}: {cmd_display}"
            )
            raise subprocess.CalledProcessError(
                result.get('returncode', -1),
                command,
                str(result.get('stdout', '')),
                stderr_msg,
            )

        result = response.get('result', {}) or {}
        rc = result.get('returncode', 0)
        _dev_log_daemon(f"[daemon] run_command_stream finished rc={rc}: {cmd_display}")
        completed = subprocess.CompletedProcess(
            command,
            rc,
            str(result.get('stdout', '')),
            str(result.get('stderr', '')),
        )
        return PrivilegedStreamResult(completed=completed, request_id=request_id)

    except RuntimeError as e:
        logger.error(f"Daemon not available ({e}). Privileged operations are disabled.")
        raise RuntimeError(
            "Privileged operations require daemon. Start application with admin privileges to enable."
        ) from e
    except Exception as e:
        logger.error(f"Error running privileged stream command: {e}", exc_info=True)
        raise


def cancel_privileged_request(target_id: str, timeout: float = 5.0) -> bool:
    """Cancel a running privileged streaming request by id.

    Returns:
        True if the daemon reported the job as cancelled.
    """
    if not target_id:
        return False
    try:
        from ..daemon import get_daemon_client

        daemon = get_daemon_client()
        _dev_log_daemon(f"[daemon] cancel: {target_id}")
        response = daemon.cancel_request(target_id, timeout=timeout)
        if not response.get('success', False):
            _dev_log_daemon(f"[daemon] cancel failed: {target_id}")
            return False
        result = response.get('result', {}) or {}
        cancelled = bool(result.get('cancelled'))
        _dev_log_daemon(f"[daemon] cancel result cancelled={cancelled}: {target_id}")
        return cancelled
    except Exception as e:
        logger.error(f"Error cancelling privileged request {target_id}: {e}", exc_info=True)
        return False


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

        # Write to temp file in default temp dir (e.g. /tmp) to avoid PermissionError
        with tempfile.NamedTemporaryFile(
            mode="w",
            delete=False,
            encoding="utf-8"
        ) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            # Atomic replace via daemon
            result = run_privileged_command(["mv", tmp_path, file_path], timeout=30)
            if result.returncode != 0:
                raise IOError(f"Failed to write {file_path}: {result.stderr}")

            # Restore permissions and ownership if we had them, otherwise default to root:root for new files
            run_privileged_command(["chmod", mode, file_path], timeout=10)
            if owner is not None and group is not None:
                run_privileged_command(["chown", f"{owner}:{group}", file_path], timeout=10)
            else:
                try:
                    run_privileged_command(["chown", "root:root", file_path], timeout=10)
                except Exception:
                    pass

            return True
        finally:
            # Clean up temp file if still present
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
                
    except Exception as e:
        logger.error(f"Error writing privileged file {file_path}: {e}")
        return False


__all__ = [
    'run_privileged_command',
    'run_privileged_command_stream',
    'cancel_privileged_request',
    'PrivilegedStreamResult',
    'read_privileged_file',
    'write_privileged_file',
]
