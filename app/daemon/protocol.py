"""Protocol definitions for daemon communication."""

from __future__ import annotations

import json
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
OPERATION_SHUTDOWN = 'shutdown'

# Socket path for daemon communication
SOCKET_PATH = '/tmp/privileged-daemon.sock'


__all__ = [
    'create_request',
    'create_response',
    'serialize_message',
    'deserialize_message',
    'OPERATION_RUN_COMMAND',
    'OPERATION_SHUTDOWN',
    'SOCKET_PATH',
]
