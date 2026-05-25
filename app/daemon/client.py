"""Daemon client for communicating with privileged daemon."""

from __future__ import annotations

import socket
import logging
import threading
import time
import subprocess
from typing import Dict, Any, Optional
from .protocol import create_request, serialize_message, deserialize_message, get_socket_path

logger = logging.getLogger(__name__)


class DaemonConnectionError(Exception):
    """Raised when daemon connection fails."""
    pass


class DaemonTimeoutError(Exception):
    """Raised when daemon operation times out."""
    pass


class DaemonClient:
    """Client for communicating with privileged daemon."""
    
    CONNECT_TIMEOUT = 5.0
    OPERATION_TIMEOUT = 30.0
    RECONNECT_RETRIES = 3
    RECONNECT_DELAY = 1.0
    
    def __init__(self, socket_path: Optional[str] = None, process: Optional[subprocess.Popen] = None):
        self._process = process
        self._lock = threading.Lock()
        
        # =====================================================================
        # Pipe Mode Setup
        # =====================================================================
        if self._process is not None:
            self.socket_path = None
            self._connected = True
        # =====================================================================
        # Legacy Socket Mode Setup (To be removed after 5.x)
        # =====================================================================
        else:
            if socket_path is None:
                # Get UID from environment to determine correct socket path
                # When running normally (not via sudo/pkexec), get current user's UID directly
                import os
                uid_str = os.environ.get('SUDO_UID') or os.environ.get('PKEXEC_UID')
                if not uid_str:
                    # Not running via sudo/pkexec, get current user's UID directly
                    try:
                        uid = os.getuid()
                    except (AttributeError, OSError):
                        uid = None
                else:
                    uid = int(uid_str) if uid_str else None
                self.socket_path = get_socket_path(uid)
            else:
                self.socket_path = socket_path
            self._socket: Optional[socket.socket] = None
            self._connected = False
    
    def is_connected(self) -> bool:
        """Check if client is connected to daemon."""
        if self._process is not None:
            return self._connected and self._process.poll() is None
        return self._connected and self._socket is not None
    
    def connect(self, timeout: float = None) -> bool:
        """Connect to daemon."""
        if self._process is not None:
            with self._lock:
                self._connected = self._process.poll() is None
                return self._connected
        
        timeout = timeout or self.CONNECT_TIMEOUT
        
        with self._lock:
            if self._connected:
                return True
            
            try:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                sock.connect(self.socket_path)
                
                self._socket = sock
                self._connected = True
                logger.info(f"Connected to daemon at {self.socket_path}")
                return True
                
            except (socket.error, OSError) as e:
                logger.error(f"Failed to connect to daemon: {e}")
                if self._socket:
                    try:
                        self._socket.close()
                    except Exception:
                        pass
                self._socket = None
                self._connected = False
                return False
    
    def disconnect(self):
        """Disconnect from daemon."""
        with self._lock:
            if self._process is not None:
                if self._process.poll() is None:
                    try:
                        self._process.terminate()
                        self._process.wait(timeout=2.0)
                    except Exception:
                        try:
                            self._process.kill()
                        except Exception:
                            pass
                self._connected = False
                logger.info("Disconnected from pipe daemon")
                return
            
            if self._socket:
                try:
                    self._socket.close()
                except Exception:
                    pass
                self._socket = None
            self._connected = False
            logger.info("Disconnected from daemon")
    
    def _send_recv(self, message: bytes, expected_id: Optional[str] = None, timeout: float = None) -> Dict[str, Any]:
        """Send message and receive response."""
        # If timeout is None, use a very large timeout (effectively unlimited)
        # Socket timeout of None blocks indefinitely, which we want for long operations
        if timeout is not None:
            timeout = timeout or self.OPERATION_TIMEOUT
        
        if not self.is_connected():
            raise DaemonConnectionError("Not connected to daemon")
        
        with self._lock:
            # =================================================================
            # Pipe Mode Send/Receive
            # =================================================================
            if self._process is not None:
                try:
                    # Write message to stdin
                    self._process.stdin.write(message)
                    self._process.stdin.flush()
                    
                    start_time = time.time()
                    while True:
                        # Wait for response with timeout
                        if timeout is not None:
                            elapsed = time.time() - start_time
                            remaining = max(0.1, timeout - elapsed)
                            import select
                            # Check if data is available to read
                            r, _, _ = select.select([self._process.stdout], [], [], remaining)
                            if not r:
                                raise DaemonTimeoutError(f"Operation timed out after {timeout} seconds")
                        
                        # Read response (one line ending with newline)
                        response_line = self._process.stdout.readline()
                        if not response_line:
                            raise DaemonConnectionError("Connection closed by daemon (pipe EOF)")
                        
                        response = deserialize_message(response_line)
                        
                        # If we have an expected ID and this response doesn't match it, discard and keep reading
                        if expected_id is not None and response.get('id') != expected_id:
                            logger.debug(f"Discarding stray/out-of-order response (expected ID {expected_id}, got {response.get('id')})")
                            continue
                            
                        return response
                except (OSError, ValueError) as e:
                    self._connected = False
                    raise DaemonConnectionError(f"Pipe error: {e}")
            
            # =================================================================
            # Legacy Socket Mode Send/Receive (To be removed after 5.x)
            # =================================================================
            else:
                try:
                    self._socket.settimeout(timeout)
                    
                    # Send request
                    self._socket.sendall(message)
                    
                    start_time = time.time()
                    while True:
                        if timeout is not None:
                            elapsed = time.time() - start_time
                            remaining = max(0.1, timeout - elapsed)
                            self._socket.settimeout(remaining)
                            
                        # Receive response (read until newline)
                        response_data = b''
                        while b'\n' not in response_data:
                            chunk = self._socket.recv(4096)
                            if not chunk:
                                raise DaemonConnectionError("Connection closed by daemon")
                            response_data += chunk
                        
                        # Parse response
                        response = deserialize_message(response_data.split(b'\n', 1)[0])
                        
                        # If we have an expected ID and this response doesn't match it, discard and keep reading
                        if expected_id is not None and response.get('id') != expected_id:
                            logger.debug(f"Discarding stray/out-of-order socket response (expected ID {expected_id}, got {response.get('id')})")
                            continue
                            
                        return response
                    
                except socket.timeout:
                    raise DaemonTimeoutError(f"Operation timed out after {timeout} seconds")
                except (socket.error, OSError) as e:
                    self._connected = False
                    raise DaemonConnectionError(f"Socket error: {e}")
    
    def request(self, operation: str, params: Dict[str, Any], 
                timeout: float = None) -> Dict[str, Any]:
        """Send a request to daemon and return response."""
        # Try to connect if not connected
        if not self.is_connected():
            if not self.connect():
                raise DaemonConnectionError("Could not connect to daemon")
        
        # Create and send request
        request = create_request(operation, params)
        message = serialize_message(request)
        
        # Retry on connection errors (only in socket mode)
        last_error = None
        retries = self.RECONNECT_RETRIES if self._process is None else 1
        for attempt in range(retries):
            try:
                response = self._send_recv(message, expected_id=request['id'], timeout=timeout)
                
                # Validate response ID matches request
                if response.get('id') != request['id']:
                    logger.warning(f"Response ID mismatch: {request['id']} != {response.get('id')}")
                
                return response
                
            except DaemonConnectionError as e:
                last_error = e
                if operation == 'shutdown':
                    logger.info(f"Connection closed during shutdown request (expected): {e}")
                else:
                    logger.warning(f"Connection error (attempt {attempt + 1}/{retries}): {e}")
                
                # Try to reconnect
                if attempt < retries - 1:
                    time.sleep(self.RECONNECT_DELAY)
                    if self.connect():
                        message = serialize_message(request)  # Re-serialize
                        continue
                
                # If all retries failed, raise
                raise last_error
                
            except DaemonTimeoutError:
                raise  # Don't retry on timeout
            except Exception as e:
                logger.error(f"Unexpected error in request: {str(e)}", exc_info=True)
                raise
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()


class LocalDaemonClient:
    """In-process daemon client when application runs directly as root."""

    def __init__(self, *args, **kwargs):
        pass

    def is_connected(self) -> bool:
        return True

    def connect(self, timeout: float = None) -> bool:
        return True

    def disconnect(self):
        pass

    def request(self, operation: str, params: Dict[str, Any], timeout: float = None) -> Dict[str, Any]:
        import uuid
        import subprocess
        request_id = str(uuid.uuid4())
        
        if operation == 'run_command':
            command = params.get('command')
            if not command:
                return {'id': request_id, 'success': False, 'error': "Command parameter is required"}
            if not isinstance(command, list):
                return {'id': request_id, 'success': False, 'error': "Command must be a list"}
            
            cmd_timeout = params.get('timeout')
            if cmd_timeout is not None:
                try:
                    cmd_timeout = int(cmd_timeout)
                except ValueError:
                    cmd_timeout = None
            
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=cmd_timeout
                )
                return {
                    'id': request_id,
                    'success': True,
                    'result': {
                        'returncode': result.returncode,
                        'stdout': result.stdout,
                        'stderr': result.stderr,
                        'success': result.returncode == 0
                    }
                }
            except subprocess.TimeoutExpired as e:
                return {
                    'id': request_id,
                    'success': True,
                    'result': {
                        'returncode': -1,
                        'stdout': '',
                        'stderr': f'Command timed out: {e}',
                        'success': False
                    }
                }
            except Exception as e:
                return {
                    'id': request_id,
                    'success': True,
                    'result': {
                        'returncode': -1,
                        'stdout': '',
                        'stderr': str(e),
                        'success': False
                    }
                }
        elif operation == 'ping':
            return {
                'id': request_id,
                'success': True,
                'result': 'pong'
            }
        elif operation == 'shutdown':
            return {
                'id': request_id,
                'success': True,
                'result': {'message': 'Shutting down'}
            }
        else:
            return {
                'id': request_id,
                'success': False,
                'error': f"Unknown operation: {operation}"
            }

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


__all__ = ['DaemonClient', 'DaemonConnectionError', 'DaemonTimeoutError', 'LocalDaemonClient']
