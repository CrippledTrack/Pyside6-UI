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
from .bindings import QApplication
from .event_dispatcher import QtEventDispatcher
from .lifecycle import configure_qt_application
from .main_window import MainWindow
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

    def run(self) -> int:
        from .deps_service import QtDepsService

        qt_deps = QtDepsService()
        deps_ok, deps_message = qt_deps.ensure_dependencies()
        if not deps_ok:
            logger.error("Required Qt xcb dependencies are missing.")
            if deps_message:
                print(deps_message, file=sys.stderr)
            return 1

        save_gui_version(self._container)

        self._app = QApplication(self._argv)

        dispatcher = QtEventDispatcher.get_instance()
        register_event_loop(self._container, dispatcher)

        configure_qt_application(self._app, self._version_name, GUI_API_VERSION)

        theme_init = ThemeInitService()
        settings_service = self._container.get(ISettingsService)
        theme_manager = theme_init.initialize(self._container, settings_service)

        self._daemon_lifecycle, self._daemon_client = start_daemon_if_required(self._container)

        window = MainWindow(
            theme_manager=theme_manager,
            settings_service=settings_service,
            container=self._container,
        )

        install_dialog_presenter(self._container, QtDialogPresenter(parent=window))
        self._notification_bridge = wire_notifications(self._container, window)

        window.show()
        exit_code = self._app.exec()

        shutdown_daemon(self._daemon_lifecycle, self._daemon_client)

        logger.info(f"Application closed with code {exit_code}")
        return exit_code

    def quit(self) -> None:
        if self._app:
            self._app.quit()


__all__ = ['QtApplicationBackend']
