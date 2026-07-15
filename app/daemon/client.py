"""Daemon client for communicating with the privileged pipe daemon."""

from __future__ import annotations

import queue
import logging
import threading
import subprocess
import time
from dataclasses import dataclass
from typing import Callable, Dict, Any, Optional
from .protocol import create_request, serialize_message, deserialize_message

logger = logging.getLogger(__name__)


class DaemonConnectionError(Exception):
    """Raised when daemon connection fails."""
    pass


class DaemonTimeoutError(Exception):
    """Raised when daemon operation times out."""
    pass


@dataclass
class StreamRequestHandle:
    """Handle for a streaming request (exposes request_id for cancel)."""

    request_id: str


class DaemonClient:
    """Client for communicating with the privileged pipe daemon over stdin/stdout."""

    CONNECT_TIMEOUT = 5.0
    OPERATION_TIMEOUT = 30.0

    def __init__(self, process: subprocess.Popen):
        if process is None:
            raise ValueError("DaemonClient requires a subprocess.Popen process")

        self._process = process
        self._lock = threading.Lock()
        self._connected = True
        self._pending_requests: Dict[str, queue.Queue] = {}
        self._pending_lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._reader_running = False
        self._reader_thread: Optional[threading.Thread] = None
        self._stream_callbacks: Dict[str, Callable[[str], None]] = {}
        self._stream_activity: Dict[str, float] = {}
        self._stream_callbacks_lock = threading.Lock()
        self._start_reader_thread()
    def is_connected(self) -> bool:
        """Check if client is connected to daemon."""
        return self._connected and self._process.poll() is None

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
                    if response.get('status') == 'running':
                        with self._stream_callbacks_lock:
                            callback = self._stream_callbacks.get(resp_id)
                            if resp_id in self._stream_activity:
                                self._stream_activity[resp_id] = time.monotonic()
                        if callback:
                            try:
                                callback(response.get('chunk', ''))
                            except Exception as e:
                                logger.warning(f"Stream callback error for {resp_id}: {e}")
                        else:
                            logger.debug(f"Streaming chunk for {resp_id} but no callback registered, discarding")
                        continue

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
            with self._pending_lock:
                for rid, q in self._pending_requests.items():
                    q.put(None)
                self._pending_requests.clear()
            with self._stream_callbacks_lock:
                self._stream_callbacks.clear()
            logger.info("Pipe reader loop exited")

    def connect(self, timeout: float = None) -> bool:
        """Verify the daemon process is still alive and ensure the reader is running."""
        with self._lock:
            self._connected = self._process.poll() is None
            if self._connected:
                self._start_reader_thread()
            return self._connected

    def disconnect(self):
        """Disconnect from daemon and terminate the process."""
        with self._lock:
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
            if self._reader_thread is not None:
                self._reader_thread.join(timeout=2.0)
                self._reader_thread = None
            self._connected = False
            logger.info("Disconnected from pipe daemon")

    def _send_recv(
        self,
        message: bytes,
        expected_id: Optional[str] = None,
        timeout: float = None,
        *,
        idle_timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Send message and receive response.

        Args:
            message: Serialized request bytes.
            expected_id: Request id used to match the response.
            timeout: Absolute wait for a non-streaming response (defaults to OPERATION_TIMEOUT).
            idle_timeout: When set, wait for the final response using an idle timeout
                that resets whenever streaming activity is recorded for ``expected_id``.
        """
        if timeout is None and idle_timeout is None:
            timeout = self.OPERATION_TIMEOUT

        if not self.is_connected():
            raise DaemonConnectionError("Not connected to daemon")

        q: queue.Queue = queue.Queue()
        with self._pending_lock:
            self._pending_requests[expected_id] = q

        try:
            with self._write_lock:
                self._process.stdin.write(message)
                self._process.stdin.flush()

            if idle_timeout is None:
                try:
                    response = q.get(timeout=timeout)
                except queue.Empty:
                    raise DaemonTimeoutError(
                        f"Operation timed out after {timeout} seconds"
                    )
            else:
                poll = min(1.0, max(0.1, idle_timeout / 10.0))
                while True:
                    with self._stream_callbacks_lock:
                        last = self._stream_activity.get(expected_id, time.monotonic())
                    elapsed_idle = time.monotonic() - last
                    if elapsed_idle >= idle_timeout:
                        raise DaemonTimeoutError(
                            f"Stream idle timed out after {idle_timeout} seconds"
                        )
                    try:
                        response = q.get(timeout=min(poll, idle_timeout - elapsed_idle))
                        break
                    except queue.Empty:
                        continue

            if response is None:
                raise DaemonConnectionError(
                    "Connection closed by daemon (pipe EOF)"
                )
            return response
        finally:
            with self._pending_lock:
                self._pending_requests.pop(expected_id, None)

    def request(self, operation: str, params: Dict[str, Any],
                timeout: float = None) -> Dict[str, Any]:
        """Send a request to daemon and return response."""
        if not self.is_connected():
            if not self.connect():
                raise DaemonConnectionError("Could not connect to daemon")

        request = create_request(operation, params)
        message = serialize_message(request)

        last_error = None
        retries = 2
        for attempt in range(retries):
            try:
                response = self._send_recv(message, expected_id=request['id'], timeout=timeout)

                if response.get('id') != request['id']:
                    logger.warning(f"Response ID mismatch: {request['id']} != {response.get('id')}")

                return response

            except DaemonConnectionError as e:
                last_error = e
                if operation == 'shutdown':
                    logger.info(f"Connection closed during shutdown request (expected): {e}")
                else:
                    logger.warning(f"Connection error (attempt {attempt + 1}/{retries}): {e}")

                if attempt < retries - 1:
                    if self._restart_pipe_daemon():
                        message = serialize_message(request)
                        continue

                raise last_error

            except DaemonTimeoutError:
                raise
            except Exception as e:
                logger.error(f"Unexpected error in request: {str(e)}", exc_info=True)
                raise

    def request_stream(
        self,
        operation: str,
        params: Dict[str, Any],
        on_chunk: Callable[[str], None],
        timeout: float = None,
        on_started: Optional[Callable[[StreamRequestHandle], None]] = None,
    ) -> Dict[str, Any]:
        """Send a streaming request to the daemon.

        Like request(), but for operations that produce incremental output
        (e.g. run_command_stream). The on_chunk callback is invoked for each
        intermediate line of output as it arrives from the daemon.

        ``timeout`` is an *idle* timeout: each received chunk resets the clock.
        ``on_started`` is called with a :class:`StreamRequestHandle` before the
        request is sent so callers can cancel via :meth:`cancel_request`.

        The final response (containing aggregated output and return code) is
        returned when the operation completes.
        """
        if not self.is_connected():
            if not self.connect():
                raise DaemonConnectionError("Could not connect to daemon")

        idle_timeout = self.OPERATION_TIMEOUT if timeout is None else float(timeout)
        request = create_request(operation, params)
        request_id = request['id']
        handle = StreamRequestHandle(request_id=request_id)
        message = serialize_message(request)

        if on_started is not None:
            try:
                on_started(handle)
            except Exception as e:
                logger.warning(f"on_started callback error for {request_id}: {e}")

        last_error: Optional[Exception] = None
        retries = 2
        for attempt in range(retries):
            with self._stream_callbacks_lock:
                self._stream_callbacks[request_id] = on_chunk
                self._stream_activity[request_id] = time.monotonic()

            active_id = request_id
            retry = False
            try:
                response = self._send_recv(
                    message,
                    expected_id=active_id,
                    idle_timeout=idle_timeout,
                )

                if response.get('id') != active_id:
                    logger.warning(f"Response ID mismatch: {active_id} != {response.get('id')}")

                return response

            except DaemonConnectionError as e:
                last_error = e
                logger.warning(f"Stream connection error (attempt {attempt + 1}/{retries}): {e}")
                retry = attempt < retries - 1 and self._restart_pipe_daemon()
            except DaemonTimeoutError:
                raise
            except Exception as e:
                logger.error(f"Unexpected error in request_stream: {e}", exc_info=True)
                raise
            finally:
                with self._stream_callbacks_lock:
                    self._stream_callbacks.pop(active_id, None)
                    self._stream_activity.pop(active_id, None)

            if not retry:
                assert last_error is not None
                raise last_error

            request = create_request(operation, params)
            request_id = request['id']
            handle.request_id = request_id
            message = serialize_message(request)
            if on_started is not None:
                try:
                    on_started(handle)
                except Exception as cb_err:
                    logger.warning(f"on_started callback error for {request_id}: {cb_err}")
            last_error = None

        assert last_error is not None
        raise last_error

    def cancel_request(self, target_id: str, timeout: float = 5.0) -> Dict[str, Any]:
        """Cancel a running request by its ID.

        Sends a cancel operation to the daemon, which will SIGTERM the
        subprocess associated with the given request ID (with a 2-second
        grace period before SIGKILL).
        """
        return self.request('cancel', {'target_id': target_id}, timeout=timeout)

    def _restart_pipe_daemon(self) -> bool:
        """Restart the pipe daemon after a crash or disconnection.

        Kills the old process (if still alive), spawns a new daemon via
        elevation_linux.start_daemon(), and re-establishes the reader loop.
        """
        logger.info("Attempting to restart pipe daemon...")

        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                self._process.wait(timeout=2.0)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass

        # Clear elevation global so start_daemon() will spawn a fresh process
        try:
            from ..utils.elevation_linux import clear_daemon_process
            clear_daemon_process()
        except Exception as e:
            logger.debug(f"clear_daemon_process failed: {e}")

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

            if isinstance(new_client, DaemonClient) and new_client is not self:
                new_client._reader_running = False
                if new_client._reader_thread:
                    new_client._reader_thread.join(timeout=2.0)
                self._process = new_client._process

            try:
                from ..utils.elevation_linux import set_daemon_process
                set_daemon_process(self._process)
            except Exception as e:
                logger.debug(f"set_daemon_process failed: {e}")

            self._connected = True
            with self._pending_lock:
                self._pending_requests = {}
            with self._stream_callbacks_lock:
                self._stream_callbacks = {}
                self._stream_activity = {}
            self._start_reader_thread()

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
        self._jobs_lock = threading.Lock()
        self._active_jobs: Dict[str, subprocess.Popen] = {}

    def is_connected(self) -> bool:
        return True

    def connect(self, timeout: float = None) -> bool:
        return True

    def disconnect(self):
        with self._jobs_lock:
            for proc in list(self._active_jobs.values()):
                try:
                    proc.terminate()
                except Exception:
                    pass
            self._active_jobs.clear()

    def request(self, operation: str, params: Dict[str, Any], timeout: float = None) -> Dict[str, Any]:
        import uuid
        request_id = str(uuid.uuid4())

        if operation == 'run_command':
            return self._run_local(request_id, params, stream=False, on_chunk=None)
        elif operation == 'run_command_stream':
            return self._run_local(request_id, params, stream=False, on_chunk=None)
        elif operation == 'cancel':
            return {
                'id': request_id,
                'success': True,
                'result': self._cancel_local(params.get('target_id')),
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

    def request_stream(
        self,
        operation: str,
        params: Dict[str, Any],
        on_chunk: Callable[[str], None],
        timeout: float = None,
        on_started: Optional[Callable[[StreamRequestHandle], None]] = None,
    ) -> Dict[str, Any]:
        import uuid
        request_id = str(uuid.uuid4())
        handle = StreamRequestHandle(request_id=request_id)
        if on_started is not None:
            try:
                on_started(handle)
            except Exception as e:
                logger.warning(f"on_started callback error for {request_id}: {e}")

        if operation not in ('run_command_stream', 'run_command'):
            return {
                'id': request_id,
                'success': False,
                'error': f"Unknown streaming operation: {operation}",
            }

        if timeout is not None and 'timeout' not in params:
            params = {**params, 'timeout': timeout}
        return self._run_local(request_id, params, stream=True, on_chunk=on_chunk)

    def cancel_request(self, target_id: str, timeout: float = 5.0) -> Dict[str, Any]:
        return self.request('cancel', {'target_id': target_id}, timeout=timeout)

    def _cancel_local(self, target_id: Optional[str]) -> Dict[str, Any]:
        if not target_id:
            return {'cancelled': False, 'target_id': target_id, 'reason': 'missing target_id'}
        with self._jobs_lock:
            proc = self._active_jobs.get(target_id)
        if proc is None:
            return {'cancelled': False, 'target_id': target_id, 'reason': 'not found'}
        try:
            proc.terminate()
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5.0)
            return {'cancelled': True, 'target_id': target_id}
        except Exception as e:
            return {'cancelled': False, 'target_id': target_id, 'reason': str(e)}

    def _run_local(
        self,
        request_id: str,
        params: Dict[str, Any],
        *,
        stream: bool,
        on_chunk: Optional[Callable[[str], None]],
    ) -> Dict[str, Any]:
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
            if not stream:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=cmd_timeout,
                )
                return {
                    'id': request_id,
                    'success': True,
                    'result': {
                        'returncode': result.returncode,
                        'stdout': result.stdout,
                        'stderr': result.stderr,
                        'success': result.returncode == 0,
                    },
                }

            proc = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            with self._jobs_lock:
                self._active_jobs[request_id] = proc

            stdout_lines: list[str] = []
            try:
                assert proc.stdout is not None
                deadline = None if cmd_timeout is None else time.monotonic() + float(cmd_timeout)
                while True:
                    if deadline is not None and time.monotonic() > deadline:
                        proc.kill()
                        raise subprocess.TimeoutExpired(command, cmd_timeout)
                    line = proc.stdout.readline()
                    if line == '' and proc.poll() is not None:
                        break
                    if line:
                        stdout_lines.append(line)
                        if on_chunk is not None:
                            on_chunk(line.rstrip('\n'))
                stderr = proc.stderr.read() if proc.stderr else ''
                returncode = proc.wait()
                return {
                    'id': request_id,
                    'success': True,
                    'result': {
                        'returncode': returncode,
                        'stdout': ''.join(stdout_lines),
                        'stderr': stderr or '',
                        'success': returncode == 0,
                    },
                }
            finally:
                with self._jobs_lock:
                    self._active_jobs.pop(request_id, None)

        except subprocess.TimeoutExpired as e:
            return {
                'id': request_id,
                'success': True,
                'result': {
                    'returncode': -1,
                    'stdout': '',
                    'stderr': f'Command timed out: {e}',
                    'success': False,
                },
            }
        except Exception as e:
            return {
                'id': request_id,
                'success': True,
                'result': {
                    'returncode': -1,
                    'stdout': '',
                    'stderr': str(e),
                    'success': False,
                },
            }

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


__all__ = [
    'DaemonClient',
    'DaemonConnectionError',
    'DaemonTimeoutError',
    'LocalDaemonClient',
    'StreamRequestHandle',
]
