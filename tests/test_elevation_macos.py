"""Privileged-daemon elevation helpers (no live sudo)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from GUI.app.daemon.server import parse_daemon_argv, parent_process_gone
from GUI.app.utils import elevation_macos as macos
from GUI.app.utils import privileged
from GUI.app.utils.elevation import privileged_action_copy, supports_privileged_daemon
from GUI.app.utils.elevation_macos import (
    ASKPASS_SCRIPT,
    sudo_askpass_command,
    sudo_askpass_env,
    write_askpass_script,
)
from GUI.app.utils.elevation_unix import build_daemon_command


def test_supports_privileged_daemon_platforms() -> None:
    assert supports_privileged_daemon("linux") is True
    assert supports_privileged_daemon("darwin") is True
    assert supports_privileged_daemon("windows") is False
    assert supports_privileged_daemon("freebsd") is False


def test_daemon_command_includes_pipe_uid_gid_parent(monkeypatch) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", "/tmp/fake-gui")
    monkeypatch.setattr(
        "GUI.app.utils.elevation_unix.get_effective_uid_gid",
        lambda: (501, 20),
    )
    monkeypatch.setattr(
        "GUI.app.utils.elevation_unix.os.getpid",
        lambda: 4242,
    )

    cmd = build_daemon_command()
    assert cmd is not None
    assert cmd[0] == "/tmp/fake-gui"
    assert "--pipe" in cmd
    uid_idx = cmd.index("--uid")
    assert cmd[uid_idx + 1] == "501"
    gid_idx = cmd.index("--gid")
    assert cmd[gid_idx + 1] == "20"
    parent_idx = cmd.index("--parent-pid")
    assert cmd[parent_idx + 1] == "4242"


def test_macos_sudo_askpass_prefix_and_env(tmp_path: Path) -> None:
    daemon_cmd = ["/usr/bin/python3", "--pipe", "--uid", "501", "--parent-pid", "9"]
    argv = sudo_askpass_command(daemon_cmd)
    assert argv[:3] == ["sudo", "-A", "-E"]
    assert argv[3:] == daemon_cmd

    askpass = write_askpass_script(str(tmp_path / "askpass.sh"))
    env = sudo_askpass_env({"PATH": "/usr/bin"}, askpass)
    assert env["SUDO_ASKPASS"] == askpass
    assert os.access(askpass, os.X_OK)
    body = Path(askpass).read_text(encoding="utf-8")
    assert "osascript" in body
    assert "display dialog" in ASKPASS_SCRIPT
    assert "with hidden answer" in ASKPASS_SCRIPT
    # Cancel must fail loudly instead of printing an empty password.
    assert "error number 1" in ASKPASS_SCRIPT
    assert "2>/dev/null" not in ASKPASS_SCRIPT


def test_facade_selects_macos_spawn_on_darwin(monkeypatch) -> None:
    import GUI.app.utils.elevation as elevation

    monkeypatch.setattr(elevation, "CURRENT_PLATFORM", "darwin")
    sentinel = object()

    class _Mac:
        @staticmethod
        def spawn_daemon_process():
            return sentinel

    monkeypatch.setattr(elevation, "_backend", lambda: _Mac)
    assert elevation.spawn_daemon_process() is sentinel


def test_parse_daemon_argv_parent_pid() -> None:
    uid, gid, parent = parse_daemon_argv(
        ["--pipe", "--uid", "501", "--gid", "20", "--parent-pid", "99"]
    )
    assert uid == 501
    assert gid == 20
    assert parent == 99


def test_parent_process_gone_current_pid() -> None:
    assert parent_process_gone(os.getpid()) is False
    assert parent_process_gone(1) is True
    assert parent_process_gone(-1) is True


def test_pipe_bootstrap_allowed_on_darwin(monkeypatch) -> None:
    from GUI.app import app as app_mod

    seen = {}

    def fake_run_daemon(argv):
        seen["argv"] = argv
        return 17

    monkeypatch.setattr(
        "GUI.app.utils.elevation.supports_privileged_daemon",
        lambda: True,
    )
    monkeypatch.setattr(
        "GUI.app.daemon.server.run_daemon",
        fake_run_daemon,
    )
    assert app_mod.run(["prog", "--pipe", "--uid", "1"]) == 17
    assert seen["argv"][1] == "--pipe"


def test_admin_factory_unix_on_darwin(monkeypatch) -> None:
    import GUI.app.services.admin_service as admin_mod
    from GUI.app.services.admin_service import AdminService, UnixAdminService

    monkeypatch.setattr(admin_mod, "CURRENT_PLATFORM", "darwin")
    monkeypatch.setattr(
        "GUI.app.utils.elevation.get_sudo_status",
        lambda: {
            "is_admin": False,
            "current_user": "tester",
            "current_group": "staff",
            "sudo_available": True,
            "pkexec_available": False,
            "can_elevate": True,
        },
    )
    service = AdminService()
    assert isinstance(service, UnixAdminService)
    assert service.is_admin() is False


def test_placeholder_copy_daemon_vs_relaunch() -> None:
    desc, btn = privileged_action_copy(True)
    assert "privileged daemon" in desc.lower()
    assert btn == "Start Privileged Daemon"
    desc, btn = privileged_action_copy(False)
    assert "restart" in desc.lower()
    assert btn == "Restart as Administrator"


def test_stat_and_chown_on_darwin(monkeypatch) -> None:
    monkeypatch.setattr(privileged.sys, "platform", "darwin")
    assert privileged._stat_ownership_command("/tmp/x") == [
        "stat",
        "-f",
        "%OLp %u %g",
        "/tmp/x",
    ]
    assert privileged._default_chown_spec() == "0:0"

    captured: list[list[str]] = []

    class _Result:
        returncode = 0
        stdout = "644 501 20"
        stderr = ""

    def fake_run(command, timeout=10):
        captured.append(list(command))
        if command[0] == "stat":
            return _Result()
        return _Result()

    monkeypatch.setattr(privileged, "run_privileged_command", fake_run)
    assert privileged.write_privileged_file("/tmp/priv-test", "hello") is True
    assert captured[0][:3] == ["stat", "-f", "%OLp %u %g"]
    chowns = [c for c in captured if c[0] == "chown"]
    assert chowns
    assert chowns[0][1] == "501:20"


def test_stat_gnu_on_non_darwin(monkeypatch) -> None:
    monkeypatch.setattr(privileged.sys, "platform", "linux")
    assert privileged._stat_ownership_command("/etc/x")[1] == "-c"


def test_failed_spawn_removes_askpass_helper(monkeypatch) -> None:
    """A cancelled prompt must not leave the executable helper on disk."""

    class _FakeProc:
        pid = 4242

    monkeypatch.setattr(macos.unix, "existing_usable_daemon", lambda: None)
    monkeypatch.setattr(macos, "check_sudo_available", lambda: True)
    monkeypatch.setattr(macos.unix, "build_daemon_command", lambda: ["python", "--pipe"])
    monkeypatch.setattr(macos.unix, "build_daemon_env", lambda: {})
    monkeypatch.setattr(macos.subprocess, "Popen", lambda *a, **k: _FakeProc())
    # finalize returns None when sudo dies before the ping succeeds.
    monkeypatch.setattr(macos.unix, "finalize_spawned_process", lambda proc: None)

    assert macos.spawn_daemon_process() is None
    assert macos._askpass_path is None


class _FakeAdminService:
    def is_admin(self) -> bool:
        return False


class _FakeDaemonService:
    def __init__(self, available: bool = False) -> None:
        self._available = available

    def is_available(self) -> bool:
        return self._available


class _FakeSettingsService:
    def get_hide_admin_menu(self) -> bool:
        return False

    def get_show_tooltips(self) -> bool:
        return False


def _menu_controller(daemon_available: bool) -> Any:
    from GUI.app.ui.qt.bindings import QApplication, QMainWindow
    from GUI.app.ui.qt.controllers.menu_bar_controller import MenuBarController

    if QApplication.instance() is None:
        QApplication([])
    window = QMainWindow()
    controller = MenuBarController(
        menu_bar=window.menuBar(),
        admin_service=_FakeAdminService(),
        daemon_service=_FakeDaemonService(daemon_available),
        settings_service=_FakeSettingsService(),
        parent_widget=window,
    )
    controller._window_ref = window  # keep the window alive for the assertions
    return controller


def _noop() -> None:
    return None


def test_admin_menu_starts_daemon_on_unix() -> None:
    """Linux/macOS get the daemon action, not the Windows relaunch action."""
    from GUI.app.utils.elevation import supports_privileged_daemon

    controller = _menu_controller(daemon_available=False)
    controller.setup(_noop, _noop, _noop)
    action = controller.restart_admin_action
    assert action is not None
    if supports_privileged_daemon():
        assert action.text() == "Start Privileged Daemon"
        assert action.isEnabled() is True
    else:
        assert action.text() == "Restart as Administrator"


def test_admin_menu_reports_running_daemon() -> None:
    from GUI.app.utils.elevation import supports_privileged_daemon

    if not supports_privileged_daemon():
        return
    controller = _menu_controller(daemon_available=True)
    controller.setup(_noop, _noop, _noop)
    assert controller.restart_admin_action.text() == "Daemon Running"
    assert controller.restart_admin_action.isEnabled() is False


def test_admin_placeholder_uses_daemon_copy() -> None:
    from GUI.app.ui.qt.bindings import QApplication
    from GUI.app.ui.qt.widgets.admin_required_placeholder import (
        AdminRequiredPlaceholder,
    )
    from GUI.app.utils.elevation import privileged_action_copy, supports_privileged_daemon

    if QApplication.instance() is None:
        QApplication([])
    placeholder = AdminRequiredPlaceholder("Probe")
    _, expected_button = privileged_action_copy(supports_privileged_daemon())
    assert placeholder._btn.text() == expected_button


def test_privileged_probe_sample_is_a_tab_plugin() -> None:
    from GUI.plugin_system.base import BaseTabPlugin
    from GUI.plugins.privileged_probe_plugin import PrivilegedProbePlugin

    assert issubclass(PrivilegedProbePlugin, BaseTabPlugin)
    assert PrivilegedProbePlugin.plugin_id == "gui.example.privileged"
    assert PrivilegedProbePlugin.requires_admin is True
    assert "macOS" in PrivilegedProbePlugin.supported_platforms
    # Sample plugins must stay host-agnostic.
    assert "cyberpatriot" not in PrivilegedProbePlugin.plugin_id.lower()
