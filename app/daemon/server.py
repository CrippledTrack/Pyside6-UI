"""Privileged daemon server for executing root operations via stdin/stdout pipes."""

from __future__ import annotations

import os
import sys
import logging
import subprocess
import threading
import signal
import select
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional
from .protocol import (
    OPERATION_RUN_COMMAND,
    OPERATION_RUN_COMMAND_STREAM,
    OPERATION_CANCEL,
    OPERATION_SHUTDOWN,
    deserialize_message,
    create_response,
    create_stream_chunk,
    serialize_message
)

logger = logging.getLogger(__name__)

log_format = '[Daemon] %(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=log_format)

MAX_WORKERS = 8
SHUTDOWN_REQUESTED = threading.Event()


class PrivilegedDaemon:
    """Daemon server for executing privileged operations over stdin/stdout."""

    def __init__(self, max_workers: int = MAX_WORKERS):
        self.allowed_uid = self._get_original_uid()
        self.allowed_gid = self._get_original_gid()
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='daemon-worker')
        self._lock = threading.Lock()
        self._active_jobs: Dict[str, subprocess.Popen] = {}
        self._jobs_lock = threading.Lock()
        self._pipe_stdout = None
        self._stdout_lock = threading.Lock()

    def _get_original_uid(self) -> Optional[int]:
        """Get the original user's UID from environment variables."""
        uid_str = os.environ.get('SUDO_UID') or os.environ.get('PKEXEC_UID')
        if uid_str:
            try:
                return int(uid_str)
            except ValueError:
                pass
        return None

    def _get_original_gid(self) -> Optional[int]:
        """Get the original user's GID from environment variables."""
        gid_str = os.environ.get('SUDO_GID') or os.environ.get('PKEXEC_GID')
        if gid_str:
            try:
                return int(gid_str)
            except ValueError:
                pass
        return None

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
                result = self._execute_command(request_id, params)
                return create_response(request_id, True, result)

            elif operation == OPERATION_RUN_COMMAND_STREAM:
                result = self._execute_command_stream(request_id, params)
                return create_response(request_id, True, result)

            elif operation == OPERATION_CANCEL:
                result = self._handle_cancel(params)
                return create_response(request_id, True, result)

            elif operation == 'ping':
                return create_response(request_id, True, 'pong')

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

    def _execute_command(self, request_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a command as root."""
        command = params.get('command')
        if not command:
            raise ValueError("Command parameter is required")

        if not isinstance(command, list):
            raise ValueError("Command must be a list")

        logger.info(f"Executing command: {' '.join(command)}")

        try:
            cmd_timeout = params.get('timeout')
            if cmd_timeout is not None:
                cmd_timeout = int(cmd_timeout)

            proc = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            with self._jobs_lock:
                self._active_jobs[request_id] = proc

            try:
                stdout, stderr = proc.communicate(timeout=cmd_timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
                logger.error(f"Command timed out: {' '.join(command)}")
                return {
                    'returncode': -1,
                    'stdout': stdout or '',
                    'stderr': f'Command timed out after {cmd_timeout}s',
                    'success': False
                }
            finally:
                with self._jobs_lock:
                    self._active_jobs.pop(request_id, None)

            return {
                'returncode': proc.returncode,
                'stdout': stdout,
                'stderr': stderr,
                'success': proc.returncode == 0
            }

        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return {
                'returncode': -1,
                'stdout': '',
                'stderr': str(e),
                'success': False
            }

    def _execute_command_stream(self, request_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a command as root, streaming stdout line-by-line over the pipe.

        Each line of output is sent as an intermediate streaming chunk response
        via the pipe. The final response contains the aggregated output and
        return code.
        """
        command = params.get('command')
        if not command:
            raise ValueError("Command parameter is required")

        if not isinstance(command, list):
            raise ValueError("Command must be a list")

        logger.info(f"Executing streaming command: {' '.join(command)}")

        try:
            proc = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )

            with self._jobs_lock:
                self._active_jobs[request_id] = proc

            aggregated_output = []
            try:
                for line in proc.stdout:
                    aggregated_output.append(line)
                    chunk_msg = create_stream_chunk(request_id, line)
                    chunk_data = serialize_message(chunk_msg)
                    with self._stdout_lock:
                        self._pipe_stdout.write(chunk_data)
                        self._pipe_stdout.flush()

                proc.wait()
            finally:
                with self._jobs_lock:
                    self._active_jobs.pop(request_id, None)

            return {
                'returncode': proc.returncode,
                'stdout': ''.join(aggregated_output),
                'stderr': '',
                'success': proc.returncode == 0
            }

        except Exception as e:
            logger.error(f"Streaming command execution failed: {e}")
            return {
                'returncode': -1,
                'stdout': '',
                'stderr': str(e),
                'success': False
            }

    def _handle_cancel(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Cancel a running job by terminating its subprocess.

        Uses SIGTERM first, waits 2 seconds for graceful exit, then SIGKILL.
        """
        target_id = params.get('target_id')
        if not target_id:
            raise ValueError("target_id parameter is required")

        with self._jobs_lock:
            proc = self._active_jobs.get(target_id)

        if proc is None:
            logger.debug(f"Cancel requested for {target_id} but no active job found")
            return {'cancelled': False, 'target_id': target_id, 'reason': 'not found'}

        logger.info(f"Cancelling job {target_id} (PID {proc.pid})")
        try:
            proc.terminate()
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                logger.warning(f"Job {target_id} did not exit after SIGTERM, sending SIGKILL")
                proc.kill()
                proc.wait(timeout=5.0)

            return {'cancelled': True, 'target_id': target_id}
        except Exception as e:
            logger.error(f"Failed to cancel job {target_id}: {e}")
            return {'cancelled': False, 'target_id': target_id, 'reason': str(e)}

    def _handle_async_pipe_request(self, request: Dict[str, Any]):
        """Handle a pipe request asynchronously and write the response thread-safely."""
        try:
            response = self._handle_request(request)
            response_data = serialize_message(response)
            with self._stdout_lock:
                self._pipe_stdout.write(response_data)
                self._pipe_stdout.flush()
        except Exception as e:
            logger.error(f"Error in async pipe handler: {e}", exc_info=True)
            try:
                request_id = request.get('id', 'unknown')
                error_response = create_response(request_id, False, error=str(e))
                error_data = serialize_message(error_response)
                with self._stdout_lock:
                    self._pipe_stdout.write(error_data)
                    self._pipe_stdout.flush()
            except Exception:
                logger.error("Failed to send error response", exc_info=True)

    def _install_parent_death_signal(self) -> None:
        """Register PR_SET_PDEATHSIG and exit if the parent is already gone.

        Elevation may already set PDEATHSIG via preexec_fn; calling again here
        covers in-process / atypical spawn paths and closes the fork/exec race
        where the parent dies before prctl runs.
        """
        try:
            import ctypes

            libc = ctypes.CDLL("libc.so.6", use_errno=True)
            PR_SET_PDEATHSIG = 1
            SIGTERM = 15
            result = libc.prctl(PR_SET_PDEATHSIG, SIGTERM)
            if result != 0:
                errno = ctypes.get_errno()
                logger.warning(f"prctl(PR_SET_PDEATHSIG) failed with errno {errno}")
            else:
                logger.info("Registered PR_SET_PDEATHSIG=SIGTERM")

            # If the parent already died between fork and now, exit immediately.
            if os.getppid() == 1:
                logger.error("Parent process already gone (ppid=1); exiting")
                sys.exit(1)
        except Exception as e:
            logger.warning(f"Could not install parent death signal: {e}")

    def start(self):
        """Start the daemon in stdin/stdout pipe mode."""
        # Save the raw binary stdout for exclusive IPC use, then redirect
        # Python-level stdout to stderr so any rogue print() from imported
        # libraries cannot corrupt the JSON pipe.
        self._pipe_stdout = sys.stdout.buffer
        sys.stdout = sys.stderr

        logging.basicConfig(
            stream=sys.stderr, level=logging.INFO,
            format='[Daemon] %(asctime)s - %(name)s - %(levelname)s - %(message)s',
            force=True
        )

        print("[Daemon] Starting privileged daemon...", file=sys.stderr, flush=True)
        print(f"[Daemon] Current EUID: {os.geteuid()}, UID: {os.getuid()}", file=sys.stderr, flush=True)

        self._install_parent_death_signal()

        if os.geteuid() != 0:
            error_msg = f"Daemon must run as root (current EUID: {os.geteuid()})"
            logger.error(error_msg)
            print(f"[Daemon] ERROR: {error_msg}", file=sys.stderr, flush=True)
            sys.exit(1)

        self._setup_signal_handlers()

        logger.info("Pipe daemon started and ready")
        print("[Daemon] Pipe daemon started and ready", file=sys.stderr, flush=True)

        while not SHUTDOWN_REQUESTED.is_set():
            try:
                r, _, _ = select.select([sys.stdin.buffer], [], [], 1.0)
                if not r:
                    continue

                line = sys.stdin.buffer.readline()
                if not line:
                    logger.info("Pipe EOF reached, shutting down")
                    break

                request = deserialize_message(line)
                self.executor.submit(self._handle_async_pipe_request, request)

            except Exception as e:
                logger.error(f"Error in pipe mode loop: {e}", exc_info=True)
                break

        self.shutdown()

    def shutdown(self):
        """Shutdown the daemon gracefully."""
        logger.info("Shutting down daemon...")

        try:
            self.executor.shutdown(wait=True, cancel_futures=True)
        except TypeError:
            self.executor.shutdown(wait=True)

        logger.info("Daemon stopped")


def run_daemon(argv: Optional[List[str]] = None) -> int:
    """
    Run the privileged pipe daemon.

    Accepts ``--pipe`` or ``--daemon`` (alias) as the entry flag.
    """
    if argv is None:
        argv = sys.argv

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

    if uid is not None and 'PKEXEC_UID' not in os.environ and 'SUDO_UID' not in os.environ:
        os.environ['PKEXEC_UID'] = str(uid)
        os.environ['SUDO_UID'] = str(uid)
    if gid is not None and 'PKEXEC_GID' not in os.environ and 'SUDO_GID' not in os.environ:
        os.environ['PKEXEC_GID'] = str(gid)
        os.environ['SUDO_GID'] = str(gid)

    try:
        print(f"[Daemon] Initializing daemon with UID: {uid}, GID: {gid}", file=sys.stderr, flush=True)
        daemon = PrivilegedDaemon()
        if uid is not None:
            daemon.allowed_uid = uid
            print(f"[Daemon] Set allowed_uid to {uid}", file=sys.stderr, flush=True)
        if gid is not None:
            daemon.allowed_gid = gid
            print(f"[Daemon] Set allowed_gid to {gid}", file=sys.stderr, flush=True)

        print("[Daemon] Calling daemon.start()...", file=sys.stderr, flush=True)
        daemon.start()
        return 0
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 0
    except SystemExit as e:
        logger.error(f"Daemon SystemExit: {e.code}")
        return e.code if isinstance(e.code, int) else 1
    except Exception as e:
        logger.error(f"Daemon error: {e}", exc_info=True)
        return 1


__all__ = ['PrivilegedDaemon', 'run_daemon']
