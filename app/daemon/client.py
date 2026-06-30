"""Daemon client for communicating with privileged daemon."""

from __future__ import annotations

import queue
import socket
import logging
import threading
import time
import subprocess
from typing import Callable, Dict, Any, Optional
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
            # Multiplexed pipe infrastructure
            self._pending_requests: Dict[str, queue.Queue] = {}
            self._pending_lock = threading.Lock()
            self._write_lock = threading.Lock()
            self._reader_running = False
            self._reader_thread: Optional[threading.Thread] = None
            # Streaming callback dispatch
            self._stream_callbacks: Dict[str, Callable[[str], None]] = {}
            self._stream_callbacks_lock = threading.Lock()
            # Start reader thread immediately — callers may skip connect()
            # because _connected is already True from above.
            self._start_reader_thread()
        # =====================================================================
        # Legacy Socket Mode Setup (To be removed after 5.x)
        # =====================================================================
        else:
            if socket_path is None:
                self.socket_path = get_socket_path()
            else:
                self.socket_path = socket_path
            self._socket: Optional[socket.socket] = None
            self._connected = False
    
    def is_connected(self) -> bool:
        """Check if client is connected to daemon."""
        if self._process is not None:
            return self._connected and self._process.poll() is None
        return self._connected and self._socket is not None
    
    def _start_reader_thread(self):
        """Start the background pipe reader thread if not already running."""
        if self._reader_thread is not None and self._reader_thread.is_alive():
            return
        self._reader_running = True
        self._reader_thread = threading.Thread(
            target=self._pipe_reader_loop,
            name="PipeDaemonReader",
            daemon=True,
        )
        self._reader_thread.start()
        logger.info("Pipe reader thread started")

    def _pipe_reader_loop(self):
        """Dedicated reader loop that dispatches responses to per-request queues.
        
        For streaming responses (status == 'running'), invokes the registered
        stream callback instead of putting the response in the queue.
        """
        try:
            while self._reader_running and self._process.poll() is None:
                line = self._process.stdout.readline()
                if not line:
                    break
                try:
                    response = deserialize_message(line)
                except Exception:
                    logger.warning("Failed to deserialize pipe response, skipping")
                    continue
                resp_id = response.get('id')
                if resp_id:
                    # Check if this is a streaming chunk
                    if response.get('status') == 'running':
                        with self._stream_callbacks_lock:
                            callback = self._stream_callbacks.get(resp_id)
                        if callback:
                            try:
                                callback(response.get('chunk', ''))
                            except Exception as e:
                                logger.warning(f"Stream callback error for {resp_id}: {e}")
                        else:
                            logger.debug(f"Streaming chunk for {resp_id} but no callback registered, discarding")
                        continue
                    
                    # Final response — route to pending queue
                    with self._pending_lock:
                        q = self._pending_requests.get(resp_id)
                    if q:
                        q.put(response)
                    else:
                        logger.debug(f"No pending request for response ID {resp_id}, discarding")
                else:
                    logger.debug("Received response with no ID, discarding")
        except Exception as e:
            logger.error(f"Pipe reader loop error: {e}", exc_info=True)
        finally:
            self._reader_running = False
            self._connected = False
            # Drain all pending queues with None sentinel so waiting threads unblock
            with self._pending_lock:
                for rid, q in self._pending_requests.items():
                    q.put(None)
                self._pending_requests.clear()
            # Clear stream callbacks
            with self._stream_callbacks_lock:
                self._stream_callbacks.clear()
            logger.info("Pipe reader loop exited")

    def connect(self, timeout: float = None) -> bool:
        """Connect to daemon."""
        if self._process is not None:
            with self._lock:
                self._connected = self._process.poll() is None
                if self._connected:
                    self._start_reader_thread()
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
                self._reader_running = False
                if self._process.poll() is None:
                    try:
                        self._process.terminate()
                        self._process.wait(timeout=2.0)
                    except Exception:
                        try:
                            self._process.kill()
                        except Exception:
                            pass
                # Reader thread will exit on EOF/poll; join briefly
                if self._reader_thread is not None:
                    self._reader_thread.join(timeout=2.0)
                    self._reader_thread = None
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
        
        # =================================================================
        # Pipe Mode Send/Receive (Multiplexed)
        # =================================================================
        if self._process is not None:
            q: queue.Queue = queue.Queue()
            # Register this request's queue so the reader thread can route the response
            with self._pending_lock:
                self._pending_requests[expected_id] = q

            try:
                # Write under write lock (prevents line interleaving between threads)
                with self._write_lock:
                    self._process.stdin.write(message)
                    self._process.stdin.flush()

                # Wait for OUR specific response (reader thread routes it)
                try:
                    response = q.get(timeout=timeout)
                except queue.Empty:
                    raise DaemonTimeoutError(
                        f"Operation timed out after {timeout} seconds"
                    )
                if response is None:
                    raise DaemonConnectionError(
                        "Connection closed by daemon (pipe EOF)"
                    )
                return response
            finally:
                # Always clean up the pending entry
                with self._pending_lock:
                    self._pending_requests.pop(expected_id, None)

        # =================================================================
        # Legacy Socket Mode Send/Receive (To be removed after 5.x)
        # =================================================================
        with self._lock:
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
                    
                    # If we have an expected ID and this response doesn't match it, discard and keep reading.
                    # WARNING: Discarding stray responses is only safe because the server handles requests 
                    # synchronously and sequentially (one at a time). If the server were async, discarding non-matching
                    # IDs here would cause other waiting threads to miss their responses, leading to timeouts.
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
        retries = 2 if self._process is not None else self.RECONNECT_RETRIES
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
                    if self._process is not None:
                        # Pipe mode: restart the daemon process
                        if self._restart_pipe_daemon():
                            message = serialize_message(request)  # Re-serialize
                            continue
                    else:
                        # Socket mode: simple reconnect
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
    
    def request_stream(self, operation: str, params: Dict[str, Any],
                       on_chunk: Callable[[str], None],
                       timeout: float = None) -> Dict[str, Any]:
        """Send a streaming request to the daemon.
        
        Like request(), but for operations that produce incremental output
        (e.g. run_command_stream). The on_chunk callback is invoked for each
        intermediate line of output as it arrives from the daemon.
        
        The final response (containing aggregated output and return code) is
        returned when the operation completes.
        
        This method is only supported in pipe mode.
        
        Args:
            operation: The operation to perform (e.g. 'run_command_stream').
            params: Operation parameters.
            on_chunk: Callback invoked with each line of streaming output.
            timeout: Optional timeout in seconds for the entire operation.
        
        Returns:
            The final response dict from the daemon.
        
        Raises:
            DaemonConnectionError: If not connected or connection lost.
            DaemonTimeoutError: If the operation times out.
            RuntimeError: If called in socket mode.
        """
        if self._process is None:
            raise RuntimeError("request_stream() is only supported in pipe mode")
        
        if not self.is_connected():
            if not self.connect():
                raise DaemonConnectionError("Could not connect to daemon")
        
        request = create_request(operation, params)
        request_id = request['id']
        message = serialize_message(request)
        
        # Register the streaming callback before sending the request
        with self._stream_callbacks_lock:
            self._stream_callbacks[request_id] = on_chunk
        
        try:
            response = self._send_recv(message, expected_id=request_id, timeout=timeout)
            
            if response.get('id') != request_id:
                logger.warning(f"Response ID mismatch: {request_id} != {response.get('id')}")
            
            return response
        finally:
            # Always clean up the streaming callback
            with self._stream_callbacks_lock:
                self._stream_callbacks.pop(request_id, None)
    
    def cancel_request(self, target_id: str, timeout: float = 5.0) -> Dict[str, Any]:
        """Cancel a running request by its ID.
        
        Sends a cancel operation to the daemon, which will SIGTERM the
        subprocess associated with the given request ID (with a 2-second
        grace period before SIGKILL).
        
        Args:
            target_id: The ID of the request to cancel.
            timeout: Timeout for the cancel request itself.
        
        Returns:
            Response dict with 'cancelled' (bool) and 'target_id' fields.
        """
        return self.request('cancel', {'target_id': target_id}, timeout=timeout)
    
    def _restart_pipe_daemon(self) -> bool:
        """Restart the pipe daemon after a crash or disconnection.
        
        Kills the old process (if still alive), spawns a new daemon via
        elevation_linux.start_daemon(), and re-establishes the reader loop.
        
        Returns:
            True if the restart succeeded, False otherwise.
        """
        logger.info("Attempting to restart pipe daemon...")
        
        # Kill old process if still alive
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                self._process.wait(timeout=2.0)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
        
        # Stop old reader thread
        self._reader_running = False
        if self._reader_thread is not None:
            self._reader_thread.join(timeout=2.0)
            self._reader_thread = None
        
        try:
            from ..utils.elevation_linux import start_daemon
            new_client = start_daemon()
            if new_client is None:
                logger.error("Failed to restart pipe daemon: start_daemon returned None")
                return False
            
            # Transplant the new process and state
            # Stop the new client's reader thread before stealing its process
            new_client._reader_running = False
            if new_client._reader_thread:
                new_client._reader_thread.join(timeout=2.0)
            self._process = new_client._process
            self._connected = True
            self._pending_requests = {}
            self._stream_callbacks = {}
            self._start_reader_thread()
            
            # Update the global daemon client reference
            from ..daemon import set_daemon_client
            set_daemon_client(self)
            
            logger.info("Pipe daemon restarted successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to restart pipe daemon: {e}", exc_info=True)
            self._connected = False
            return False
    
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
