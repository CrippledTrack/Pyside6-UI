"""Desired-behavior tests for overlapping-ownership fixes (rc-5)."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, List

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from GUI.app.constants import GUI_API_VERSION
from GUI.app.daemon.client import DaemonClient
from GUI.app.services.container import ServiceContainer
from GUI.app.services.interfaces import ISettingsService
from GUI.app.services.notification_service import NotificationService
from GUI.app.services.plugin_service import PluginService
from GUI.app.services.settings_service import SettingsService
from GUI.app.ui.controllers.plugin_controller import PluginController
from GUI.app.ui.qt.tab_loader import TabLoaderThread
from GUI.app.utils.imports import merge_constants
from GUI.plugin_system.base import BaseTabPlugin
from GUI.plugin_system.registry import PluginRegistry
from GUI.tests.test_plugin_lifecycle import _probe


def _controller(tmp_path: Path) -> tuple[PluginController, PluginService]:
    settings = SettingsService(settings_file=tmp_path / "settings.json")
    svc = PluginService(settings_service=settings, registry=PluginRegistry())
    container = ServiceContainer()
    container.register_singleton(ISettingsService, settings)
    container.register_singleton(PluginService, svc)
    svc.bind_container(container)
    return PluginController(container), svc


def _ensure_qapp() -> Any:
    from GUI.app.ui.qt.bindings import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_tab_loader_success_signal_is_not_native_finished() -> None:
    assert "load_complete" in TabLoaderThread.__dict__
    assert "finished" not in TabLoaderThread.__dict__
    from GUI.app.ui.qt.bindings import QThread

    assert TabLoaderThread.finished is QThread.finished


def test_toggle_already_enabled_is_noop(_isolate_host_paths: Path) -> None:
    controller, svc = _controller(_isolate_host_paths)
    svc.register_plugin(_probe("Toggle", plugin_id="gui.toggle"))
    events: List[tuple[str, bool]] = []
    controller.add_plugin_toggled_listener(lambda name, enabled: events.append((name, enabled)))
    assert svc.is_enabled("gui.toggle") is True
    assert controller.toggle_plugin("gui.toggle", True) is True
    assert events == []


def test_disable_runs_shutdown_before_unload(_isolate_host_paths: Path) -> None:
    hooks: List[str] = []

    class ServicePlugin(_probe("Service", plugin_id="gui.svc")):
        def on_application_start(self, container: Any) -> None:
            hooks.append("start")

        def on_application_shutdown(self) -> None:
            hooks.append("shutdown")
            assert svc.has_plugin_instance("gui.svc")

        def on_plugin_disabled(self) -> None:
            hooks.append("disabled")

        def _cleanup_plugin_resources(self) -> None:
            hooks.append("cleanup")

    controller, svc = _controller(_isolate_host_paths)
    svc.register_plugin(ServicePlugin)
    instance = svc.get_plugin_instance("gui.svc")
    controller._host._started_services.add("gui.svc")
    instance.on_application_start(controller.container)
    assert controller.toggle_plugin("gui.svc", False) is True
    assert hooks == ["start", "shutdown", "disabled", "cleanup"]
    assert svc.has_plugin_instance("gui.svc") is False
    assert controller.toggle_plugin("gui.svc", False) is True


def test_remove_tab_without_bar_entry_disposes_views() -> None:
    _ensure_qapp()
    from GUI.app.ui.qt.bindings import QTabWidget, QWidget
    from GUI.app.ui.qt.controllers.tab_controller import TabController

    class _Admin:
        def needs_admin_for_plugin(self, _requires_admin: bool) -> bool:
            return False

    svc = PluginService(registry=PluginRegistry())
    tabs = QTabWidget()
    controller = TabController(tabs, _Admin(), None, svc)
    placeholder = QWidget()
    view = QWidget()
    controller.loaded_tabs["gui.example"] = {
        "plugin_class": _probe("Example", plugin_id="gui.example"),
        "widget": view,
        "placeholder": placeholder,
    }
    controller.remove_tab("gui.example")
    assert "gui.example" not in controller.loaded_tabs


def test_add_tab_skips_duplicate_plugin_id() -> None:
    _ensure_qapp()
    from GUI.app.ui.qt.bindings import QTabWidget
    from GUI.app.ui.qt.controllers.tab_controller import TabController

    class _Admin:
        def needs_admin_for_plugin(self, _requires_admin: bool) -> bool:
            return False

    svc = PluginService(registry=PluginRegistry())
    tabs = QTabWidget()
    controller = TabController(tabs, _Admin(), None, svc)
    plugin = _probe("Example", plugin_id="gui.example")
    controller.add_tab("gui.example", plugin)
    controller.add_tab("gui.example", plugin)
    assert tabs.count() == 1
    assert list(controller.loaded_tabs) == ["gui.example"]
    assert "widget" in controller.loaded_tabs["gui.example"]


def test_theme_refresh_without_popup_is_quiet(_isolate_host_paths: Path, caplog) -> None:
    import logging

    _ensure_qapp()
    from GUI.app.ui.qt.bindings import QMainWindow
    from GUI.app.ui.qt.controllers.status_bar_manager import StatusBarManager
    from GUI.app.ui.qt.themes.theme_manager import ThemeManager

    window = QMainWindow()
    theme = ThemeManager(
        themes_dir=str(_isolate_host_paths / "themes"),
        settings_service=None,
    )
    manager = StatusBarManager(
        window.statusBar(),
        NotificationService(),
        theme,
        parent=window,
    )
    with caplog.at_level(logging.DEBUG):
        manager.refresh_theme()
    assert "does not exist" not in caplog.text
    assert manager._notification_widget is None


def test_clear_unopened_tabs_does_not_log_deleted_placeholder(caplog) -> None:
    import logging

    _ensure_qapp()
    from GUI.app.ui.qt.bindings import QTabWidget
    from GUI.app.ui.qt.controllers.tab_controller import TabController

    class _Admin:
        def needs_admin_for_plugin(self, _requires_admin: bool) -> bool:
            return False

    svc = PluginService(registry=PluginRegistry())
    tabs = QTabWidget()
    controller = TabController(tabs, _Admin(), None, svc)
    plugin = _probe("Shortcuts", plugin_id="gui.example.shortcuts")
    controller.add_tab("gui.example.shortcuts", plugin)
    with caplog.at_level(
        logging.DEBUG, logger="GUI.app.ui.qt.controllers.tab_controller"
    ):
        controller.clear_all_tabs()
    assert "already deleted" not in caplog.text
    assert controller.loaded_tabs == {}
    assert tabs.count() == 0


def test_custom_theme_is_not_replaced_by_builtin_factory(_isolate_host_paths: Path) -> None:
    _ensure_qapp()
    from GUI.app.ui.qt.themes.theme_manager import ThemeManager

    themes_dir = _isolate_host_paths / "themes"
    manager = ThemeManager(themes_dir=str(themes_dir), settings_service=None)
    pending_before = len(manager._theme_factories)
    custom = {
        "name": "Custom dark",
        "palette": {"background": "#010101", "foreground": "#fafafa"},
        "stylesheet": "QWidget { background: #010101; }",
    }
    assert manager.save_custom_theme("dark", custom) is True
    assert manager.get_theme_data("dark")["name"] == "Custom dark"
    snapshot = dict(manager.themes)
    assert snapshot["dark"]["name"] == "Custom dark"
    assert manager.get_theme_data("dark")["name"] == "Custom dark"
    assert len(manager._theme_factories) == pending_before - 1
    assert manager.has_theme("light") is True
    assert "light" in manager._theme_factories


def test_notification_center_unsubscribes_on_destroy(_isolate_host_paths: Path) -> None:
    _ensure_qapp()
    from GUI.app.ui.qt.themes.theme_manager import ThemeManager
    from GUI.app.ui.qt.widgets.notification_center import NotificationCenterWidget

    service = NotificationService()
    manager = ThemeManager(
        themes_dir=str(_isolate_host_paths / "themes"),
        settings_service=None,
    )
    widget = NotificationCenterWidget(service, manager)
    assert len(service._added_subscribers) == 1
    widget.close()
    widget.deleteLater()
    _ensure_qapp().processEvents()
    assert service._added_subscribers == []


class _BlockingPipe:
    def __init__(self) -> None:
        self._released = threading.Event()

    def readline(self) -> bytes:
        self._released.wait(timeout=30)
        return b""

    def close(self) -> None:
        self._released.set()


class _FakeProcess:
    def __init__(self) -> None:
        self.stdout = _BlockingPipe()
        self.stdin = None
        self._code = None

    def poll(self) -> int | None:
        return self._code


def test_daemon_stop_reader_unblocks_before_replacement() -> None:
    process = _FakeProcess()
    client = DaemonClient(process)
    thread = client._reader_thread
    assert thread is not None and thread.is_alive()
    assert client._stop_reader(timeout=2.0) is True
    assert thread.is_alive() is False
    client._start_reader_thread()
    replacement = client._reader_thread
    assert replacement is not None and replacement is not thread
    client._stop_reader(timeout=2.0)


def test_merge_constants_protects_gui_api_version() -> None:
    runtime = merge_constants(apply_launch_overrides=True)
    build = merge_constants(apply_launch_overrides=False)
    assert runtime["GUI_API_VERSION"] == GUI_API_VERSION
    assert build["GUI_API_VERSION"] == GUI_API_VERSION
    assert runtime["CURRENT_PLATFORM"] == build["CURRENT_PLATFORM"]


def test_timed_out_ping_does_not_consume_later_line() -> None:
    import socket

    from GUI.app.daemon.pipe_io import ping_pipe
    from GUI.app.daemon.protocol import serialize_message

    req_server, req_client = socket.socketpair()
    resp_server, resp_client = socket.socketpair()
    stdin = req_client.makefile("wb", buffering=0)
    stdout = resp_client.makefile("rb", buffering=0)
    try:
        assert ping_pipe(stdin, stdout, timeout=0.2) is False
        resp_server.sendall(
            serialize_message({"id": "cmd-1", "success": True, "result": "output"})
        )
        line = stdout.readline()
        assert b"cmd-1" in line
    finally:
        stdin.close()
        stdout.close()
        for sock in (req_server, req_client, resp_server, resp_client):
            sock.close()


def test_client_for_process_never_wraps_twice() -> None:
    from GUI.app.daemon import client_for_process, peek_daemon_client, set_daemon_client

    first = object()
    set_daemon_client(first)
    try:
        assert client_for_process(object()) is first
        assert peek_daemon_client() is first
    finally:
        set_daemon_client(None)


def test_client_for_process_skips_closed_stdout() -> None:
    import io

    from GUI.app.daemon import client_for_process, set_daemon_client
    from GUI.app.daemon.pipe_io import process_stdout_usable

    class Proc:
        def __init__(self) -> None:
            self.stdout = io.BytesIO()
            self.stdout.close()

        def poll(self) -> None:
            return None

    proc = Proc()
    assert process_stdout_usable(proc) is False
    set_daemon_client(None)
    try:
        assert client_for_process(proc) is None
    finally:
        set_daemon_client(None)


def test_theme_dialog_apply_uses_callback_result(
    _isolate_host_paths: Path, monkeypatch
) -> None:
    _ensure_qapp()
    from GUI.app.ui.qt.dialogs.theme_dialog import ThemeDialog, QMessageBox
    from GUI.app.ui.qt.themes.theme_manager import ThemeManager

    boxes: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda *args, **kwargs: boxes.append("ok")
    )
    monkeypatch.setattr(
        QMessageBox, "critical", lambda *args, **kwargs: boxes.append("err")
    )

    manager = ThemeManager(
        themes_dir=str(_isolate_host_paths / "themes"),
        settings_service=None,
    )
    manager.load_builtin_themes()
    manager.current_theme = "dark"
    calls: list[str] = []

    def apply(name: str) -> bool:
        calls.append(name)
        return False

    dialog = ThemeDialog(
        theme_manager=manager,
        settings_service=SettingsService(settings_file=_isolate_host_paths / "s.json"),
        apply_callback=apply,
    )
    for i in range(dialog.theme_list.count()):
        item = dialog.theme_list.item(i)
        if dialog._theme_key(item) == "dark":
            dialog.theme_list.setCurrentItem(item)
            break
    dialog.apply_selected_theme()
    assert calls == ["dark"]
    assert boxes == ["err"]
    assert manager.get_current_theme() == "dark"


def test_failed_lazy_load_records_error_placeholder() -> None:
    _ensure_qapp()
    from GUI.app.ui.qt.bindings import QTabWidget
    from GUI.app.ui.qt.controllers.tab_controller import TabController
    from GUI.app.ui.qt.widgets.error_placeholder import ErrorPlaceholder

    class _Admin:
        def needs_admin_for_plugin(self, _requires_admin: bool) -> bool:
            return False

    class Boom(_probe("Boom", plugin_id="gui.boom")):
        def create_tab_content(self, context: Any) -> Any:
            raise RuntimeError("boom")

    svc = PluginService(registry=PluginRegistry())
    svc.bind_container(type("C", (), {"get": lambda self, _t: None})())
    tabs = QTabWidget()
    controller = TabController(tabs, _Admin(), None, svc)
    svc.register_plugin(Boom)
    controller.add_tab("gui.boom", Boom)
    if controller.loaded_tabs["gui.boom"].get("widget") is None:
        controller.on_tab_changed(controller.index_for_plugin("gui.boom"))
    tab_info = controller.loaded_tabs["gui.boom"]
    assert isinstance(tab_info["widget"], ErrorPlaceholder)
