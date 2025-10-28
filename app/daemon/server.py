"""Privileged daemon server for executing root operations."""

import os
import sys
import socket
import logging
import subprocess
import threading
import signal
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional
from .protocol import (
    OPERATION_RUN_COMMAND,
    OPERATION_SHUTDOWN,
    deserialize_message,
    create_response,
    serialize_message
)

logger = logging.getLogger(__name__)

# Configure logging for daemon
log_format = '[Daemon] %(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=log_format)

SOCKET_PATH = '/tmp/cyberpatriot-daemon.sock'
MAX_WORKERS = 8
SHUTDOWN_REQUESTED = threading.Event()


class PrivilegedDaemon:
    """Daemon server for executing privileged operations."""
    
    def __init__(self, socket_path: str = SOCKET_PATH, max_workers: int = MAX_WORKERS):
        self.socket_path = socket_path
        self.server_socket: Optional[socket.socket] = None
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='daemon-worker')
        self._lock = threading.Lock()
    
    def _cleanup_socket(self):
        """Remove existing socket file if it exists."""
        try:
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)
        except OSError as e:
            logger.warning(f"Could not remove socket file: {e}")
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            SHUTDOWN_REQUESTED.set()
            self.shutdown()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def _handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a single request."""
        request_id = request.get('id', 'unknown')
        operation = request.get('operation')
        params = request.get('params', {})
        
        logger.debug(f"Handling request {request_id}: {operation}")
        
        try:
            if operation == OPERATION_RUN_COMMAND:
                result = self._execute_command(params)
                return create_response(request_id, True, result)
            
            elif operation == OPERATION_SHUTDOWN:
                logger.info("Shutdown requested")
                SHUTDOWN_REQUESTED.set()
                return create_response(request_id, True, {'message': 'Shutting down'})
            
            else:
                return create_response(
                    request_id, False,
                    error=f"Unknown operation: {operation}"
                )
                
        except Exception as e:
            logger.error(f"Error handling request {request_id}: {e}", exc_info=True)
            return create_response(request_id, False, error=str(e))
    
    def _execute_command(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a command as root."""
        command = params.get('command')
        if not command:
            raise ValueError("Command parameter is required")
        
        if not isinstance(command, list):
            raise ValueError("Command must be a list")
        
        # Execute command
        logger.debug(f"Executing command: {' '.join(command)}")
        
        try:
            # Handle timeout: None means no timeout
            cmd_timeout = params.get('timeout')
            if cmd_timeout is not None:
                cmd_timeout = int(cmd_timeout)
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=cmd_timeout  # None means no timeout
            )
            
            return {
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'success': result.returncode == 0
            }
            
        except subprocess.TimeoutExpired as e:
            logger.error(f"Command timed out: {' '.join(command)}")
            return {
                'returncode': -1,
                'stdout': '',
                'stderr': f'Command timed out: {e}',
                'success': False
            }
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return {
                'returncode': -1,
                'stdout': '',
                'stderr': str(e),
                'success': False
            }
    
    def _handle_client(self, client_socket: socket.socket, addr):
        """Handle a client connection."""
        logger.debug(f"Client connected: {addr}")
        
        try:
            while not SHUTDOWN_REQUESTED.is_set():
                # Read request
                data = b''
                while b'\n' not in data:
                    chunk = client_socket.recv(4096)
                    if not chunk:
                        return  # Client closed connection
                    data += chunk
                
                # Parse request
                request_line = data.split(b'\n', 1)[0]
                request = deserialize_message(request_line)
                
                # Handle request in thread pool
                future = self.executor.submit(self._handle_request, request)
                response = future.result()
                
                # Send response
                response_data = serialize_message(response)
                client_socket.sendall(response_data)
                
        except socket.error as e:
            logger.debug(f"Client connection error: {e}")
        except Exception as e:
            logger.error(f"Error handling client: {e}", exc_info=True)
        finally:
            client_socket.close()
            logger.debug(f"Client disconnected: {addr}")
    
    def start(self):
        """Start the daemon server."""
        # Verify we're running as root
        if os.geteuid() != 0:
            logger.error("Daemon must run as root")
            sys.exit(1)
        
        logger.info("Starting privileged daemon")
        
        # Setup signal handlers
        self._setup_signal_handlers()
        
        # Cleanup old socket
        self._cleanup_socket()
        
        # Create socket
        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_socket.bind(self.socket_path)
        self.server_socket.listen(5)
        
        # Set socket permissions so UI can connect
        os.chmod(self.socket_path, 0o666)
        
        logger.info(f"Daemon listening on {self.socket_path}")
        
        # Main accept loop
        while not SHUTDOWN_REQUESTED.is_set():
            try:
                self.server_socket.settimeout(1.0)  # Check shutdown flag periodically
                client_socket, addr = self.server_socket.accept()
                
                # Handle client in separate thread
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, addr),
                    daemon=True
                )
                client_thread.start()
                
            except socket.timeout:
                continue  # Check shutdown flag
            except socket.error as e:
                if not SHUTDOWN_REQUESTED.is_set():
                    logger.error(f"Socket error: {e}")
                    break
        
        self.shutdown()
    
    def shutdown(self):
        """Shutdown the daemon gracefully."""
        logger.info("Shutting down daemon...")
        
        # Stop accepting new connections
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        # Wait for active tasks to complete
        self.executor.shutdown(wait=True, timeout=5.0)
        
        # Cleanup socket file
        self._cleanup_socket()
        
        logger.info("Daemon stopped")


def run_daemon() -> int:
    """Run the daemon (entry point for --daemon mode)."""
    try:
        daemon = PrivilegedDaemon()
        daemon.start()
        return 0
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 0
    except SystemExit as e:
        # Re-raise SystemExit but log it first
        logger.error(f"Daemon SystemExit: {e.code}")
        return e.code if isinstance(e.code, int) else 1
    except Exception as e:
        logger.error(f"Daemon error: {e}", exc_info=True)
        return 1
