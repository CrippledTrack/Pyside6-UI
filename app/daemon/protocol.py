"""Protocol definitions for daemon communication."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Dict, Any, Optional


def create_request(operation: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Create a request message."""
    return {
        'id': str(uuid.uuid4()),
        'operation': operation,
        'params': params
    }


def create_response(request_id: str, success: bool, 
                   result: Any = None, error: Optional[str] = None) -> Dict[str, Any]:
    """Create a response message."""
    response = {
        'id': request_id,
        'success': success
    }
    
    if success:
        if result is not None:
            response['result'] = result
    else:
        response['error'] = error or 'Unknown error'
    
    return response


def serialize_message(message: Dict[str, Any]) -> bytes:
    """Serialize a message to bytes."""
    return json.dumps(message).encode('utf-8') + b'\n'


def deserialize_message(data: bytes) -> Dict[str, Any]:
    """Deserialize bytes to a message."""
    return json.loads(data.decode('utf-8').strip())


# Operation types
OPERATION_RUN_COMMAND = 'run_command'
OPERATION_RUN_COMMAND_STREAM = 'run_command_stream'
OPERATION_CANCEL = 'cancel'
OPERATION_SHUTDOWN = 'shutdown'


def create_stream_chunk(request_id: str, chunk: str) -> Dict[str, Any]:
    """Create a streaming progress chunk response.
    
    These intermediate responses are sent during a run_command_stream operation
    for each line of output produced by the subprocess. The final response is
    sent via create_response() once the subprocess completes.
    
    Args:
        request_id: The ID of the originating request.
        chunk: A line of subprocess output.
    
    Returns:
        A dict representing the streaming chunk message.
    """
    return {
        'id': request_id,
        'success': True,
        'status': 'running',
        'chunk': chunk
    }


def get_socket_path(uid: Optional[int] = None) -> str:
    """
    Get a secure socket path in a user-specific directory.
    
    Tries, in order:
    1. /run/user/<uid>/ (systemd user runtime directory - most secure)
    2. ~/.local/run/ (user-specific runtime directory, requires uid to get home)
    3. /tmp/ (fallback, less secure but always available)
    
    Args:
        uid: User ID to use for path determination. If None, tries to get from environment.
    
    Returns:
        Path to socket file
    """
    # Try to get original user's UID
    if uid is None:
        uid_str = os.environ.get('SUDO_UID') or os.environ.get('PKEXEC_UID')
        if uid_str:
            try:
                uid = int(uid_str)
            except ValueError:
                uid = None
    
    if uid is not None:
        try:
            # Try systemd user runtime directory first (most secure)
            systemd_runtime = Path(f'/run/user/{uid}')
            if systemd_runtime.exists() and systemd_runtime.is_dir():
                socket_dir = systemd_runtime / 'privileged-daemon'
                try:
                    socket_dir.mkdir(mode=0o700, exist_ok=True)
                    return str(socket_dir / 'daemon.sock')
                except OSError as e:
                    # Directory might exist but we can't create it - try anyway
                    if socket_dir.exists():
                        return str(socket_dir / 'daemon.sock')
                    raise
        except OSError as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Could not use systemd runtime directory: {e}")
            pass
        
        # Fallback: use user's home directory (need to get home from uid)
        try:
            import pwd
            user_info = pwd.getpwuid(uid)
            home = Path(user_info.pw_dir)
            runtime_dir = home / '.local' / 'run' / 'privileged-daemon'
            try:
                runtime_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
                return str(runtime_dir / 'daemon.sock')
            except OSError as e:
                # Directory might exist but we can't create it - try anyway
                if runtime_dir.exists():
                    return str(runtime_dir / 'daemon.sock')
                raise
        except (OSError, KeyError, ImportError) as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Could not use home directory: {e}")
            pass
    
    # Last resort: /tmp (less secure but always available)
    return '/tmp/privileged-daemon/daemon.sock'


# Default socket path (will be overridden at runtime with proper uid)
# This is just for backwards compatibility - actual path is determined at daemon startup
SOCKET_PATH = '/tmp/privileged-daemon/daemon.sock'


__all__ = [
    'create_request',
    'create_response',
    'create_stream_chunk',
    'serialize_message',
    'deserialize_message',
    'OPERATION_RUN_COMMAND',
    'OPERATION_RUN_COMMAND_STREAM',
    'OPERATION_CANCEL',
    'OPERATION_SHUTDOWN',
    'SOCKET_PATH',
    'get_socket_path',
]
