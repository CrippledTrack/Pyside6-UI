"""macOS platform conventions: plugin matching, shortcuts, quit path, packaging."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from GUI.app.host_config import HostConfig, set_host_config
from GUI.app.ui.qt.controllers.shortcut_manager import default_shortcut_sequences
from GUI.app.ui.qt.widgets.notification_center import uses_manual_popup_shadow
from GUI.app.utils.dev_mode_utils import linux_mocks
from GUI.plugin_system.registry import PluginRegistry

_BUILD_SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(_BUILD_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_BUILD_SCRIPT_DIR))

import build as build_script  # noqa: E402  (path set above)


# --- Extension plugin platform matching -----------------------------------


class _MacLabelled:
    supported_platforms = ["macOS"]


class _DarwinLabelled:
    supported_platforms = ["Darwin"]


class _WindowsOnly:
    supported_platforms = ["Windows"]


class _AnyPlatform:
    supported_platforms: list[str] = []


def test_extension_plugin_accepts_macos_label_on_darwin(monkeypatch) -> None:
    """"macOS" is the label plugins actually write; platform.system() says Darwin."""
    import platform as platform_module

    monkeypatch.setattr(platform_module, "system", lambda: "Darwin")
    registry = PluginRegistry()

    assert registry._check_extension_plugin_compatibility(_MacLabelled) is True
    assert registry._check_extension_plugin_compatibility(_DarwinLabelled) is True
    assert registry._check_extension_plugin_compatibility(_AnyPlatform) is True
    assert registry._check_extension_plugin_compatibility(_WindowsOnly) is False


def test_extension_plugin_rejects_macos_label_off_darwin(monkeypatch) -> None:
    import platform as platform_module

    monkeypatch.setattr(platform_module, "system", lambda: "Linux")
    registry = PluginRegistry()

    assert registry._check_extension_plugin_compatibility(_MacLabelled) is False
    assert registry._check_extension_plugin_compatibility(_DarwinLabelled) is False


# --- Shortcuts -------------------------------------------------------------


def test_tab_shortcuts_avoid_the_macos_app_switcher() -> None:
    """Qt maps Ctrl to Command, so Ctrl+Tab would be the OS app switcher."""
    darwin = default_shortcut_sequences("darwin")
    assert darwin["next_tab"] == "Meta+Tab"
    assert darwin["prev_tab"] == "Meta+Shift+Tab"
    assert darwin["fullscreen"] == "Ctrl+Meta+F"


@pytest.mark.parametrize("platform_name", ["linux", "windows"])
def test_tab_shortcuts_unchanged_elsewhere(platform_name: str) -> None:
    sequences = default_shortcut_sequences(platform_name)
    assert sequences["next_tab"] == "Ctrl+Tab"
    assert sequences["prev_tab"] == "Ctrl+Shift+Tab"
    assert sequences["fullscreen"] == "F11"


# --- Quit-path teardown ----------------------------------------------------


class _FakeLoader:
    def __init__(self, running: bool) -> None:
        self._running = running
        self.cancelled = False
        self.waited = False

    def cancel(self) -> None:
        self.cancelled = True

    def isRunning(self) -> bool:  # noqa: N802  (Qt naming)
        return self._running

    def wait(self, _timeout: int | None = None) -> bool:
        self.waited = True
        self._running = False
        return True


class _FakeWindow:
    """Stand-in for MainWindow state that finalize_shutdown touches."""

    def __init__(self, *, loader: _FakeLoader | None, close_complete: bool = False) -> None:
        self.tab_loader = loader
        self._close_complete = close_complete
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1


def _finalize(window: _FakeWindow) -> None:
    from GUI.app.ui.qt.main_window import MainWindow

    MainWindow.finalize_shutdown(window)


def test_finalize_shutdown_drains_loader_then_closes() -> None:
    """closeEvent defers on a running loader via a timer no quit path will run."""
    loader = _FakeLoader(running=True)
    window = _FakeWindow(loader=loader)

    _finalize(window)

    assert loader.cancelled is True
    assert loader.waited is True
    assert window.close_calls == 1


def test_finalize_shutdown_is_a_noop_after_close_completed() -> None:
    loader = _FakeLoader(running=False)
    window = _FakeWindow(loader=loader, close_complete=True)

    _finalize(window)
    _finalize(window)

    assert window.close_calls == 0
    assert loader.cancelled is False


def test_quit_teardown_is_wired_to_about_to_quit() -> None:
    """Nothing else reaches window teardown when the loop stops without a close."""
    import inspect

    from GUI.app.ui.qt import application

    source = inspect.getsource(application.QtApplicationBackend.run)
    assert "aboutToQuit.connect(window.finalize_shutdown)" in source


# --- Dev-mode mocks --------------------------------------------------------


def test_darwin_mock_subset_leaves_real_posix_modules_alone() -> None:
    """pwd/grp/fcntl work on macOS; stubbing them fakes the sudo status UI."""
    for name in ("pwd", "grp", "fcntl", "posix", "termios", "resource", "syslog"):
        assert name not in linux_mocks.DARWIN_MISSING_MODULES

    for name in ("spwd", "crypt", "dbus", "gi"):
        assert name in linux_mocks.DARWIN_MISSING_MODULES

    assert set(linux_mocks.DARWIN_MISSING_MODULES) <= set(linux_mocks.LINUX_MODULES)


def test_plugin_service_installs_only_the_missing_subset_on_darwin() -> None:
    import inspect

    from GUI.app.services import plugin_service

    source = inspect.getsource(plugin_service.PluginService._install_cross_platform_mocks)
    assert "install_linux_mocks(DARWIN_MISSING_MODULES)" in source


def test_install_linux_mocks_defaults_to_the_full_set() -> None:
    """Linux and Windows hosts must keep mocking everything they lack."""
    import inspect

    signature = inspect.signature(linux_mocks.install_linux_mocks)
    assert signature.parameters["modules"].default is None


# --- Appearance ------------------------------------------------------------


def test_popup_shadow_is_left_to_macos() -> None:
    """A Qt.Popup already has a compositor shadow on macOS; a manual one doubles it."""
    assert uses_manual_popup_shadow("darwin") is False
    assert uses_manual_popup_shadow("windows") is False
    assert uses_manual_popup_shadow("linux") is True


def test_no_hardcoded_font_families_in_qt_widgets() -> None:
    """Named Windows fonts fall back to 9pt Arial on macOS."""
    qt_root = Path(__file__).resolve().parents[1] / "app" / "ui" / "qt"
    offenders = []
    for path in qt_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for marker in ('QFont("', "font-family"):
            if marker in text:
                offenders.append(f"{path.name}: {marker}")
    assert offenders == []


# --- Log viewer / logging service agreement --------------------------------


def test_log_viewer_looks_where_the_logger_writes(tmp_path: Path) -> None:
    """utils.paths.logs_dir ignores HostConfig, so the two used to diverge."""
    import logging

    from GUI.app.services import logging_service
    from GUI.app.ui.dialogs import log_viewer_dialog

    set_host_config(HostConfig(app_id="log-probe", user_data_dir=tmp_path, portable=False))
    try:
        viewer_dir = log_viewer_dialog.get_host_config().logs_dir()
        assert viewer_dir == tmp_path / "logs"

        # Where the writer actually puts the file, not where it says it will.
        probe_logger = logging.getLogger("gui-log-path-probe")
        monkeypatched_save = getattr(logging_service, "SAVE_LOGS_TO_FILE", None)
        logging_service.SAVE_LOGS_TO_FILE = True
        try:
            logging_service._configure_handlers(probe_logger, logging.INFO)
            written = [
                Path(handler.baseFilename)
                for handler in probe_logger.handlers
                if hasattr(handler, "baseFilename")
            ]
        finally:
            logging_service.SAVE_LOGS_TO_FILE = monkeypatched_save
            for handler in probe_logger.handlers[:]:
                handler.close()
                probe_logger.removeHandler(handler)

        assert written, "logging service installed no file handler"
        assert all(path.parent == viewer_dir for path in written)
    finally:
        set_host_config(None)


# --- Bundle metadata -------------------------------------------------------


def test_bundle_identifier_is_reverse_dns() -> None:
    assert build_script.derive_bundle_identifier("Basic UI Application") == (
        "com.example.basic-ui-application"
    )
    assert build_script.derive_bundle_identifier("My__Weird!! App") == "com.example.my-weird-app"
    assert build_script.derive_bundle_identifier("   ") == "com.example.application"
    assert build_script.derive_bundle_identifier("App", prefix="org.host") == "org.host.app"


def test_plist_updates_strip_non_numeric_version_suffixes() -> None:
    """macOS rejects a CFBundleVersion like 6.1.0-dev-1."""
    updates = build_script.macos_plist_updates(
        version="6.1.0-dev-1",
        app_name="Basic UI Application",
        min_system_version="13.0",
    )
    assert updates == {
        "CFBundleShortVersionString": "6.1.0",
        "CFBundleVersion": "6.1.0",
        "CFBundleDisplayName": "Basic UI Application",
        "LSMinimumSystemVersion": "13.0",
    }


def test_plist_patch_preserves_unrelated_keys(tmp_path: Path) -> None:
    import plistlib

    contents = tmp_path / "Sample.app" / "Contents"
    contents.mkdir(parents=True)
    (contents / "Info.plist").write_bytes(
        plistlib.dumps(
            {
                "CFBundleExecutable": "Sample",
                "CFBundleShortVersionString": "0.0.0",
                "NSHighResolutionCapable": True,
            }
        )
    )

    assert build_script.patch_macos_plist(contents.parent, {"CFBundleVersion": "1.2.3"}) is True

    data = plistlib.loads((contents / "Info.plist").read_bytes())
    assert data["CFBundleVersion"] == "1.2.3"
    assert data["CFBundleExecutable"] == "Sample"
    assert data["NSHighResolutionCapable"] is True


def test_plist_patch_reports_a_missing_bundle(tmp_path: Path) -> None:
    assert build_script.patch_macos_plist(tmp_path / "Missing.app", {"X": "y"}) is False


def test_min_system_version_comes_from_the_pyside_wheel() -> None:
    """The bundle can only run where its Qt build runs."""
    detected = build_script.detect_macos_min_system_version()
    major, _, minor = detected.partition(".")
    assert major.isdigit() and minor.isdigit()
