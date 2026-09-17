"""Qt application backend implementing IUIApplication."""

from __future__ import annotations

import logging
import sys
from typing import Any, List, Optional

from ...constants import GUI_API_VERSION
from ...services.container import ServiceContainer
from ...services.interfaces import ISettingsService
from ...services.daemon_lifecycle_service import DaemonLifecycleService
from ..backend_wiring import (
    install_dialog_presenter,
    register_event_loop,
    save_gui_version,
    shutdown_daemon,
    start_daemon_if_required,
    wire_notifications,
)
from ..notification_bridge import NotificationShellBridge
from ....plugin_system.interfaces import IPluginResourceCleanup
from .bindings import QApplication
from .event_dispatcher import QtEventDispatcher
from .lifecycle import configure_qt_application
from .main_window import MainWindow
from .plugin_cleanup import QtPluginResourceCleanup
from .presenters import QtDialogPresenter
from .theme_init import ThemeInitService

logger = logging.getLogger(__name__)


class QtApplicationBackend:
    """Qt-specific UI application backend."""

    def __init__(self, container: ServiceContainer, argv: List[str], version_name: str) -> None:
        self._container = container
        self._argv = argv
        self._version_name = version_name
        self._app: Optional[QApplication] = None
        self._daemon_lifecycle: Optional[DaemonLifecycleService] = None
        self._daemon_client: Any = None
        self._notification_bridge: Optional[NotificationShellBridge] = None
        self._theme_init: Optional[ThemeInitService] = None

    def run(self) -> int:
        from .deps_service import QtDepsService, should_skip_qt_deps

        skip_deps = should_skip_qt_deps(self._argv)
        qt_deps = QtDepsService()
        deps_ok, deps_message = qt_deps.ensure_dependencies(skip=skip_deps)
        if not deps_ok:
            logger.error("Required Qt xcb dependencies are missing.")
            if deps_message:
                print(deps_message, file=sys.stderr)
            return 1

        save_gui_version(self._container)

        # Drop only our own flag so Qt does not warn about an unknown option.
        qt_argv = [arg for arg in self._argv if arg != "--skip-qt-deps"]
        self._app = QApplication(qt_argv)

        dispatcher = QtEventDispatcher.get_instance()
        register_event_loop(self._container, dispatcher)
        self._container.register_singleton(
            IPluginResourceCleanup, QtPluginResourceCleanup()
        )

        configure_qt_application(self._app, self._version_name, GUI_API_VERSION)

        # Held for the process lifetime: it owns the colorSchemeChanged slot.
        self._theme_init = ThemeInitService()
        settings_service = self._container.get(ISettingsService)
        theme_manager = self._theme_init.initialize(self._container, settings_service)

        # Show the shell before optional auto-daemon elevation so hosts with
        # REQUIRE_ADMIN_BY_DEFAULT=True are not stuck on a blank process during pkexec.
        window = MainWindow(
            theme_manager=theme_manager,
            settings_service=settings_service,
            container=self._container,
        )

        install_dialog_presenter(self._container, QtDialogPresenter(parent=window))
        self._notification_bridge = wire_notifications(self._container, window)

        # Teardown must be reachable from the quit path, not just from a window
        # close: an event-loop stop that skips closeEvent otherwise loses window
        # geometry, session state and extension shutdown. finalize_shutdown() is
        # a no-op once closeEvent has already completed.
        self._app.aboutToQuit.connect(window.finalize_shutdown)

        window.show()
        # Process one event loop tick so the window paints before a blocking daemon start
        self._app.processEvents()

        self._daemon_lifecycle, self._daemon_client = start_daemon_if_required(self._container)

        exit_code = self._app.exec()

        shutdown_daemon(self._daemon_lifecycle, self._daemon_client)

        logger.info(f"Application closed with code {exit_code}")
        return exit_code

    def quit(self) -> None:
        if self._app:
            self._app.quit()


__all__ = ['QtApplicationBackend']
