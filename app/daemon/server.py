"""Privileged daemon server for executing root operations."""

from __future__ import annotations

import os
import sys
import socket
import logging
import subprocess
import threading
import signal
import struct
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional
from .protocol import (
    OPERATION_RUN_COMMAND,
    OPERATION_SHUTDOWN,
    get_socket_path,
    deserialize_message,
    create_response,
    serialize_message
)

logger = logging.getLogger(__name__)

# Configure logging for daemon
log_format = '[Daemon] %(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=log_format)

MAX_WORKERS = 8
SHUTDOWN_REQUESTED = threading.Event()


class PrivilegedDaemon:
    """Daemon server for executing privileged operations."""
    
    def __init__(self, socket_path: Optional[str] = None, max_workers: int = MAX_WORKERS):
        # Get original user's UID/GID from environment (set by sudo/pkexec)
        self.allowed_uid = self._get_original_uid()
        self.allowed_gid = self._get_original_gid()
        
        # Determine socket path based on user UID (more secure location)
        if socket_path is None:
            self.socket_path = get_socket_path(self.allowed_uid)
        else:
            self.socket_path = socket_path
        
        self.server_socket: Optional[socket.socket] = None
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='daemon-worker')
        self._lock = threading.Lock()
    
    def _get_original_uid(self) -> Optional[int]:
        """Get the original user's UID from environment variables."""
        # sudo sets SUDO_UID, pkexec sets PKEXEC_UID
        uid_str = os.environ.get('SUDO_UID') or os.environ.get('PKEXEC_UID')
        if uid_str:
            try:
                return int(uid_str)
            except ValueError:
                pass
        return None
    
    def _get_original_gid(self) -> Optional[int]:
        """Get the original user's GID from environment variables."""
        # sudo sets SUDO_GID, pkexec sets PKEXEC_GID
        gid_str = os.environ.get('SUDO_GID') or os.environ.get('PKEXEC_GID')
        if gid_str:
            try:
                return int(gid_str)
            except ValueError:
                pass
        return None
    
    def _verify_client_credentials(self, client_socket: socket.socket) -> bool:
        """Verify that the connecting client belongs to the authorized user using SO_PEERCRED."""
        try:
            # SO_PEERCRED is Linux-specific and returns (pid, uid, gid) as a struct
            # Format: '3i' means 3 integers (pid, uid, gid)
            SOL_SOCKET = socket.SOL_SOCKET
            SO_PEERCRED = 17  # Linux-specific constant
            
            creds = client_socket.getsockopt(SOL_SOCKET, SO_PEERCRED, struct.calcsize('3i'))
            pid, uid, gid = struct.unpack('3i', creds)
            
            # Verify UID matches the original user
            if self.allowed_uid is not None and uid != self.allowed_uid:
                logger.warning(f"Connection rejected: UID {uid} does not match allowed UID {self.allowed_uid} (PID {pid})")
                return False
            
            logger.debug(f"Client verified: PID {pid}, UID {uid}, GID {gid}")
            return True
            
        except (OSError, struct.error, AttributeError) as e:
            # SO_PEERCRED might not be available on all systems
            # Fall back to less secure but still better than nothing
            logger.warning(f"Could not verify client credentials: {e}. Falling back to socket ownership check.")
            # If we can't verify, we'll rely on socket file permissions
            return True
    
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
        
        # Verify client credentials before processing requests
        if not self._verify_client_credentials(client_socket):
            logger.error(f"Unauthorized connection attempt from {addr}, closing connection")
            client_socket.close()
            return
        
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
        # Log immediately to stderr so we can see what's happening
        print("[Daemon] Starting privileged daemon...", file=sys.stderr, flush=True)
        print(f"[Daemon] Current EUID: {os.geteuid()}, UID: {os.getuid()}", file=sys.stderr, flush=True)
        
        # Verify we're running as root
        if os.geteuid() != 0:
            error_msg = f"Daemon must run as root (current EUID: {os.geteuid()})"
            logger.error(error_msg)
            print(f"[Daemon] ERROR: {error_msg}", file=sys.stderr, flush=True)
            sys.exit(1)
        
        logger.info("Starting privileged daemon")
        logger.info(f"Socket path will be: {self.socket_path}")
        logger.info(f"Allowed UID: {self.allowed_uid}, Allowed GID: {self.allowed_gid}")
        print(f"[Daemon] Socket path: {self.socket_path}", file=sys.stderr, flush=True)
        print(f"[Daemon] Allowed UID: {self.allowed_uid}, Allowed GID: {self.allowed_gid}", file=sys.stderr, flush=True)
        
        # Setup signal handlers
        self._setup_signal_handlers()
        
        # Cleanup old socket
        self._cleanup_socket()
        
        # Ensure socket directory exists
        socket_dir = os.path.dirname(self.socket_path)
        if socket_dir and not os.path.exists(socket_dir):
            try:
                os.makedirs(socket_dir, mode=0o700, exist_ok=True)
                logger.info(f"Created socket directory: {socket_dir}")
            except OSError as e:
                logger.error(f"Failed to create socket directory {socket_dir}: {e}")
                raise
        
        # Create socket
        try:
            print(f"[Daemon] Creating socket at: {self.socket_path}", file=sys.stderr, flush=True)
            self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.server_socket.bind(self.socket_path)
            print(f"[Daemon] Socket bound successfully", file=sys.stderr, flush=True)
            self.server_socket.listen(5)
            logger.info(f"Socket created and bound successfully")
            print(f"[Daemon] Socket created and bound successfully", file=sys.stderr, flush=True)
        except OSError as e:
            error_msg = f"Failed to create/bind socket at {self.socket_path}: {e}"
            logger.error(error_msg)
            print(f"[Daemon] ERROR: {error_msg}", file=sys.stderr, flush=True)
            raise
        
        # Set socket ownership and permissions to only allow the original user
        if self.allowed_uid is not None and self.allowed_gid is not None:
            try:
                os.chown(self.socket_path, self.allowed_uid, self.allowed_gid)
                os.chmod(self.socket_path, 0o600)  # Only owner can read/write
                logger.info(f"Socket restricted to UID {self.allowed_uid}, GID {self.allowed_gid}")
            except OSError as e:
                logger.warning(f"Could not set socket ownership: {e}. Using permissive permissions.")
                os.chmod(self.socket_path, 0o666)  # Fallback to world-writable (less secure)
        else:
            logger.warning("Could not determine original user UID/GID. Using permissive socket permissions.")
            os.chmod(self.socket_path, 0o666)  # Fallback to world-writable (less secure)
        
        logger.info(f"Daemon listening on {self.socket_path}")
        print(f"[Daemon] Daemon is now listening on socket: {self.socket_path}", file=sys.stderr, flush=True)
        
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
            except Exception:
                pass
        
        # Wait for active tasks to complete
        self.executor.shutdown(wait=True, timeout=5.0)
        
        # Cleanup socket file
        self._cleanup_socket()
        
        logger.info("Daemon stopped")


def run_daemon(argv: Optional[List[str]] = None) -> int:
    """
    Run the daemon (entry point for --daemon mode).
    
    Args:
        argv: Command-line arguments (defaults to sys.argv)
    """
    # Ensure sys is available (imported at module level, but explicit access helps)
    import sys
    if argv is None:
        argv = sys.argv
    
    # Parse UID/GID from command-line arguments (pkexec doesn't preserve env vars)
    uid = None
    gid = None
    if '--uid' in argv:
        idx = argv.index('--uid')
        if idx + 1 < len(argv):
            try:
                uid = int(argv[idx + 1])
                logger.info(f"Parsed UID from command line: {uid}")
            except (ValueError, IndexError) as e:
                logger.warning(f"Failed to parse UID from command line: {e}")
    else:
        logger.warning("--uid argument not found in daemon command line")
    
    if '--gid' in argv:
        idx = argv.index('--gid')
        if idx + 1 < len(argv):
            try:
                gid = int(argv[idx + 1])
                logger.info(f"Parsed GID from command line: {gid}")
            except (ValueError, IndexError) as e:
                logger.warning(f"Failed to parse GID from command line: {e}")
    
    # Set environment variables from command-line if not already set
    # (helps with socket path determination)
    if uid is not None and 'PKEXEC_UID' not in os.environ and 'SUDO_UID' not in os.environ:
        os.environ['PKEXEC_UID'] = str(uid)
        os.environ['SUDO_UID'] = str(uid)
    if gid is not None and 'PKEXEC_GID' not in os.environ and 'SUDO_GID' not in os.environ:
        os.environ['PKEXEC_GID'] = str(gid)
        os.environ['SUDO_GID'] = str(gid)
    
    try:
        print(f"[Daemon] Initializing daemon with UID: {uid}, GID: {gid}", file=sys.stderr, flush=True)
        daemon = PrivilegedDaemon()
        # Override UID/GID if provided via command line
        if uid is not None:
            daemon.allowed_uid = uid
            print(f"[Daemon] Set allowed_uid to {uid}", file=sys.stderr, flush=True)
        if gid is not None:
            daemon.allowed_gid = gid
            print(f"[Daemon] Set allowed_gid to {gid}", file=sys.stderr, flush=True)
        # Recalculate socket path with correct UID
        if uid is not None:
            from .protocol import get_socket_path
            daemon.socket_path = get_socket_path(uid)
            print(f"[Daemon] Set socket_path to {daemon.socket_path}", file=sys.stderr, flush=True)
        
        print("[Daemon] Calling daemon.start()...", file=sys.stderr, flush=True)
        daemon.start()
        print("[Daemon] daemon.start() returned (should not happen)", file=sys.stderr, flush=True)
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


__all__ = ['PrivilegedDaemon', 'run_daemon']
