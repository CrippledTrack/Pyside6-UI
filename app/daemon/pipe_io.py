"""One-shot pipe I/O helpers that never start a background reader."""

from __future__ import annotations

import select
from typing import Any

from .protocol import create_request, deserialize_message, serialize_message


def stdout_is_usable(stdout: Any) -> bool:
    """Return True if *stdout* can be selected and read."""
    if stdout is None:
        return False
    if getattr(stdout, "closed", False):
        return False
    try:
        stdout.fileno()
    except Exception:
        return False
    return True


def process_stdout_usable(process: Any) -> bool:
    """Return True if *process* still has an open stdout pipe."""
    if process is None:
        return False
    poll = getattr(process, "poll", None)
    if callable(poll):
        try:
            if poll() is not None:
                return False
        except Exception:
            return False
    return stdout_is_usable(getattr(process, "stdout", None))


def wait_readable(stream: Any, timeout: float) -> bool:
    """Wait until *stream* has data or *timeout* seconds elapse.

    Uses ``select`` so a timeout does not leave a blocked ``readline()``.
    """
    if not stdout_is_usable(stream):
        return False
    try:
        fd = stream.fileno()
        ready, _, _ = select.select([fd], [], [], max(0.0, timeout))
        return bool(ready)
    except (OSError, ValueError, TypeError):
        return False


def ping_pipe(stdin: Any, stdout: Any, timeout: float = 1.0) -> bool:
    """Send a ping and read one pong without a background reader thread.

    On timeout this does not call ``readline()``, so a later response stays
    in the pipe for the process's single attached reader.
    """
    if stdin is None or not stdout_is_usable(stdout):
        return False
    if getattr(stdin, "closed", False):
        return False

    message = serialize_message(create_request("ping", {}))
    try:
        stdin.write(message)
        stdin.flush()
    except Exception:
        return False

    if not wait_readable(stdout, timeout):
        return False
    try:
        line = stdout.readline()
    except Exception:
        return False
    if not line:
        return False
    try:
        response = deserialize_message(line)
    except Exception:
        return False
    return bool(response.get("success") and response.get("result") == "pong")


def ping_daemon_process(process: Any, timeout: float = 1.0) -> bool:
    """One-shot ping of a daemon process stdin/stdout pair."""
    if process is None:
        return False
    return ping_pipe(
        getattr(process, "stdin", None),
        getattr(process, "stdout", None),
        timeout=timeout,
    )


__all__ = [
    "ping_daemon_process",
    "ping_pipe",
    "process_stdout_usable",
    "stdout_is_usable",
    "wait_readable",
]
