"""Privileged helper smoke tests with a local (in-process) daemon client."""

from __future__ import annotations

import sys

from GUI.app.daemon.client import LocalDaemonClient
from GUI.app.utils import privileged


def test_run_privileged_command_with_local_client(monkeypatch) -> None:
    client = LocalDaemonClient()
    monkeypatch.setattr(
        "GUI.app.daemon.get_daemon_client",
        lambda: client,
    )

    import GUI.app.daemon as daemon_mod

    monkeypatch.setattr(daemon_mod, "get_daemon_client", lambda: client)

    cmd = [sys.executable, "-c", "print('ok', end='')"]
    result = privileged.run_privileged_command(cmd, timeout=10)
    assert result.returncode == 0
    assert "ok" in (result.stdout or "")
