"""Daemon client for communicating with privileged daemon."""

import socket
import logging
import threading
import time
from typing import Dict, Any, Optional
from .protocol import create_request, serialize_message, deserialize_message

logger = logging.getLogger(__name__)


class DaemonConnectionError(Exception):
    """Raised when daemon connection fails."""
    pass


class DaemonTimeoutError(Exception):
    """Raised when daemon operation times out."""
    pass


class DaemonClient:
    """Client for communicating with privileged daemon."""
    
    SOCKET_PATH = '/tmp/cyberpatriot-daemon.sock'
    CONNECT_TIMEOUT = 5.0
    OPERATION_TIMEOUT = 30.0
    RECONNECT_RETRIES = 3
    RECONNECT_DELAY = 1.0
    
    def __init__(self, socket_path: Optional[str] = None):
        self.socket_path = socket_path or self.SOCKET_PATH
        self._socket: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self._connected = False
    
    def is_connected(self) -> bool:
        """Check if client is connected to daemon."""
        return self._connected and self._socket is not None
    
    def connect(self, timeout: float = None) -> bool:
        """Connect to daemon."""
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
                    except:
                        pass
                self._socket = None
                self._connected = False
                return False
    
    def disconnect(self):
        """Disconnect from daemon."""
        with self._lock:
            if self._socket:
                try:
                    self._socket.close()
                except:
                    pass
                self._socket = None
            self._connected = False
            logger.info("Disconnected from daemon")
    
    def _send_recv(self, message: bytes, timeout: float = None) -> Dict[str, Any]:
        """Send message and receive response."""
        # If timeout is None, use a very large timeout (effectively unlimited)
        # Socket timeout of None blocks indefinitely, which we want for long operations
        if timeout is None:
            timeout = None  # No socket timeout - blocks until data arrives
        else:
            timeout = timeout or self.OPERATION_TIMEOUT
        
        if not self.is_connected():
            raise DaemonConnectionError("Not connected to daemon")
        
        with self._lock:
            try:
                self._socket.settimeout(timeout)
                
                # Send request
                self._socket.sendall(message)
                
                # Receive response (read until newline)
                response_data = b''
                while b'\n' not in response_data:
                    chunk = self._socket.recv(4096)
                    if not chunk:
                        raise DaemonConnectionError("Connection closed by daemon")
                    response_data += chunk
                
                # Parse response
                response = deserialize_message(response_data.split(b'\n', 1)[0])
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
        
        # Retry on connection errors
        last_error = None
        for attempt in range(self.RECONNECT_RETRIES):
            try:
                response = self._send_recv(message, timeout)
                
                # Validate response ID matches request
                if response.get('id') != request['id']:
                    logger.warning(f"Response ID mismatch: {request['id']} != {response.get('id')}")
                
                return response
                
            except DaemonConnectionError as e:
                last_error = e
                logger.warning(f"Connection error (attempt {attempt + 1}/{self.RECONNECT_RETRIES}): {e}")
                
                # Try to reconnect
                if attempt < self.RECONNECT_RETRIES - 1:
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
