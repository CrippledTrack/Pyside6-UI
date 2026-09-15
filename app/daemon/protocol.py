"""Protocol definitions for daemon communication."""

from __future__ import annotations

import json
import os
import uuid
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


def get_effective_uid_gid() -> tuple[Optional[int], Optional[int]]:
    """
    Get the original user's UID and GID, falling back to os.getuid()/os.getgid().

    This handles environments where the app has been elevated via sudo or pkexec.
    """
    uid_str = os.environ.get('SUDO_UID') or os.environ.get('PKEXEC_UID')
    gid_str = os.environ.get('SUDO_GID') or os.environ.get('PKEXEC_GID')

    uid = None
    gid = None

    if uid_str:
        try:
            uid = int(uid_str)
        except ValueError:
            pass
    if gid_str:
        try:
            gid = int(gid_str)
        except ValueError:
            pass

    if uid is None:
        try:
            uid = os.getuid()
        except (AttributeError, OSError):
            pass
    if gid is None:
        try:
            gid = os.getgid()
        except (AttributeError, OSError):
            pass

    return uid, gid


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
    'get_effective_uid_gid',
]
