"""Privileged daemon server for executing root operations via stdin/stdout pipes."""

from __future__ import annotations

import os
import sys
import logging
import subprocess
import threading
import signal
import select
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional, Tuple
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


def parse_daemon_argv(argv: List[str]) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """Parse ``--uid``, ``--gid``, and ``--parent-pid`` from daemon argv."""

    def _flag(name: str) -> Optional[int]:
        if name not in argv:
            return None
        idx = argv.index(name)
        if idx + 1 >= len(argv):
            logger.warning("%s argument missing value", name)
            return None
        try:
            return int(argv[idx + 1])
        except ValueError as e:
            logger.warning("Failed to parse %s from command line: %s", name, e)
            return None

    uid = _flag("--uid")
    gid = _flag("--gid")
    parent_pid = _flag("--parent-pid")
    if uid is None:
        logger.warning("--uid argument not found in daemon command line")
    return uid, gid, parent_pid


def parent_process_gone(pid: int) -> bool:
    """Return True when *pid* is missing or cannot be signaled."""
    if pid is None or pid <= 1:
        return True
    try:
        os.kill(pid, 0)
        return False
    except OSError:
        return True


def kqueue_wait_for_exit(pid: int) -> None:
    """Block until *pid* exits using kqueue NOTE_EXIT (Darwin).

    Raises if kqueue is unavailable or the kevent cannot be registered.
    Callers should fall back to polling. Times out in 1s slices so shutdown
    can interrupt the wait.
    """
    if not hasattr(select, "kqueue"):
        raise RuntimeError("kqueue is not available")
    kq = select.kqueue()
    try:
        ke = select.kevent(
            pid,
            filter=select.KQ_FILTER_PROC,
            flags=select.KQ_EV_ADD | select.KQ_EV_ONESHOT,
            fflags=select.KQ_NOTE_EXIT,
        )
        kq.control([ke], 0, 0)
        while not SHUTDOWN_REQUESTED.is_set():
            events = kq.control(None, 1, 1.0)
            if events:
                return
    finally:
        kq.close()



class PrivilegedDaemon:
    """Daemon server for executing privileged operations over stdin/stdout."""

    def __init__(self, max_workers: int = MAX_WORKERS, parent_pid: Optional[int] = None):
        self.allowed_uid = self._get_original_uid()
        self.allowed_gid = self._get_original_gid()
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='daemon-worker')
        self._lock = threading.Lock()
        self._active_jobs: Dict[str, subprocess.Popen] = {}
        self._jobs_lock = threading.Lock()
        self._pipe_stdout = None
        self._stdout_lock = threading.Lock()
        self._stopping = False
        self._parent_pid = parent_pid

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

            proc = self._start_command(request_id, command, subprocess.PIPE)

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
            proc = self._start_command(request_id, command, subprocess.STDOUT)

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

    def _start_command(self, request_id: str, command: List[str], stderr: Any):
        # Admission and registration share the shutdown lock: a worker cannot
        # create an untracked child after shutdown snapshots active jobs.
        with self._jobs_lock:
            if self._stopping or SHUTDOWN_REQUESTED.is_set():
                raise RuntimeError("Daemon is shutting down")
            proc = subprocess.Popen(
                command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=stderr, text=True,
            )
            self._active_jobs[request_id] = proc
            return proc

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
        """Exit when the GUI parent dies.

        Linux uses prctl(PR_SET_PDEATHSIG). macOS (and a Linux fallback when
        ``--parent-pid`` is passed) watches that pid with kqueue or polling,
        because ``sudo`` is the daemon's immediate parent rather than the GUI.
        """
        if sys.platform == "linux":
            self._install_linux_pdeathsig()
        if self._parent_pid:
            self._watch_parent_pid(self._parent_pid)

    def _install_linux_pdeathsig(self) -> None:
        """Register PR_SET_PDEATHSIG and exit if the parent is already gone."""
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

            if os.getppid() == 1:
                logger.error("Parent process already gone (ppid=1); exiting")
                sys.exit(1)
        except Exception as e:
            logger.warning(f"Could not install parent death signal: {e}")

    def _watch_parent_pid(self, parent_pid: int) -> None:
        """Shut down when *parent_pid* exits (kqueue on Darwin, else poll)."""
        if parent_process_gone(parent_pid):
            logger.error("GUI parent %s already gone; exiting", parent_pid)
            sys.exit(1)

        def _watch() -> None:
            if sys.platform == "darwin":
                try:
                    kqueue_wait_for_exit(parent_pid)
                    if not SHUTDOWN_REQUESTED.is_set():
                        logger.info("GUI parent %s exited; shutting down", parent_pid)
                        os.kill(os.getpid(), signal.SIGTERM)
                    return
                except Exception as e:
                    logger.warning("kqueue parent watch failed (%s); polling", e)
            while not SHUTDOWN_REQUESTED.is_set():
                if parent_process_gone(parent_pid):
                    logger.info("GUI parent %s gone; shutting down", parent_pid)
                    try:
                        os.kill(os.getpid(), signal.SIGTERM)
                    except OSError:
                        SHUTDOWN_REQUESTED.set()
                    return
                time.sleep(1.0)

        threading.Thread(target=_watch, name="ParentDeathWatch", daemon=True).start()

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

        self._serve_pipe(sys.stdin.buffer.fileno())
        self.shutdown()

    def _dispatch_pipe_request(self, request: Dict[str, Any]) -> None:
        if request.get('operation') in (OPERATION_CANCEL, OPERATION_SHUTDOWN, 'ping'):
            self._handle_async_pipe_request(request)
        else:
            self.executor.submit(self._handle_async_pipe_request, request)

    def _serve_pipe(self, fd: int) -> None:
        """Read OS bytes directly and dispatch every complete JSON line."""
        pending = b''
        while not SHUTDOWN_REQUESTED.is_set():
            try:
                r, _, _ = select.select([fd], [], [], 1.0)
                if not r:
                    continue

                chunk = os.read(fd, 65536)
                if not chunk:
                    logger.info("Pipe EOF reached, shutting down")
                    break

                pending += chunk
                while b'\n' in pending:
                    line, pending = pending.split(b'\n', 1)
                    self._dispatch_pipe_request(deserialize_message(line))
                    if SHUTDOWN_REQUESTED.is_set():
                        break

            except Exception as e:
                logger.error(f"Error in pipe mode loop: {e}", exc_info=True)
                break

    def shutdown(self):
        """Shutdown the daemon gracefully."""
        logger.info("Shutting down daemon...")

        with self._jobs_lock:
            self._stopping = True
            active_ids = list(self._active_jobs)
        # Cancel queued commands before stopping running children.
        self.executor.shutdown(wait=False, cancel_futures=True)
        for request_id in active_ids:
            self._handle_cancel({'target_id': request_id})

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

    uid, gid, parent_pid = parse_daemon_argv(argv)
    if uid is not None:
        logger.info("Parsed UID from command line: %s", uid)
    if gid is not None:
        logger.info("Parsed GID from command line: %s", gid)
    if parent_pid is not None:
        logger.info("Parsed parent PID from command line: %s", parent_pid)

    if uid is not None and 'PKEXEC_UID' not in os.environ and 'SUDO_UID' not in os.environ:
        os.environ['PKEXEC_UID'] = str(uid)
        os.environ['SUDO_UID'] = str(uid)
    if gid is not None and 'PKEXEC_GID' not in os.environ and 'SUDO_GID' not in os.environ:
        os.environ['PKEXEC_GID'] = str(gid)
        os.environ['SUDO_GID'] = str(gid)

    try:
        print(
            f"[Daemon] Initializing daemon with UID: {uid}, GID: {gid}, parent: {parent_pid}",
            file=sys.stderr,
            flush=True,
        )
        daemon = PrivilegedDaemon(parent_pid=parent_pid)
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


__all__ = [
    'PrivilegedDaemon',
    'run_daemon',
    'parse_daemon_argv',
    'parent_process_gone',
    'kqueue_wait_for_exit',
]
