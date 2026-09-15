"""Daemon protocol serialize/parse smoke tests (no live daemon)."""

from __future__ import annotations

import sys

from GUI.app.daemon.protocol import (
    create_request,
    create_response,
    create_stream_chunk,
    serialize_message,
    deserialize_message,
    OPERATION_RUN_COMMAND,
    OPERATION_RUN_COMMAND_STREAM,
    OPERATION_CANCEL,
)
from GUI.app.daemon.client import LocalDaemonClient

# ``echo`` is a shell builtin on Windows; use the interpreter for a real argv.
_HELLO_CMD = [sys.executable, "-c", "print('hello-local', end='')"]
_STREAM_CMD = [sys.executable, "-c", "print('stream-line', end='')"]


def test_request_roundtrip() -> None:
    req = create_request(OPERATION_RUN_COMMAND_STREAM, {"command": ["echo", "hi"]})
    raw = serialize_message(req)
    back = deserialize_message(raw)
    assert back["operation"] == OPERATION_RUN_COMMAND_STREAM
    assert back["params"]["command"] == ["echo", "hi"]
    assert "id" in back


def test_stream_chunk_shape() -> None:
    chunk = create_stream_chunk("abc-123", "line one")
    assert chunk["id"] == "abc-123"
    assert chunk["status"] == "running"
    assert chunk["chunk"] == "line one"
    assert chunk["success"] is True


def test_response_error_shape() -> None:
    resp = create_response("id-1", False, error="boom")
    assert resp["success"] is False
    assert resp["error"] == "boom"


def test_local_client_run_command() -> None:
    """LocalDaemonClient supports run_command without a live elevated daemon."""
    client = LocalDaemonClient()
    response = client.request(
        OPERATION_RUN_COMMAND,
        {"command": _HELLO_CMD},
    )
    assert response.get("success") is True
    result = response.get("result") or {}
    assert result.get("returncode") == 0
    assert "hello-local" in str(result.get("stdout", ""))


def test_local_client_cancel_and_stream() -> None:
    client = LocalDaemonClient()
    chunks: list[str] = []
    response = client.request_stream(
        OPERATION_RUN_COMMAND_STREAM,
        {"command": _STREAM_CMD},
        on_chunk=chunks.append,
    )
    assert response.get("success") is True
    assert any("stream-line" in c for c in chunks) or "stream-line" in str(
        (response.get("result") or {}).get("stdout", "")
    )
    cancel = client.cancel_request("missing-id")
    assert cancel.get("success") is True
    assert cancel.get("result", {}).get("cancelled") is False
